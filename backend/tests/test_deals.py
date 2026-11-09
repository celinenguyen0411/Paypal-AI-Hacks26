from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import services
from app.application import create_app
from app.ask_schemas import ExtractedIntent
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


def create_as(client, merchant, title):
    return client.post("/merchant/community-quests", json=merchant_quest(title),
                       headers={"X-Merchant-Id": merchant}).json()["id"]


def quest_ids(client):
    return {quest["id"] for quest in client.get("/map/community-quests").json()["quests"]}


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
