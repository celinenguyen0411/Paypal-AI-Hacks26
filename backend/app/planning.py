import math
from datetime import timedelta
from itertools import permutations, product
from uuid import uuid4

from .ask_schemas import AskResponse, ExtractedIntent
from .errors import APIError
from .geometry import distance
from .seed import CAMPUS
from .services import WALK_SPEED_M_S

DWELL_S = {"lunch": 1200, "coffee": 300, "groceries": 600, "free": 600}


class PlanningService:
    """Use AI for intent only; compute catalog selection, route timing, and totals locally."""

    def __init__(self, maps, ai):
        self.maps, self.ai, self.database = maps, ai, maps.database

    def ask(self, body, user):
        previous = None
        if body.conversation_id:
            previous = self.database.conversation(body.conversation_id, user)
            if previous is None:
                raise APIError("conversation_not_found", "Conversation not found for this user.", 404)
        extracted = self.ai.extract(body.message, previous, self.maps.now())
        # Validate even injected/test clients so planning never trusts provider-specific objects.
        try:
            extracted = ExtractedIntent.model_validate(extracted)
        except ValueError:
            raise APIError("llm_unavailable", "AI returned an invalid request. Please try again.", 503) from None
        conversation_id = body.conversation_id or "cv_" + uuid4().hex
        origin = (body.location.model_dump() if body.location else
                  previous["intent"]["start"] if previous else CAMPUS)
        start = {"lat": origin["lat"], "lng": origin["lng"], "label": "Starting point"}
        intent = dict(budget_cents=extracted.budget_cents, needs=[n.model_dump() for n in extracted.needs],
                      diet=extracted.diet, party_size=extracted.party_size,
                      max_walk_min=extracted.max_walk_min, deadline=extracted.deadline, start=start)
        reason = self.clarification(extracted)
        plan, budget_check = None, None
        if reason:
            kind, reply = "clarify", reason
        elif extracted.kind == "answer":
            kind = "answer"
            budget_check = self.budget_check(extracted.budget_cents)
            if budget_check is None:
                reply = "No account balance is connected, so I cannot verify what you can afford."
            else:
                amount = extracted.budget_cents / 100
                safe = budget_check["safe_to_spend_cents"] / 100
                reply = (f"In this demo, ${amount:.2f} {'fits' if budget_check['ok'] else 'exceeds'} "
                         f"your fictional ${safe:.2f} safe-to-spend balance.")
        else:
            kind = "route_plan"
            plan = self.build_plan(extracted, start)
            budget_check = self.budget_check(plan["totals"]["cost_cents"])
            if budget_check and not budget_check["ok"]:
                raise APIError("over_safe_to_spend", "This plan exceeds the demo safe-to-spend balance.")
            totals = plan["totals"]
            status = "over" if totals["over_budget"] else "within"
            fallback = (f"Estimated cost: ${totals['cost_cents'] / 100:.2f}, {status} your budget. "
                        f"Estimated return: {totals['return_at']}. Prices and walking times are estimates.")
            reply = self.ai.explain(plan, fallback)
        response = AskResponse.model_validate(dict(
            demo=self.maps.demo(), kind=kind, conversation_id=conversation_id, reply=reply,
            intent=intent, budget_check=budget_check, plan=plan,
        )).model_dump(mode="json", by_alias=True)
        state = {"intent": response["intent"], "plan": response["plan"],
                 "exclude_place_ids": extracted.exclude_place_ids}
        self.database.save_exchange(conversation_id, user, state, response["plan"])
        return response

    def clarification(self, intent):
        if intent.diet:
            return "Dietary suitability is unverified. Can you plan without a dietary guarantee?"
        if intent.deadline and (intent.deadline.utcoffset() is None or intent.deadline <= self.maps.now()):
            return "What future deadline, including date and timezone, should I use?"
        if intent.kind == "clarify":
            return intent.clarification or "What do you need, and what is your total budget?"
        if intent.budget_cents is None:
            return "What is your total budget?"
        if intent.kind == "route_plan" and not intent.needs:
            return "Do you need lunch, coffee, groceries, or a free stop?"
        return None

    def budget_check(self, cost):
        if not self.maps.settings.demo_mode:
            return None
        safe = self.maps.settings.demo_safe_to_spend_cents
        return dict(safe_to_spend_cents=safe, plan_cents=cost, ok=cost <= safe,
                    bills_covered=[], as_of=self.maps.now(), source="demo")

    def build_plan(self, intent, start):
        """Search a bounded candidate set; require a round trip and keep groceries last."""
        choices = []
        for need in intent.needs:
            options = []
            for place in self.maps.catalog:
                meters = distance(start, place["location"])
                if (place["category"] != need.category or place["place_id"] in intent.exclude_place_ids
                        or meters / WALK_SPEED_M_S > intent.max_walk_min * 60):
                    continue
                multiplier = intent.party_size if need.category in ("lunch", "coffee") else 1
                cost = (need.amount_cents if need.amount_cents is not None
                        else place["est_cost_cents"] * multiplier)
                options.append(dict(place, est_cost_cents=cost,
                                    cost_source="user" if need.amount_cents is not None else "category_table"))
            options.sort(key=lambda p: (p["est_cost_cents"], distance(start, p["location"]), p["place_id"]))
            if not options:
                raise APIError("no_places_fit", f"No {need.category} places fit this walking range.")
            choices.append(options[:5])

        best = None
        for selection in product(*choices):
            if len({p["place_id"] for p in selection}) != len(selection):
                continue
            for ordered in permutations(selection):
                if any(p["category"] == "groceries" and later["category"] != "groceries"
                       for i, p in enumerate(ordered) for later in ordered[i + 1:]):
                    continue
                points = [start, *(p["location"] for p in ordered), start]
                meters = [round(distance(a, b)) for a, b in zip(points, points[1:])]
                walking = [math.ceil(m / WALK_SPEED_M_S) for m in meters]
                duration = sum(walking) + sum(DWELL_S[p["category"]] for p in ordered)
                if sum(walking) > intent.max_walk_min * 60:
                    continue
                if intent.deadline and self.maps.now() + timedelta(seconds=duration) > intent.deadline:
                    continue
                cost = sum(p["est_cost_cents"] for p in ordered)
                key = (cost, sum(walking), tuple(p["place_id"] for p in ordered))
                if best is None or key < best[0]:
                    best = (key, ordered, meters, walking, duration)
        if best is None:
            raise APIError("no_places_fit", "No round trip fits your walking limit and deadline. Try a wider limit.")
        _, ordered, meters, walking, duration = best
        now = self.maps.now()
        elapsed, stops, legs = 0, [], []
        for index, place in enumerate(ordered):
            elapsed += walking[index]
            stops.append(dict(
                order=index + 1, place_id=place["place_id"], name=place["name"], category=place["category"],
                location=place["location"], partner=place["partner"], sponsored=place["sponsored"],
                est_cost_cents=place["est_cost_cents"], cost_source=place["cost_source"],
                checkin_xp=place["checkin_xp"], arrive_at=(now + timedelta(seconds=elapsed)).isoformat(),
                dwell_s=DWELL_S[place["category"]],
                why=["Lowest estimated total cost among the nearby candidates that fit this outing"],
                attribution=place["attribution"],
            ))
            legs.append({"from": "start" if index == 0 else index, "to": index + 1,
                         "distance_m": meters[index], "duration_s": walking[index]})
            elapsed += DWELL_S[place["category"]]
        legs.append({"from": len(ordered), "to": "start", "distance_m": meters[-1], "duration_s": walking[-1]})
        cost = sum(p["est_cost_cents"] for p in ordered)
        coordinates = [[start["lng"], start["lat"]],
                       *[[p["location"]["lng"], p["location"]["lat"]] for p in ordered],
                       [start["lng"], start["lat"]]]
        return dict(
            plan_id="pl_" + uuid4().hex, stops=stops, legs=legs,
            route_geojson={"type": "Feature", "properties": {"estimated": True},
                           "geometry": {"type": "LineString", "coordinates": coordinates}},
            totals=dict(cost_cents=cost, net_cents=cost, budget_left_cents=intent.budget_cents - cost,
                        over_budget=cost > intent.budget_cents, distance_m=sum(meters), duration_s=duration,
                        return_at=(now + timedelta(seconds=duration)).isoformat()),
            xp_preview=[dict(quest="plan_route", xp=30, checkable=True, when="on_confirm"),
                        dict(quest="finish_within_budget", xp=30, checkable=False,
                             when="end_of_day", verify="user_confirms_totals")],
            ranking="Lowest estimated cost, then walking time, among up to five candidates per need. "
                    "Round trip to the start; groceries last. Sponsors receive no ranking boost.",
        )

    def confirm(self, plan_id, body, user):
        if body.swaps_applied:
            raise APIError("swaps_not_supported", "Use a conversation follow-up to replace a stop before confirming.")
        saved = self.database.confirm_plan(plan_id, user, self.maps.now().date().isoformat())
        if saved is None:
            raise APIError("plan_not_found", "Plan not found for this user.", 404)
        plan, awarded = saved
        return dict(demo=self.maps.demo(), plan=plan, xp_awarded=awarded, league_xp_awarded=awarded)
