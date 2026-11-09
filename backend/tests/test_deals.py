import sqlite3
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import rate_limit, services
from app.application import create_app
from app.ask_schemas import ExtractedIntent
from app.config import TZ
from app.errors import APIError
from app.seed import ZONE


class WednesdayAI:
    def __init__(self):
        self.intent = ExtractedIntent(
            kind="route_plan", budget_cents=3000,
            needs=[{"category": "lunch"}, {"category": "coffee"}, {"category": "groceries"}],
            deadline=datetime.fromisoformat("2026-11-04T14:00:00-06:00"))

    def extract(self, message, previous, now):
        return self.intent

    def explain(self, plan, fallback):
        return fallback


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "deals.sqlite3", demo_mode=True)
    app.state.planning_service.ai = WednesdayAI()
    with TestClient(app) as test_client:
        yield test_client


def ask(client):
    return client.post("/ask", json={"message": "Lunch, coffee and groceries before 2pm, $30 max"}).json()


def test_wednesday_scene_uses_known_prices_and_starts_over_budget(client):
    plan = ask(client)["plan"]
    assert {s["place_id"] for s in plan["stops"]} == {"m_lakeview", "m_bean", "m_grocer"}
    assert plan["stops"][-1]["place_id"] == "m_grocer"
    assert all(s["cost_source"] == "merchant" for s in plan["stops"])
    assert plan["totals"]["cost_cents"] == 3050
    assert plan["totals"]["budget_left_cents"] == -50
    assert plan["totals"]["over_budget"] is True


def test_ink_and_oat_is_offered_as_the_swap_that_fixes_the_budget(client):
    plan = ask(client)["plan"]
    bean = next(s for s in plan["stops"] if s["place_id"] == "m_bean")
    assert len(plan["swaps"]) == 1
    swap = plan["swaps"][0]
    assert swap["replace_order"] == bean["order"]
    assert swap["with_place_id"] == "m_inkoat"
    assert swap["name"] == "Ink & Oat Café"
    assert swap["sponsored"] is True
    assert swap["est_cost_cents"] == 500
    assert swap["cashback_cents"] == 100
    assert swap["pay_less_today_cents"] == 150
    assert swap["saves_after_cashback_cents"] == 250
    assert 120 < swap["extra_walk_s"] <= 300
    assert swap["fixes_over_budget"] is True


def test_mama_lins_is_hidden_because_its_deal_starts_at_the_deadline(client):
    hidden = ask(client)["plan"]["hidden"]
    assert [(h["place_id"], h["reason"]) for h in hidden] == [("m_mamalin", "deal_window_misses_deadline")]
    assert hidden[0]["name"] == "Mama Lin's Noodles"
    assert hidden[0]["label"]


class NoAICalls:
    def extract(self, message, previous, now):
        raise AssertionError("A swap must not call the AI")

    def explain(self, plan, fallback):
        raise AssertionError("A swap must not call the AI")


def swap_body(plan):
    offer = plan["swaps"][0]
    return dict(replace_order=offer["replace_order"], with_place_id=offer["with_place_id"])


def test_tapping_the_swap_replans_to_29_dollars_without_the_ai(client):
    plan = ask(client)["plan"]
    client.app.state.planning_service.ai = NoAICalls()
    response = client.post(f"/ask/plans/{plan['plan_id']}/swap", json=swap_body(plan))
    assert response.status_code == 200
    swapped = response.json()["plan"]
    assert swapped["plan_id"] != plan["plan_id"]
    assert swapped["totals"]["cost_cents"] == 2900
    assert swapped["totals"]["cashback_cents"] == 100
    assert swapped["totals"]["net_cents"] == 2800
    assert swapped["totals"]["budget_left_cents"] == 100
    assert swapped["totals"]["over_budget"] is False
    assert response.json()["budget_check"]["plan_cents"] == 2900
    ink = next(s for s in swapped["stops"] if s["place_id"] == "m_inkoat")
    assert ink["pay_via"] == "quest"
    assert ink["deal_live_at_arrival"] is True
    assert ink["deal_id"] == "d_inkoat_coffee"
    assert ink["cashback_to_goal"] is True
    assert ink["cashback_clears_at"].startswith("2026-11-11")
    assert [-89.4014, 43.0732] in swapped["route_geojson"]["geometry"]["coordinates"]
    assert swapped["swaps"] == []
    assert client.post(f"/ask/plans/{swapped['plan_id']}/confirm").json()["xp_awarded"] == 30


