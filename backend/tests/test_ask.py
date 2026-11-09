import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from app import ai as ai_module
from app.ai import AIClient
from app.application import create_app
from app.ask_schemas import ExtractedIntent
from app.config import Settings
from app.errors import APIError


class FakeAI:
    def __init__(self):
        self.intent = ExtractedIntent(kind="route_plan", budget_cents=3000,
                                     max_walk_min=30,
                                     needs=[{"category": "lunch"}, {"category": "coffee"}],
                                     deadline=datetime.fromisoformat("2026-11-04T14:00:00-06:00"))
        self.previous = None

    def extract(self, message, previous, now):
        self.previous = previous
        return self.intent

    def explain(self, plan, fallback):
        return fallback


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("[]")
    app = create_app(tmp_path / "ask.sqlite3", True, places_path=path)
    fake = FakeAI()
    app.state.planning_service.ai = fake
    with TestClient(app) as client:
        yield client, fake, app


def ask(client, **overrides):
    return client.post("/ask", json={"message": "Lunch and coffee under $30", **overrides})


def test_plan_computed_from_catalog(setup):
    client, fake, app = setup
    response = ask(client, location=None)
    assert response.status_code == 200
    data = response.json()
    plan = data["plan"]
    assert data["kind"] == "route_plan" and data["conversation_id"].startswith("cv_")
    assert data["intent"]["start"]["lng"] == -89.3999
    assert plan["source"] == "fallback_seeded"
    catalog_ids = {p["place_id"] for p in app.state.map_service.catalog}
    assert all(stop["place_id"] in catalog_ids for stop in plan["stops"])
    assert plan["totals"]["cost_cents"] == sum(s["est_cost_cents"] for s in plan["stops"])
    assert plan["totals"]["budget_left_cents"] == 1150
    assert data["budget_check"]["plan_cents"] == 1850
    assert data["budget_check"]["source"] == "demo"
    assert plan["legs"][-1]["to"] == "start"
    assert sum(leg["duration_s"] for leg in plan["legs"]) <= fake.intent.max_walk_min * 60
    assert plan["totals"]["duration_s"] == sum(leg["duration_s"] for leg in plan["legs"]) + sum(s["dwell_s"] for s in plan["stops"])
    assert datetime.fromisoformat(plan["totals"]["return_at"]) <= fake.intent.deadline
    line = plan["route_geojson"]["geometry"]["coordinates"]
    assert line[0] == line[-1] == [-89.3999, 43.0761]


def test_groceries_last_and_explicit_total_allocation(setup):
    client, fake, _ = setup
    fake.intent = ExtractedIntent(kind="route_plan", budget_cents=4000, party_size=2, max_walk_min=30,
                                 needs=[{"category": "groceries", "amount_cents": 1234},
                                        {"category": "coffee"}, {"category": "lunch"}])
    plan = ask(client).json()["plan"]
    assert plan["stops"][-1]["category"] == "groceries"
    assert plan["stops"][-1]["cost_source"] == "user"
    assert plan["stops"][-1]["est_cost_cents"] == 1234
    assert plan["totals"]["cost_cents"] == 4934
    assert plan["totals"]["over_budget"]


@pytest.mark.parametrize("changes,fragment", [
    ({"budget_cents": None}, "budget"),
    ({"needs": []}, "need"),
    ({"diet": ["vegan"]}, "Dietary"),
    ({"deadline": datetime(2026, 11, 4, 14)}, "timezone"),
    ({"deadline": datetime.fromisoformat("2026-11-04T10:00:00-06:00")}, "future"),
    ({"kind": "clarify", "clarification": "Which type of stop?"}, "Which"),
])
def test_clarification(setup, changes, fragment):
    client, fake, _ = setup
    fake.intent = fake.intent.model_copy(update=changes)
    data = ask(client).json()
    assert data["kind"] == "clarify"
    assert fragment in data["reply"]
    assert data["plan"] is None


def test_affordability_and_safe_to_spend(setup):
    client, fake, _ = setup
    fake.intent = ExtractedIntent(kind="answer", budget_cents=6500)
    data = ask(client).json()
    assert data["kind"] == "answer" and not data["budget_check"]["ok"]
    assert "fictional" in data["reply"]
    fake.intent = ExtractedIntent(kind="route_plan", budget_cents=10000, max_walk_min=30,
                                 needs=[{"category": "lunch", "amount_cents": 6500}])
    assert ask(client).json()["error"] == "over_safe_to_spend"


def test_no_plan_fits_deadline_or_location(setup):
    client, fake, _ = setup
    fake.intent.deadline = datetime.fromisoformat("2026-11-04T12:31:00-06:00")
    assert ask(client).json()["error"] == "no_places_fit"
    fake.intent.deadline = None
    assert ask(client, location={"lat": 0, "lng": 0}).json()["error"] == "no_places_fit"


def test_followup_context_and_ownership(setup):
    client, fake, _ = setup
    first = ask(client).json()
    previous_coffee = next(s["place_id"] for s in first["plan"]["stops"] if s["category"] == "coffee")
    fake.intent.exclude_place_ids = [previous_coffee]
    second = ask(client, conversation_id=first["conversation_id"], message="Swap the coffee").json()
    assert fake.previous["intent"] == first["intent"]
    assert second["conversation_id"] == first["conversation_id"]
    assert previous_coffee not in {s["place_id"] for s in second["plan"]["stops"]}
    assert client.post("/ask", headers={"X-User-Id": "other"}, json={
        "message": "Swap the coffee", "conversation_id": first["conversation_id"]}).status_code == 404


