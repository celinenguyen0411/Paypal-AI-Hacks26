from datetime import timedelta
from uuid import uuid4

from .ask_schemas import AskResponse, ExtractedIntent, SwapResponse
from .errors import APIError
from .route_solver import DWELL_S, NoPlacesFit, Trip, solve
from .seed import CAMPUS

CASHBACK_CLEARS_DAYS = 7
RANKING = ("Places with a known price come first: the cheapest after cashback within a 2-minute detour. "
           "Places with only an estimated price fill a need when no known-price place fits. "
           "Round trip to the start; groceries last. Sponsors receive no ranking boost.")


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
        plan, budget_check, stop_needs = None, None, []
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
            plan, stop_needs = self.build_plan(extracted, start)
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
        context = dict(conversation_id=conversation_id, intent=extracted.model_dump(mode="json"),
                       start=start, forced={}, stop_needs=stop_needs)
        self.database.save_exchange(conversation_id, user, state, response["plan"], context)
        return response

    def swap(self, plan_id, body, user):
        saved = self.database.plan_with_context(plan_id, user)
        if saved is None:
            raise APIError("plan_not_found", "Plan not found for this user.", 404)
        plan, context = saved
        if not any(offer["replace_order"] == body.replace_order and offer["with_place_id"] == body.with_place_id
                   for offer in plan["swaps"]):
            raise APIError("swap_not_offered", "That swap is not available for this plan.")
        forced = {int(index): place_id for index, place_id in context["forced"].items()}
        forced[context["stop_needs"][body.replace_order - 1]] = body.with_place_id
        intent = ExtractedIntent.model_validate(context["intent"])
        new_plan, stop_needs = self.build_plan(intent, context["start"], forced)
        response = SwapResponse.model_validate(dict(
            demo=self.maps.demo(), plan=new_plan, budget_check=self.budget_check(new_plan["totals"]["cost_cents"]),
        )).model_dump(mode="json", by_alias=True)
        conversation_id = context["conversation_id"]
        state = dict(self.database.conversation(conversation_id, user), plan=response["plan"])
        self.database.save_exchange(conversation_id, user, state, response["plan"],
                                    dict(context, forced=forced, stop_needs=stop_needs))
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

    def trip(self, intent, start, forced=None):
        return Trip(start=start, now=self.maps.now(), needs=intent.needs, party_size=intent.party_size,
                    max_walk_s=intent.max_walk_min * 60, deadline=intent.deadline,
                    budget_cents=intent.budget_cents,
                    excluded=frozenset(intent.exclude_place_ids), forced=forced or {})

    def build_plan(self, intent, start, forced=None):
        trip = self.trip(intent, start, forced)
        try:
            solution = solve(self.maps.catalog, trip)
        except NoPlacesFit as failure:
            raise APIError("no_places_fit", str(failure)) from None
        stop_needs = [stop["place"]["need_index"] for stop in solution.route["stops"]]
        return self.plan_payload(solution, trip), stop_needs

    def plan_payload(self, solution, trip):
        route, now, start = solution.route, trip.now, trip.start
        stops, legs = [], []
        for number, stop in enumerate(route["stops"], start=1):
            stops.append(self.stop_payload(number, stop, now))
            legs.append({"from": "start" if number == 1 else number - 1, "to": number,
                         "distance_m": route["meters"][number - 1], "duration_s": route["walking"][number - 1]})
        legs.append({"from": len(stops), "to": "start", "distance_m": route["meters"][-1],
                     "duration_s": route["walking"][-1]})
        coordinates = [[start["lng"], start["lat"]],
                       *[[s["location"]["lng"], s["location"]["lat"]] for s in stops],
                       [start["lng"], start["lat"]]]
        return dict(
            plan_id="pl_" + uuid4().hex, stops=stops, legs=legs,
            route_geojson={"type": "Feature", "properties": {"estimated": True},
                           "geometry": {"type": "LineString", "coordinates": coordinates}},
            totals=dict(cost_cents=route["cost"], cashback_cents=route["cashback"], net_cents=route["net"],
                        budget_left_cents=trip.budget_cents - route["cost"],
                        over_budget=route["cost"] > trip.budget_cents, distance_m=sum(route["meters"]),
                        duration_s=route["duration"],
                        return_at=(now + timedelta(seconds=route["duration"])).isoformat()),
            xp_preview=[dict(quest="plan_route", xp=30, checkable=True, when="on_confirm"),
                        dict(quest="finish_within_budget", xp=30, checkable=False,
                             when="end_of_day", verify="user_confirms_totals")],
            swaps=solution.swaps, hidden=solution.hidden, ranking=RANKING,
        )

    def stop_payload(self, number, stop, now):
        place, deal = stop["place"], stop["place"]["deal"]
        clears_at = (now + timedelta(days=CASHBACK_CLEARS_DAYS)).isoformat() if stop["cashback"] else None
        return dict(
            order=number, place_id=place["place_id"], name=place["name"], category=place["category"],
            location=place["location"], partner=place["partner"], sponsored=place["sponsored"],
            est_cost_cents=place["est_cost_cents"], cost_source=place["cost_source"],
            cashback_cents=stop["cashback"], deal_id=deal["id"] if deal and stop["live"] else None,
            pay_via="quest" if place["partner"] else "as_usual", checkin_xp=place["checkin_xp"],
            arrive_at=(now + timedelta(seconds=stop["arrive_s"])).isoformat(), wait_s=stop["wait_s"],
            dwell_s=DWELL_S[place["category"]], deal_live_at_arrival=stop["live"],
            cashback_to_goal=stop["cashback"] > 0, cashback_clears_at=clears_at,
            why=[self.why(place, stop)], attribution=place["attribution"],
        )

    @staticmethod
    def why(place, stop):
        if stop["cashback"]:
            return f"Cheapest nearby after ${stop['cashback'] / 100:.2f} back"
        if place["cost_source"] == "category_table":
            return "No place with a known price fits, so this uses an estimated price"
        return "Cheapest known price within a 2-minute detour"

    def confirm(self, plan_id, body, user):
        if body.swaps_applied:
            raise APIError("swaps_not_supported", "Use a conversation follow-up to replace a stop before confirming.")
        saved = self.database.confirm_plan(plan_id, user, self.maps.now().date().isoformat())
        if saved is None:
            raise APIError("plan_not_found", "Plan not found for this user.", 404)
        plan, awarded = saved
        return dict(demo=self.maps.demo(), plan=plan, xp_awarded=awarded, league_xp_awarded=awarded)
