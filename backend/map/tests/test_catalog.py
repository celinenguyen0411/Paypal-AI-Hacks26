import json

import pytest
from fastapi.testclient import TestClient

from map_api.application import create_app
from map_api.catalog import load_places
from map_api.seed import PLACES, ZONE


def source_place(source_id, categories, **overrides):
    record = dict(entity_type="place", source="foursquare", source_id=source_id,
                  name=f"Test {source_id}", lat=43.0761, lon=-89.3999, categories=categories)
    record.update(overrides)
    return record


def dataset(tmp_path, records):
    path = tmp_path / "places.json"
    path.write_text(json.dumps(records))
    return path


def test_normalization_filtering_and_stable_ids(tmp_path):
    path = dataset(tmp_path, [
        source_place("coffee", ["Coffee Shop", "Restaurant"]),
        source_place("lunch", ["Thai Restaurant"]),
        source_place("grocery", ["Supermarket"]),
        source_place("coffee", ["Coffee Shop"]),
        source_place("private", ["Home (private)", "Restaurant"]),
        source_place("park", ["Park"]),
        source_place("far", ["Coffee Shop"], lat=0, lon=0),
        source_place("invalid", ["Coffee Shop"], lat=91),
        source_place("blank", ["Coffee Shop"], name=" "),
        {"name": "Missing required fields"},
    ])
    catalog = load_places(path)
    imported = catalog[len(PLACES):]
    assert [(p["place_id"], p["category"], p["est_cost_cents"]) for p in imported] == [
        ("fsq:coffee", "coffee", 500), ("fsq:lunch", "lunch", 1400),
        ("fsq:grocery", "groceries", 1200),
    ]
    assert imported[0]["location"] == {"lat": 43.0761, "lng": -89.3999}
    assert all(not p["partner"] and not p["sponsored"] and p["deal"] is None for p in imported)
    assert all(p["attribution"] == "foursquare" and p["cost_source"] == "category_table" for p in imported)
    assert catalog == load_places(path)


def test_startup_caches_snapshot_and_uses_catalog_for_quests(tmp_path):
    path = dataset(tmp_path, [source_place("one", ["Coffee Shop"]),
                              source_place("two", ["Restaurant"])])
    with TestClient(create_app(tmp_path / "db.sqlite3", True, places_path=path)) as client:
        path.write_text("[]")
        health = client.get("/health").json()
        assert health["status"] == "ok"
        assert health["snapshot_places_loaded"] == 2
        assert health["demo_places_loaded"] == 6
        assert health["places_loaded"] == 8
        places = client.get("/map/places").json()
        assert {"fsq:one", "fsq:two"} <= {p["place_id"] for p in places["places"]}
        assert places["attributions"] == ["foursquare"]
        body = dict(title="Real catalog quest", zone_geojson=ZONE,
                    place_ids=["fsq:one", "fsq:two"], needed_visits=2,
                    ends_at="2026-11-09T23:59:00-06:00")
        assert client.post("/merchant/community-quests", json=body).status_code == 201
        checkin = dict(place_id="fsq:one", location={"lat": 43.0761, "lng": -89.3999}, accuracy_m=10)
        assert client.post("/map/checkin", json=checkin).json()["reason"] == "paid_stop_uses_paypal"


@pytest.mark.parametrize("contents", ["{}", "not json"])
def test_malformed_dataset_fails_startup(tmp_path, contents):
    path = tmp_path / "bad.json"
    path.write_text(contents)
    with pytest.raises(ValueError):
        with TestClient(create_app(tmp_path / "db.sqlite3", True, places_path=path)):
            pass


def test_missing_dataset_fails_startup(tmp_path):
    with pytest.raises(FileNotFoundError):
        with TestClient(create_app(tmp_path / "db.sqlite3", True, places_path=tmp_path / "missing.json")):
            pass


def test_actual_snapshot_health_and_nearby_places(tmp_path):
    with TestClient(create_app(tmp_path / "real.sqlite3", True)) as client:
        health = client.get("/health").json()
        assert health["snapshot_places_loaded"] > 100
        places = client.get("/map/places?categories=coffee,lunch,groceries&walk_min=15").json()
        imported = [p for p in places["places"] if p["place_id"].startswith("fsq:")]
        assert imported
        assert {p["category"] for p in imported} == {"coffee", "lunch", "groceries"}
        assert all(p["attribution"] == "foursquare" and p["walk_s"] <= 900 for p in imported)