def test_confirmation_is_idempotent_and_once_daily(setup):
    client, _, _ = setup
    plan = ask(client).json()["plan"]
    url = f"/ask/plans/{plan['plan_id']}/confirm"
    first = client.post(url).json()
    assert first["plan"] == plan
    assert first["xp_awarded"] == first["league_xp_awarded"] == 30
    assert client.post(url).json()["xp_awarded"] == 0
    second = ask(client).json()["plan"]
    assert client.post(f"/ask/plans/{second['plan_id']}/confirm").json()["xp_awarded"] == 0
    assert client.post(url, headers={"X-User-Id": "other"}).status_code == 404
    assert client.post(url, json={"swaps_applied": [2]}).json()["error"] == "swaps_not_supported"


def test_concurrent_confirm_awards_once(setup):
    client, _, _ = setup
    plan = ask(client).json()["plan"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(f"/ask/plans/{plan['plan_id']}/confirm").json(), range(4)))
    assert sum(r["xp_awarded"] for r in results) == 30


def test_missing_key_does_not_break_maps(setup):
    client, _, app = setup
    settings = replace(app.state.map_service.settings, groq_api_key="")
    app.state.planning_service.ai = AIClient(settings)
    response = ask(client)
    assert response.status_code == 503 and response.json()["error"] == "llm_unavailable"
    assert client.get("/map/places").status_code == 200


def test_real_clock_does_not_claim_account_balance(setup):
    client, fake, app = setup
    app.state.map_service.settings = replace(app.state.map_service.settings, demo_mode=False)
    fake.intent = ExtractedIntent(kind="answer", budget_cents=2000)
    data = ask(client).json()
    assert data["demo"] is None and data["budget_check"] is None
    assert "No account balance" in data["reply"]


def test_persistence_across_restart(setup):
    client, fake, app = setup
    data = ask(client).json()
    settings = app.state.map_service.settings
    restarted = create_app(settings.database_path, True, settings.places_path)
    restarted.state.planning_service.ai = fake
    with TestClient(restarted) as other:
        assert ask(other, conversation_id=data["conversation_id"]).status_code == 200
        assert other.post(f"/ask/plans/{data['plan']['plan_id']}/confirm").json()["xp_awarded"] == 30


@pytest.mark.parametrize("message", ["", "  ", "x" * 4001])
def test_input_validation(setup, message):
    client, _, _ = setup
    assert ask(client, message=message).status_code == 422


@pytest.mark.parametrize("status,code", [(401, "llm_unavailable"), (429, "rate_limited"), (500, "llm_unavailable")])
def test_provider_errors_and_narration_fallback(monkeypatch, status, code):
    settings = replace(Settings.from_env(), groq_api_key="test-key")
    def respond(request):
        return httpx.Response(status, json={"error": {"message": "private provider detail", "type": "api_error"}})
    monkeypatch.setattr(ai_module, "OpenAI", lambda **kwargs: OpenAI(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))))
    ai = AIClient(settings)
    with pytest.raises(APIError) as failure:
        ai.extract("Lunch", None, datetime.now())
    assert failure.value.code == code
    assert "private provider detail" not in failure.value.message
    assert ai.explain({}, "Computed fallback") == "Computed fallback"


def test_sdk_structured_output_parsing(monkeypatch):
    settings = replace(Settings.from_env(), groq_api_key="test-key")
    output = ExtractedIntent(kind="route_plan", budget_cents=2000, needs=[{"category": "coffee"}])
    def respond(request):
        body = json.loads(request.content)
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["model"] == settings.groq_model
        assert body["response_format"]["type"] == "json_schema"
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert set(schema["schema"]["required"]) == set(schema["schema"]["properties"])
        assert schema["schema"]["additionalProperties"] is False
        assert body["messages"][0]["role"] == "system"
        assert json.loads(body["messages"][1]["content"])["message"] == "Coffee under $20"
        return httpx.Response(200, json={
            "id": "chat_test", "object": "chat.completion", "created": 0,
            "model": settings.groq_model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": output.model_dump_json()}}],
        })
    monkeypatch.setattr(ai_module, "OpenAI", lambda **kwargs: OpenAI(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))))
    result = AIClient(settings).extract("Coffee under $20", None, datetime.now())
    assert result == output


def test_dotenv_precedence_and_secret_repr(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "dotenv_values", lambda path: {
        "GROQ_API_KEY": "file-secret", "GROQ_MODEL": "file-model"})
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_MODEL", "environment-model")
    settings = Settings.from_env()
    assert settings.groq_api_key == "file-secret"
    assert settings.groq_model == "environment-model"
    assert "file-secret" not in repr(settings)


@pytest.mark.parametrize("message,finish_reason", [
    ({"content": None, "refusal": "Cannot help"}, "stop"),
    ({"content": "not json"}, "stop"),
    ({"content": '{"kind":"unsupported"}'}, "stop"),
    ({"content": "{"}, "length"),
])
def test_unusable_provider_output(monkeypatch, message, finish_reason):
    settings = replace(Settings.from_env(), groq_api_key="test-key")

    def respond(request):
        return httpx.Response(200, json={
            "id": "chat_test", "object": "chat.completion", "created": 0,
            "model": settings.groq_model,
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": {"role": "assistant", **message}}],
        })

    monkeypatch.setattr(ai_module, "OpenAI", lambda **kwargs: OpenAI(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))))
    ai = AIClient(settings)
    with pytest.raises(APIError) as failure:
        ai.extract("Coffee", None, datetime.now())
    assert failure.value.code == "llm_unavailable"
    assert ai.explain({}, "Computed fallback") == "Computed fallback"
