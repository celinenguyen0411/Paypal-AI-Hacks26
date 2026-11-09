from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import services
from main import create_app
from app.seed import ZONE


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3", demo_mode=True)) as client:
        yield client


def checkin(place_id="m_librarymall", **overrides):
    return dict(place_id=place_id, location={"lat": 43.0752, "lng": -89.3966},
                accuracy_m=18, simulated=False, **overrides)


def quest(**overrides):
    return dict(title="Explore campus", zone_geojson=ZONE,
                place_ids=["m_librarymall", "m_lakeshore", "m_mamalin"], needed_visits=2,
                ends_at="2026-11-09T23:59:00-06:00", **overrides)


def test_places_filters_and_geojson(client):
    response = client.get("/map/places?categories=free&walk_min=5")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "fallback_seeded"
    assert data["demo"]["location"]["lat"] == 43.0761
    assert len(data["places"]) == 2
    assert all(p["category"] == "free" and p["walk_s"] <= 300 for p in data["places"])
    ring = data["isochrone_geojson"]["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    assert ring[0][0] < 0 < ring[0][1]
    assert client.get("/map/places?lat=0&lng=0").json()["places"] == []


@pytest.mark.parametrize("query", ["walk_min=7", "lat=91", "lng=nan", "categories=invalid"])
def test_query_errors_have_contract_shape(client, query):
    response = client.get("/map/places?" + query)
    assert response.status_code == 422
    assert {"error", "message", "demo"} <= response.json().keys()


def test_checkin_duplicate_and_user_isolation(client):
    first = client.post("/map/checkin", json=checkin()).json()
    assert first["ok"] and first["xp_awarded"] == first["league_xp_awarded"] == 20
    assert first["community_progress"][0]["visited"] == 1
    duplicate = client.post("/map/checkin", json=checkin()).json()
    assert duplicate["reason"] == "already_today" and duplicate["xp_awarded"] == 0
    assert client.post("/map/checkin", json=checkin(), headers={"X-User-Id": "another"}).json()["ok"]


def test_location_accuracy_and_paid_rejections(client):
    body = checkin()
    body["accuracy_m"] = 51
    assert client.post("/map/checkin", json=body).json()["reason"] == "low_accuracy"
    body["accuracy_m"] = 18
    body["location"] = {"lat": 0, "lng": 0}
    assert client.post("/map/checkin", json=body).json()["reason"] == "too_far"
    body["place_id"] = "m_bean"
    assert client.post("/map/checkin", json=body).json()["reason"] == "too_far"
    body["place_id"] = "missing"
    assert client.post("/map/checkin", json=body).status_code == 404


def test_simulation_and_quest_completion(client):
    body = checkin()
    body.update(location={"lat": 0, "lng": 0}, simulated=True)
    assert client.post("/map/checkin", json=body).json()["ok"]
    body["place_id"] = "m_lakeshore"
    second = client.post("/map/checkin", json=body).json()
    assert second["community_progress"][0]["completed"]
    assert client.get("/map/community-quests").json()["quests"][0]["progress"]["visited"] == 2
    assert client.get("/map/community-quests?lat=0&lng=0").json()["quests"] == []


def test_simulation_disabled_outside_demo(tmp_path):
    with TestClient(create_app(tmp_path / "normal.sqlite3", demo_mode=False)) as client:
        body = checkin()
        body["simulated"] = True
        data = client.post("/map/checkin", json=body).json()
        assert data["demo"] is None
        assert data["reason"] == "simulation_not_allowed"


def test_daily_cap(client, monkeypatch):
    monkeypatch.setattr(services, "DAILY_XP_CAP", 20)
    assert client.post("/map/checkin", json=checkin()).json()["ok"]
    body = checkin()
    body.update(place_id="m_lakeshore", simulated=True)
    assert client.post("/map/checkin", json=body).json()["reason"] == "daily_cap"


def test_concurrent_retries_award_once(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post("/map/checkin", json=checkin()).json(), range(4)))
    assert sum(r["xp_awarded"] for r in results) == 20
    assert sum(r["reason"] == "already_today" for r in results) == 3


def test_create_quest_and_persist(tmp_path):
    path = tmp_path / "persist.sqlite3"
    with TestClient(create_app(path, demo_mode=True)) as client:
        response = client.post("/merchant/community-quests", json=quest())
        assert response.status_code == 201
        quest_id = response.json()["id"]
        assert response.json()["places_in_zone"] >= 6
        assert client.post("/map/checkin", json=checkin()).json()["ok"]
        places = client.get("/map/places").json()["places"]
        assert quest_id in next(p for p in places if p["place_id"] == "m_librarymall")["community_quest_ids"]
    with TestClient(create_app(path, demo_mode=True)) as client:
        quests = client.get("/map/community-quests").json()["quests"]
        assert next(q for q in quests if q["id"] == quest_id)["progress"]["visited"] == 1
        assert client.post("/map/checkin", json=checkin()).json()["reason"] == "already_today"


@pytest.mark.parametrize("change,code", [
    ({"zone_geojson": {"type": "Polygon", "coordinates": [[[-90, 42], [-88, 42], [-88, 44], [-90, 42]]]}}, "zone_too_large"),
    ({"zone_geojson": {"type": "Polygon", "coordinates": [[]]}}, "invalid_zone"),
    ({"zone_geojson": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}}, "invalid_zone"),
    ({"ends_at": "2026-12-01T00:00:00-06:00"}, "invalid_end_time"),
    ({"ends_at": "2026-11-09T00:00:00"}, "invalid_end_time"),
    ({"place_ids": ["m_librarymall", "missing"]}, "invalid_places"),
    ({"place_ids": ["m_librarymall", "m_librarymall"]}, "invalid_places"),
    ({"needed_visits": 4}, "invalid_places"),
    ({"title": "  "}, "invalid_title"),
])
def test_quest_validation(client, change, code):
    body = quest()
    body.update(change)
    response = client.post("/merchant/community-quests", json=body)
    assert response.status_code == 422
    assert response.json()["error"] == code


def test_cors_and_openapi(client):
    response = client.options("/map/checkin", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,X-User-Id"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    schema = client.get("/openapi.json").json()
    assert len(schema["paths"]) == 8
    assert "CheckinResponse" in schema["components"]["schemas"]
