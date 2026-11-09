# Ask API

`POST /ask` uses the OpenAI SDK against Groq’s Chat Completions API. It extracts a typed intent, computes a plan
from the local catalog in Python, then asks the model to explain that computed plan.
The implementation follows the [official Structured Outputs documentation](https://console.groq.com/docs/structured-outputs).
No LangChain, vector database, or external routing service is required.

## Supply your key

From `backend/`:

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
cp example.env .env
```

Skip the copy if `.env` already exists. Edit `backend/.env` in your editor:

```dotenv
GROQ_API_KEY=your_own_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT_S=20
MAP_DEMO_MODE=true
DEMO_SAFE_TO_SPEND_CENTS=6400
```

Create a key in [Groq Console](https://console.groq.com/keys). Use the Free plan for
no API charges within its quotas; enabling a paid plan changes billing. The default
`openai/gpt-oss-20b` supports strict JSON schemas. See the
[rate limits](https://console.groq.com/docs/rate-limits) and your account’s limits page.
When migrating an existing `.env`, replace `OPENAI_API_KEY`, `OPENAI_MODEL`, and
`OPENAI_TIMEOUT_S` with the `GROQ_` settings above; old settings are no longer read.
Keep the key server-side. `.env` and `.env.*` are ignored; `example.env` contains no key
and can be committed. No key is included in API responses or settings representations.

The application reads `backend/.env` regardless of the launch directory, without exporting
its values into the process environment. Existing environment variables override the file.
Restart after changing settings. Start the server:

```sh
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Without a key, map endpoints and `/health` still work. `/ask` returns HTTP 503,
`error: "llm_unavailable"`, so the frontend can show a configuration message.

## Create an outing

```sh
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -H 'X-User-Id: linh' \
  -d '{"message":"Lunch and coffee under $30 before 2pm today","location":{"lat":43.0761,"lng":-89.3999}}'
```

With demo mode enabled, the clock is frozen at `2026-11-04T12:30:00-06:00`.
"Today" and "2pm" resolve against that clock, not your computer's current date.

The response contains:

- `kind`: `route_plan`, `answer`, or `clarify`.
- `conversation_id`: save this for subsequent messages.
- `reply`: text for the chat UI.
- `intent`: validated budget, needs, diet, party size, walking limit, deadline, and start.
- `budget_check`: a fictional demo balance comparison, or `null` outside demo mode.
- `plan`: stops, legs, line GeoJSON, computed totals, and XP preview; otherwise `null`.
- `demo`: frozen clock/location metadata, or `null` outside demo mode.

Money is integer cents. Stops and timing use the existing catalog estimates.
`location: null` defaults to campus for a new conversation, or retains the previous
start for a follow-up. An explicit location changes the start. The API does not geocode
landmarks mentioned in messages.

For each need, the planner considers places with a known merchant price and uses estimated
snapshot prices only when no known-price place fits. It starts from the quickest route, takes
the cheapest pick after cashback within a 2-minute detour, keeps groceries last, may wait up to
10 minutes for a deal to open, and includes the walk back to the start. Cheaper places 2 to 5
minutes off the route come back in `plan.swaps`; partners left out for a deal or distance
reason come back in `plan.hidden`. The budget counts what you pay today, not cashback. `max_walk_min` limits total
round-trip walking time; `duration_s` also includes stop time: lunch 20 minutes, coffee
5 minutes, groceries 10 minutes, free stop 10 minutes. A deadline applies to returning
to the start. These conventions are specific to this initial planner.

If no plan meets walking/deadline constraints, the response is HTTP 422 `no_places_fit`.
If a plan exceeds the requested budget, it can still be returned with `over_budget: true`.
If it exceeds the fictional safe-to-spend balance, it is rejected with `over_safe_to_spend`.
Meal/coffee estimates scale with party size; explicit per-need amounts are total allocations,
not per-person amounts. Grocery estimates are per outing.

## Clarify, answer, and follow up

Missing budget or needs produce `kind: "clarify"` and `plan: null`. Submit the answer
with the returned conversation ID. Unsupported dietary guarantees or specific cuisines,
brands, and venues require clarification rather than an invented catalog match.

```sh
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' -H 'X-User-Id: linh' \
  -d '{"message":"Swap the coffee","conversation_id":"REPLACE_WITH_RETURNED_CONVERSATION_ID"}'
```

The model receives the previous validated intent and plan and returns a complete updated
intent. A swap excludes the previous stop from selection. Each new computed plan gets a
new `plan_id`; previously issued plans remain available for confirmation. Conversation
state and plans persist in SQLite across restarts. Use a fresh conversation ID by omitting
the field when starting an unrelated outing. Follow-ups depend on correct model extraction;
the planner validates the resulting values and recomputes the plan.

For a simple affordability answer:

```sh
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' -H 'X-User-Id: linh' \
  -d '{"message":"Can I afford a $20 purchase?"}'
```

In demo mode, this compares against the configured fictional balance. `bills_covered` is
empty because no bills or banking feed is connected. Outside demo mode, affordability
answers say that no account balance is connected and `budget_check` is `null`.

## Confirm a plan

```sh
curl -X POST http://localhost:8000/ask/plans/REPLACE_WITH_PLAN_ID/confirm \
  -H 'X-User-Id: linh'
```

Response: `{ "plan": {...}, "xp_awarded": 30, "league_xp_awarded": 30, "demo": {...} }`.
The first plan confirmation per user per Chicago calendar day awards 30 planning XP.
Retries, concurrent requests, and other plans confirmed that day award zero additional XP.
A previously confirmed plan cannot award XP on a later day. This award is separate from
the map check-in cap. The default frozen clock means the demo day does not advance.

Use the same `X-User-Id` for ask, follow-ups, and confirmation. Omitting it uses `demo-user`.
Cross-user conversation and plan lookups return HTTP 404. These headers remain spoofable
development identities; this is not production authentication.

The body is optional. `{ "swaps_applied": [] }` is accepted. Nonempty swap lists return
`swaps_not_supported`; apply swaps with the swap endpoint first.

## Apply a swap

```sh
curl -X POST http://localhost:8000/ask/plans/REPLACE_WITH_PLAN_ID/swap \n  -H 'Content-Type: application/json' -H 'X-User-Id: linh' \n  -d '{"replace_order":2,"with_place_id":"m_inkoat"}'
```

The response is `{ "plan": {...}, "budget_check": {...}, "demo": {...} }`. It makes no AI call and
returns a new `plan_id`; the earlier plan stays available so the UI can undo. Only swaps listed
in that plan's `swaps` are accepted.

## Errors and AI behavior

Errors use `{ "error": "code", "message": "...", "demo": ... }`.

| Status | Code | Meaning |
| --- | --- | --- |
| 422 | `invalid_request` | Blank/oversized message, invalid coordinates, or invalid body |
| 422 | `no_places_fit` | No candidate or round trip fits the requested constraints |
| 422 | `over_safe_to_spend` | Plan exceeds the fictional demo balance |
| 422 | `swaps_not_supported` | Swap list sent to confirm instead of the swap endpoint |
| 422 | `swap_not_offered` | The requested swap is not in that plan's `swaps` |
| 404 | `conversation_not_found` / `plan_not_found` | Missing record or different user |
| 429 | `rate_limited` | Groq quota/rate limit response |
| 503 | `llm_unavailable` | Missing/invalid key, timeout, provider error, refusal, or unusable extraction |

A route request normally makes two model calls: extraction and explanation. Each has the
configured timeout and no automatic retries. Answers/clarifications use one call. If the
explanation fails, the computed plan is returned with a deterministic summary. No extraction
fallback guesses the user's intent. The prompt and previous intent/plan are sent to Groq;
the entire catalog is not sent. Requests use stateless Chat Completions; conversation history is stored locally.

## Initial version limits

- No live banking, merchant payments, opening-hour checks, or verified dietary filtering.
- Route lines and travel times are estimates; they do not follow streets or account for barriers.
- Cashback comes from fictional seeded deals. `pay_via: "quest"` is a label; no payment is taken.
- Ranking is a bounded candidate search, not a guarantee of the global optimum. Sponsors get no ranking boost.
- Planning XP is persisted. End-of-day budget verification, reward issuance, and balances are deferred.
- User coordinates and conversational intent are user-provided; no landmark geocoder or destination lookup exists.

## Test

```sh
python -m pytest -q
```

Tests use isolated databases, fake intent extraction, and an HTTP mock for the actual OpenAI
SDK serializer/parser. They do not contact Groq or spend API credits. Live extraction quality
and your account's model/key access must be checked locally after supplying a real key.
