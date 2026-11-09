import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import permutations, product

from .deals import deal_cashback, deal_live, deal_opens_at, deal_runs_on
from .geometry import WALK_SPEED_M_S, distance

DWELL_S = {"lunch": 1200, "coffee": 300, "groceries": 600, "free": 600}
DEFAULT_DETOUR_S = 120
SWAP_DETOUR_S = 300
MAX_WAIT_S = 600
CANDIDATES_PER_NEED = 5
PARTY_PRICED_CATEGORIES = ("lunch", "coffee")
HIDDEN_LABELS = {
    "deal_not_today": "Its deal doesn't run today",
    "deal_window_misses_deadline": "Its deal starts too late for your deadline",
    "deal_not_live_at_arrival": "Its deal isn't running when you'd arrive",
    "too_far": "Too far to fit this outing",
}


class NoPlacesFit(Exception):
    pass


@dataclass(frozen=True)
class Trip:
    start: dict
    now: datetime
    needs: list
    party_size: int
    max_walk_s: int
    deadline: datetime | None
    budget_cents: int
    excluded: frozenset = frozenset()
    forced: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Solution:
    route: dict
    swaps: list
    hidden: list


def solve(catalog, trip):
    choices, quickest = _first_route_that_fits(catalog, trip)
    route = _take_cheaper_picks(quickest, choices, trip)
    swaps = _swaps(route, choices, trip)
    return Solution(route=route, swaps=swaps, hidden=_hidden(route, choices, swaps, trip))


def stop_for(route, need_index):
    return next(stop for stop in route["stops"] if stop["place"]["need_index"] == need_index)


def _first_route_that_fits(catalog, trip):
    try:
        choices = _candidates(catalog, trip, known_prices_only=True)
        return choices, _quickest_route(choices, trip)
    except NoPlacesFit:
        choices = _candidates(catalog, trip, known_prices_only=False)
        return choices, _quickest_route(choices, trip)


def _candidates(catalog, trip, known_prices_only):
    return [_options_for(index, need, catalog, trip, known_prices_only) for index, need in enumerate(trip.needs)]


def _options_for(index, need, catalog, trip, known_prices_only):
    options = [_option(index, need, place, trip) for place in catalog if _reachable(place, need, trip)]
    if index in trip.forced:
        options = [option for option in options if option["place_id"] == trip.forced[index]]
    if not options:
        raise NoPlacesFit(f"No {need.category} places fit this walking range.")
    options.sort(key=lambda p: (p["est_cost_cents"], distance(trip.start, p["location"]), p["place_id"]))
    known = [p for p in options if p["known_price"]] if known_prices_only else []
    return (known or options)[:CANDIDATES_PER_NEED]


def _reachable(place, need, trip):
    return (place["category"] == need.category and place["place_id"] not in trip.excluded
            and distance(trip.start, place["location"]) / WALK_SPEED_M_S <= trip.max_walk_s)


def _option(index, need, place, trip):
    multiplier = trip.party_size if need.category in PARTY_PRICED_CATEGORIES else 1
    explicit = need.amount_cents is not None
    listed = place["est_cost_cents"] * multiplier
    return dict(place, need_index=index, known_price=place["cost_source"] == "merchant", listed_cents=listed,
                est_cost_cents=need.amount_cents if explicit else listed,
                cost_source="user" if explicit else place["cost_source"])


def _quickest_route(choices, trip):
    best = None
    for selection in product(*choices):
        if len({place["place_id"] for place in selection}) != len(selection):
            continue
        route = _best_order(selection, trip)
        if route is None:
            continue
        key = (route["duration"], route["net"], _route_ids(route))
        if best is None or key < best[0]:
            best = (key, route)
    if best is None:
        raise NoPlacesFit("No round trip fits your walking limit and deadline. Try a wider limit.")
    return best[1]


def _take_cheaper_picks(route, choices, trip):
    for index, options in enumerate(choices):
        for option in options:
            changed = _replace(route, index, option, trip)
            if (changed and _net_at(changed, index) < _net_at(route, index)
                    and changed["duration"] - route["duration"] <= DEFAULT_DETOUR_S):
                route = changed
    return route


def _swaps(route, choices, trip):
    offers = (_best_swap(route, index, options, trip)
              for index, options in enumerate(choices) if index not in trip.forced)
    return [offer for offer in offers if offer]


def _best_swap(route, index, options, trip):
    offers = [offer for option in options if (offer := _swap_offer(route, index, option, trip))]
    return max(offers, key=lambda offer: offer["saves_after_cashback_cents"], default=None)