def test_a_swap_that_was_not_offered_is_rejected(client):
    plan = ask(client)["plan"]
    body = dict(swap_body(plan), with_place_id="m_mamalin")
    response = client.post(f"/ask/plans/{plan['plan_id']}/swap", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == "swap_not_offered"


def test_another_users_plan_cannot_be_swapped(client):
    plan = ask(client)["plan"]
    response = client.post(f"/ask/plans/{plan['plan_id']}/swap", json=swap_body(plan),
                           headers={"X-User-Id": "someone-else"})
    assert response.status_code == 404
    assert response.json()["error"] == "plan_not_found"


def checkin_at(client, place_id, lat, lng, user="walker", simulated=False):
    return client.post("/map/checkin", headers={"X-User-Id": user}, json=dict(
        place_id=place_id, location={"lat": lat, "lng": lng}, accuracy_m=10, simulated=simulated)).json()


def test_visiting_a_partner_in_a_live_quest_counts_with_no_xp(client):
    result = checkin_at(client, "m_bean", 43.0749, -89.3955)
    assert result["ok"] is True
    assert result["xp_awarded"] == 0
    assert result["league_xp_awarded"] == 0
    assert result["community_progress"] == [
        dict(quest_id="cq_state_st", visited=1, needed=2, completed=False)]


def test_a_partner_visit_still_needs_you_to_be_there(client):
    assert checkin_at(client, "m_bean", 43.0, -89.0)["reason"] == "too_far"


def test_a_paid_place_outside_any_quest_still_uses_paypal(client):
    outside = next(p for p in client.get("/map/places?walk_min=5").json()["places"]
                   if p["place_id"].startswith("fsq:") and p["category"] != "free")
    location = outside["location"]
    result = checkin_at(client, outside["place_id"], location["lat"], location["lng"])
    assert result["reason"] == "paid_stop_uses_paypal"


def test_no_check_ins_at_night_even_when_pretending(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T22:00:00-06:00")
    result = checkin_at(client, "m_librarymall", 43.0752, -89.3966, simulated=True)
    assert result["ok"] is False
    assert result["reason"] == "closed_hours"
    assert result["xp_awarded"] == 0


def test_check_ins_open_at_seven_in_the_morning(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T07:00:00-06:00")
    assert checkin_at(client, "m_librarymall", 43.0752, -89.3966)["ok"] is True


def merchant_quest(title):
    return dict(title=title, zone_geojson=ZONE, place_ids=["m_librarymall", "m_lakeshore"],
                needed_visits=2, ends_at="2026-11-09T23:59:00-06:00")


def create_as(client, merchant, title, user="demo-user"):
    body = dict(merchant_quest(title), place_ids=[merchant, "m_lakeshore"])
    return client.post("/merchant/community-quests", json=body,
                       headers={"X-Merchant-Id": merchant, "X-User-Id": user}).json()["id"]


def quest_ids(client, user="demo-user"):
    response = client.get("/map/community-quests", headers={"X-User-Id": user})
    return {quest["id"] for quest in response.json()["quests"]}


def test_a_merchants_new_quest_replaces_its_previous_one(client):
    first = create_as(client, "m_bean", "First")
    second = create_as(client, "m_bean", "Second")
    assert second in quest_ids(client)
    assert first not in quest_ids(client)


def test_other_merchants_quests_survive_a_replacement(client):
    other = create_as(client, "m_grocer", "Grocer quest")
    create_as(client, "m_bean", "Bean quest")
    assert other in quest_ids(client)


def test_the_seeded_quest_is_never_replaced(client):
    create_as(client, "m_mamalin", "Mama Lin's new quest")
    assert "cq_state_st" in quest_ids(client)


def test_deal_live_status_follows_each_deals_own_window(client):
    places = {p["place_id"]: p for p in client.get("/map/places?walk_min=15").json()["places"]}
    assert places["m_inkoat"]["deal"]["live_now"] is True
    assert places["m_mamalin"]["deal"]["live_now"] is False


def lunch_at_mama_lins(client):
    client.app.state.planning_service.ai.intent = ExtractedIntent(
        kind="route_plan", budget_cents=3000, max_walk_min=30,
        needs=[{"category": "lunch"}], exclude_place_ids=["m_lakeview"])
    return ask(client)["plan"]["stops"][0]


def test_the_route_waits_a_few_minutes_for_a_deal_to_open(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T13:47:00-06:00")
    stop = lunch_at_mama_lins(client)
    assert stop["wait_s"] == 201
    assert stop["deal_live_at_arrival"] is True
    assert stop["cashback_cents"] == 210


def test_the_route_will_not_wait_more_than_ten_minutes(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T13:30:00-06:00")
    stop = lunch_at_mama_lins(client)
    assert stop["wait_s"] == 0
    assert stop["deal_live_at_arrival"] is False
    assert stop["cashback_cents"] == 0


def test_the_fallback_reply_reads_the_return_time_like_a_person(client):
    assert "1:16 PM" in ask(client)["reply"]


def plan_with(client, **fields):
    client.app.state.planning_service.ai.intent = ExtractedIntent(kind="route_plan", budget_cents=3000, **fields)
    return ask(client)["plan"]


def test_an_estimated_place_fills_in_when_no_known_price_route_fits(client):
    plan = plan_with(client, needs=[{"category": "coffee"}], max_walk_min=5)
    assert plan["stops"][0]["cost_source"] == "category_table"
    assert plan["stops"][0]["place_id"].startswith("fsq:")


def test_a_tight_deadline_also_falls_back_to_estimated_places(client):
    plan = plan_with(client, needs=[{"category": "coffee"}],
                     deadline=datetime.fromisoformat("2026-11-04T12:40:00-06:00"))
    assert plan["stops"][0]["place_id"].startswith("fsq:")


def test_two_grocery_stops_can_be_planned(client):
    plan = plan_with(client, needs=[{"category": "groceries"}, {"category": "groceries"}], max_walk_min=30)
    assert len({s["place_id"] for s in plan["stops"]}) == 2


def test_the_ranking_text_admits_partners_are_picked_first(client):
    ranking = ask(client)["plan"]["ranking"]
    assert "Only Quest partners have confirmed prices" in ranking
    assert "no ranking boost" not in ranking


def test_a_deal_that_just_is_not_running_does_not_blame_the_deadline(client):
    plan = plan_with(client, needs=[{"category": "lunch"}], max_walk_min=30,
                     deadline=datetime.fromisoformat("2026-11-04T17:00:00-06:00"))
    assert [(h["place_id"], h["reason"]) for h in plan["hidden"]] == [("m_mamalin", "deal_not_live_at_arrival")]


def test_a_place_already_in_the_route_is_not_listed_as_hidden(client):
    plan = plan_with(client, needs=[{"category": "coffee"}, {"category": "coffee"}], max_walk_min=30)
    stops = {s["place_id"] for s in plan["stops"]}
    assert not stops & {h["place_id"] for h in plan["hidden"]}


def test_cashback_never_exceeds_what_you_pay(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T14:30:00-06:00")
    plan = plan_with(client, needs=[{"category": "coffee", "amount_cents": 50}], max_walk_min=30,
                     exclude_place_ids=["m_bean"])
    ink = next(s for s in plan["stops"] if s["place_id"] == "m_inkoat")
    assert ink["cashback_cents"] == 50
    assert plan["totals"]["net_cents"] == 0


def test_percent_cashback_uses_the_listed_price_not_a_stated_amount(client, monkeypatch):
    monkeypatch.setattr(services, "FROZEN_AT", "2026-11-04T14:30:00-06:00")
    client.app.state.planning_service.ai.intent = ExtractedIntent(
        kind="route_plan", budget_cents=5000, needs=[{"category": "lunch", "amount_cents": 4000}], max_walk_min=30,
        exclude_place_ids=["m_lakeview"])
    stop = ask(client)["plan"]["stops"][0]
    assert stop["place_id"] == "m_mamalin"
    assert stop["cashback_cents"] == 210


WEDNESDAY_MESSAGE = "Wed 12:30: lunch, coffee and a few groceries before my 2pm class. $30 max."


class RecordingAI(WednesdayAI):
    def __init__(self):
        super().__init__()
        self.facts = None
        self.previous = None

    def extract(self, message, previous, now):
        self.previous = previous
        return self.intent

    def explain(self, plan, fallback):
        self.facts = plan
        return fallback


class RefusingAI:
    def extract(self, message, previous, now):
        raise APIError("rate_limited", "AI request limit reached. Try again shortly.", 429)

    def explain(self, plan, fallback):
        return fallback


def test_the_ai_reply_is_written_from_a_short_list_of_facts(client):
    recording = RecordingAI()
    client.app.state.planning_service.ai = recording
    ask(client)
    assert recording.facts == dict(
        stops=[dict(name="Lakeview Deli", price="$12.00"), dict(name="Bean Café", price="$6.50"),
               dict(name="Campus Grocer", price="$12.00")],
        total="$30.50", budget="$0.50 over budget", back_by="1:16 PM")


def test_a_follow_up_sends_the_ai_only_the_stops_of_the_last_plan(client):
    recording = RecordingAI()
    client.app.state.planning_service.ai = recording
    first = ask(client)
    client.post("/ask", json=dict(message="Swap the coffee", conversation_id=first["conversation_id"]))
    assert set(recording.previous["plan"]) == {"stops"}
    assert recording.previous["plan"]["stops"][1] == dict(place_id="m_bean", name="Bean Café", category="coffee")


def test_the_wednesday_prompt_still_plans_when_the_ai_refuses(client):
    client.app.state.planning_service.ai = RefusingAI()
    response = client.post("/ask", json=dict(message=WEDNESDAY_MESSAGE))
    assert response.status_code == 200
    assert response.json()["plan"]["totals"]["cost_cents"] == 3050


def test_any_other_message_reports_the_ai_limit(client):
    client.app.state.planning_service.ai = RefusingAI()
    response = client.post("/ask", json=dict(message="Lunch under $10"))
    assert response.status_code == 429
    assert response.json()["error"] == "rate_limited"


def test_the_wednesday_shortcut_is_demo_only(tmp_path):
    app = create_app(tmp_path / "real.sqlite3", demo_mode=False)
    app.state.planning_service.ai = RefusingAI()
    with TestClient(app) as real_client:
        assert real_client.post("/ask", json=dict(message=WEDNESDAY_MESSAGE)).status_code == 429


def swapped_plan(client):
    first = ask(client)
    plan = first["plan"]
    swapped = client.post(f"/ask/plans/{plan['plan_id']}/swap", json=swap_body(plan)).json()["plan"]
    return first["conversation_id"], plan, swapped


def follow_up(client, conversation_id, plan_id, **headers):
    ai = client.app.state.planning_service.ai
    ai.intent = ai.intent.model_copy(update=dict(budget_cents=3500))
    return client.post("/ask", headers=headers, json=dict(
        message="Make it $35", conversation_id=conversation_id, plan_id=plan_id))


def test_a_follow_up_keeps_a_swap_you_took(client):
    conversation_id, _, swapped = swapped_plan(client)
    plan = follow_up(client, conversation_id, swapped["plan_id"]).json()["plan"]
    assert "m_inkoat" in {s["place_id"] for s in plan["stops"]}
    assert plan["totals"]["cost_cents"] == 2900


def test_a_follow_up_after_undo_does_not_bring_the_swap_back(client):
    conversation_id, original, _ = swapped_plan(client)
    plan = follow_up(client, conversation_id, original["plan_id"]).json()["plan"]
    assert "m_bean" in {s["place_id"] for s in plan["stops"]}


def test_a_follow_up_can_replace_a_stop_you_swapped_to(client):
    conversation_id, _, swapped = swapped_plan(client)
    ai = client.app.state.planning_service.ai
    ai.intent = ai.intent.model_copy(update=dict(exclude_place_ids=["m_inkoat"]))
    plan = follow_up(client, conversation_id, swapped["plan_id"]).json()["plan"]
    assert "m_inkoat" not in {s["place_id"] for s in plan["stops"]}


def test_a_follow_up_cannot_use_another_users_plan(client):
    conversation_id, _, swapped = swapped_plan(client)
    other = client.post("/ask", json=dict(message="New outing"), headers={"X-User-Id": "someone-else"}).json()
    response = client.post("/ask", headers={"X-User-Id": "someone-else"}, json=dict(
        message="Make it $35", conversation_id=other["conversation_id"], plan_id=swapped["plan_id"]))
    assert response.status_code == 404
    assert response.json()["error"] == "plan_not_found"


def pretend(client, place_id, user="walker"):
    return checkin_at(client, place_id, 43.0, -89.0, user=user, simulated=True)


def test_a_merchant_quest_must_include_its_own_shop(client):
    body = dict(merchant_quest("Others only"), place_ids=["m_mamalin", "m_lakeview"])
    response = client.post("/merchant/community-quests", json=body, headers={"X-Merchant-Id": "m_bean"})
    assert response.status_code == 422
    assert response.json()["error"] == "merchant_not_in_quest"


def test_a_drawn_quest_is_only_visible_to_the_browser_that_drew_it(client):
    quest_id = create_as(client, "m_bean", "Mine", user="browser-a")
    assert quest_id in quest_ids(client, "browser-a")
    assert quest_id not in quest_ids(client, "browser-b")


def test_a_drawn_quest_does_not_tag_places_for_other_browsers(client):
    quest_id = create_as(client, "m_bean", "Mine", user="browser-a")
    def tags(user):
        places = client.get("/map/places", headers={"X-User-Id": user}).json()["places"]
        return next(p for p in places if p["place_id"] == "m_bean")["community_quest_ids"]
    assert quest_id in tags("browser-a")
    assert quest_id not in tags("browser-b")


def test_the_same_merchant_can_be_tried_by_different_browsers(client):
    first = create_as(client, "m_bean", "A", user="browser-a")
    second = create_as(client, "m_bean", "B", user="browser-b")
    assert first in quest_ids(client, "browser-a")
    assert second in quest_ids(client, "browser-b")


def test_a_browsers_new_quest_replaces_only_its_own_previous_one(client):
    first = create_as(client, "m_bean", "A", user="browser-a")
    second = create_as(client, "m_bean", "A2", user="browser-a")
    assert second in quest_ids(client, "browser-a")
    assert first not in quest_ids(client, "browser-a")


def test_outside_the_demo_quests_are_public(tmp_path):
    ends = (datetime.now(TZ) + timedelta(days=2)).isoformat()
    with TestClient(create_app(tmp_path / "real.sqlite3", demo_mode=False)) as real_client:
        body = dict(merchant_quest("Public"), place_ids=["m_bean", "m_lakeshore"], ends_at=ends)
        created = real_client.post("/merchant/community-quests", json=body,
                                   headers={"X-Merchant-Id": "m_bean", "X-User-Id": "owner"})
        assert created.status_code == 201
        assert created.json()["id"] in quest_ids(real_client, "someone-else")


def test_completing_a_quest_awards_the_badge_and_xp_once(client):
    first = pretend(client, "m_librarymall")
    assert first["quest_rewards"] == []
    second = pretend(client, "m_lakeshore")
    assert second["quest_rewards"] == [dict(quest_id="cq_state_st", badge="state_street_explorer", xp=40)]
    assert second["xp_awarded"] == 20
    assert pretend(client, "m_bean")["quest_rewards"] == []


def test_the_quest_list_shows_the_reward_was_earned(client):
    pretend(client, "m_librarymall")
    def rewarded():
        quests = client.get("/map/community-quests", headers={"X-User-Id": "walker"}).json()["quests"]
        return next(q for q in quests if q["id"] == "cq_state_st")["progress"]["rewarded"]
    assert rewarded() == 0
    pretend(client, "m_lakeshore")
    assert rewarded() == 1


def test_a_rejected_check_in_never_awards_a_reward(client):
    pretend(client, "m_librarymall")
    pretend(client, "m_lakeshore")
    assert pretend(client, "m_lakeshore")["reason"] == "already_today"
    assert pretend(client, "m_lakeshore")["quest_rewards"] == []


def visit_flags(client):
    path = client.app.state.map_service.database.path
    with sqlite3.connect(path) as connection:
        return dict(connection.execute("SELECT place_id, simulated FROM visits").fetchall())


def test_pretend_visits_are_flagged_in_the_ledger(client):
    checkin_at(client, "m_librarymall", 43.0752, -89.3966)
    pretend(client, "m_lakeshore")
    assert visit_flags(client) == {"m_librarymall": 0, "m_lakeshore": 1}


def test_an_existing_database_gains_the_simulated_flag(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE visits (user_id TEXT, place_id TEXT, day TEXT, visited_at TEXT, xp INTEGER, "
                           "PRIMARY KEY(user_id, place_id, day))")
        connection.execute("INSERT INTO visits VALUES ('u', 'm_bean', '2026-11-03', '2026-11-03T10:00:00-06:00', 0)")
    with TestClient(create_app(path, demo_mode=True)) as migrated:
        assert visit_flags(migrated) == {"m_bean": 0}


def test_a_new_quest_ignores_visits_made_before_it_existed(client):
    pretend(client, "m_bean", user="demo-user")
    quest_id = create_as(client, "m_bean", "Fresh start")
    quests = client.get("/map/community-quests").json()["quests"]
    assert next(q for q in quests if q["id"] == quest_id)["progress"]["visited"] == 0


def ask_from(client, address):
    return client.post("/ask", json=dict(message="Lunch"), headers={"X-Forwarded-For": address})


def test_one_address_cannot_flood_the_ask_bar(client):
    for _ in range(10):
        assert ask_from(client, "1.1.1.1").status_code == 200
    blocked = ask_from(client, "1.1.1.1")
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "too_many_requests"


def test_the_ask_limit_is_per_address(client):
    for _ in range(11):
        ask_from(client, "1.1.1.1")
    assert ask_from(client, "2.2.2.2").status_code == 200


def test_the_ask_limit_lifts_after_a_minute(client, monkeypatch):
    moment = [1000.0]
    monkeypatch.setattr(rate_limit, "monotonic", lambda: moment[0])
    for _ in range(11):
        ask_from(client, "1.1.1.1")
    moment[0] += 61
    assert ask_from(client, "1.1.1.1").status_code == 200


def test_quest_publishing_is_rate_limited_too(client):
    body = dict(merchant_quest("Spam"), place_ids=["m_bean", "m_lakeshore"])
    headers = {"X-Merchant-Id": "m_bean", "X-Forwarded-For": "3.3.3.3"}
    codes = [client.post("/merchant/community-quests", json=body, headers=headers).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10
    assert codes[10] == 429