def _swap_offer(route, index, option, trip):
    changed = _replace(route, index, option, trip)
    if changed is None:
        return None
    extra = changed["duration"] - route["duration"]
    saved = _net_at(route, index) - _net_at(changed, index)
    if saved <= 0 or not DEFAULT_DETOUR_S < extra <= SWAP_DETOUR_S:
        return None
    current, new = stop_for(route, index), stop_for(changed, index)
    return dict(replace_order=route["stops"].index(current) + 1, with_place_id=option["place_id"],
                name=option["name"], partner=option["partner"], sponsored=option["sponsored"],
                est_cost_cents=option["est_cost_cents"], cashback_cents=new["cashback"],
                pay_less_today_cents=current["place"]["est_cost_cents"] - option["est_cost_cents"],
                saves_after_cashback_cents=saved, extra_walk_s=extra,
                fixes_over_budget=route["cost"] > trip.budget_cents >= changed["cost"])


def _hidden(route, choices, swaps, trip):
    offered = {swap["with_place_id"] for swap in swaps}
    return [entry for index, options in enumerate(choices) for option in options
            if (entry := _hidden_entry(route, index, option, offered, trip))]


def _hidden_entry(route, index, option, offered, trip):
    in_plan = option["place_id"] in _route_ids(route)
    if in_plan or option["place_id"] in offered or not option["partner"]:
        return None
    if _best_case_net(option) >= _net_at(route, index):
        return None
    reason = _hidden_reason(route, index, option, trip)
    return dict(place_id=option["place_id"], name=option["name"], reason=reason, label=HIDDEN_LABELS[reason])


def _best_case_net(option):
    deal, cost = option["deal"], option["est_cost_cents"]
    return cost - deal_cashback(deal, option["listed_cents"], cost) if deal else cost


def _hidden_reason(route, index, option, trip):
    deal = option["deal"]
    if deal and not deal_runs_on(deal, trip.now):
        return "deal_not_today"
    if deal and _opens_after_deadline(deal, trip):
        return "deal_window_misses_deadline"
    changed = _replace(route, index, option, trip)
    if changed and deal and not stop_for(changed, index)["live"]:
        return "deal_not_live_at_arrival"
    return "too_far"


def _opens_after_deadline(deal, trip):
    opens = deal_opens_at(deal, trip.now)
    return bool(opens and trip.deadline and opens >= trip.deadline)


def _best_order(selection, trip):
    best = None
    for ordered in permutations(selection):
        if not _groceries_last(ordered):
            continue
        for allow_wait in (True, False):
            route = _walk(ordered, trip, allow_wait)
            if route is None:
                continue
            key = (route["net"], route["duration"], _route_ids(route))
            if best is None or key < best[0]:
                best = (key, route)
    return best[1] if best else None


def _groceries_last(ordered):
    return not any(place["category"] == "groceries" and later["category"] != "groceries"
                   for i, place in enumerate(ordered) for later in ordered[i + 1:])


def _walk(ordered, trip, allow_wait):
    points = [trip.start, *(place["location"] for place in ordered), trip.start]
    meters = [round(distance(a, b)) for a, b in zip(points, points[1:])]
    walking = [math.ceil(m / WALK_SPEED_M_S) for m in meters]
    if sum(walking) > trip.max_walk_s:
        return None
    elapsed, stops = 0, []
    for index, place in enumerate(ordered):
        elapsed += walking[index]
        stop = _arrive(place, elapsed, trip.now + timedelta(seconds=elapsed), allow_wait)
        stops.append(stop)
        elapsed += stop["wait_s"] + DWELL_S[place["category"]]
    elapsed += walking[-1]
    if trip.deadline and trip.now + timedelta(seconds=elapsed) > trip.deadline:
        return None
    cost = sum(place["est_cost_cents"] for place in ordered)
    cashback = sum(stop["cashback"] for stop in stops)
    return dict(stops=stops, meters=meters, walking=walking, duration=elapsed,
                cost=cost, cashback=cashback, net=cost - cashback)


def _arrive(place, elapsed, arrival, allow_wait):
    deal = place["deal"]
    live, wait = bool(deal) and deal_live(deal, arrival), 0
    if deal and not live and allow_wait:
        wait = _seconds_until_open(deal, arrival)
        live = wait > 0
    cashback = deal_cashback(deal, place["listed_cents"], place["est_cost_cents"]) if live else 0
    return dict(place=place, arrive_s=elapsed, wait_s=wait, live=live, cashback=cashback)


def _seconds_until_open(deal, arrival):
    opens = deal_opens_at(deal, arrival)
    seconds = math.ceil((opens - arrival).total_seconds()) if opens else 0
    return seconds if seconds <= MAX_WAIT_S else 0


def _replace(route, need_index, option, trip):
    others = [stop["place"] for stop in route["stops"] if stop["place"]["need_index"] != need_index]
    taken = {place["place_id"] for place in others} | {stop_for(route, need_index)["place"]["place_id"]}
    return None if option["place_id"] in taken else _best_order([*others, option], trip)


def _net_at(route, need_index):
    stop = stop_for(route, need_index)
    return stop["place"]["est_cost_cents"] - stop["cashback"]


def _route_ids(route):
    return tuple(stop["place"]["place_id"] for stop in route["stops"])
