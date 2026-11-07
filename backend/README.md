# Quest API

Shared FastAPI backend for Quest's map and ask/planning features.
Map, `/ask`, and plan confirmation endpoints are implemented. Python 3.11+ is required.
Map features run without external services. `/ask` requires your own Groq API key.

## Run

From the repository root:

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json
- Base URL: `http://localhost:8000`
- Health and loaded-place counts: http://localhost:8000/health

Run commands from `backend/`. From the repository root, the equivalent server command is:

```sh
backend/.venv/bin/uvicorn main:app --app-dir backend --reload
```

## Enable the AI ask bar

From `backend/`, copy the template, then edit `.env` locally:

```sh
cp example.env .env
```

Set `GROQ_API_KEY` in `.env` and restart the server. The backend reads this file
automatically; process environment variables take precedence. `.env` is ignored by Git.
Keep the key in the backend; the frontend calls `/ask` without receiving the key.
The default `GROQ_MODEL` is `openai/gpt-oss-20b`; select another Structured Outputs-capable
model supported by Groq if needed. The OpenAI SDK connects to Groq, not OpenAI.
Create a key at [Groq Console](https://console.groq.com/keys) and use the Free plan
for no API charges within its [quotas](https://console.groq.com/docs/rate-limits).
A normal route request uses two model calls. Do not overwrite an existing `.env` when updating.

See [Ask API setup and examples](docs/ask.md) for requests, follow-ups, confirmation,
demo balance behavior, limitations, and troubleshooting.

## Code layout

```text
backend/
├── main.py                 # Uvicorn entry point; exposes app and create_app
├── data/
│   ├── README.md           # Dataset sources and intended preparation
│   └── raw/                # Unchanged place dataset snapshots
├── app/
│   ├── application.py      # App factory, lifecycle, CORS, and error handlers
│   ├── ai.py               # Groq structured intent extraction and plan narration
│   ├── ask_routes.py       # Ask and plan confirmation endpoints
│   ├── ask_schemas.py      # Intent, plan, and ask response contracts
│   ├── planning.py         # Catalog selection, estimated routes, budgets, follow-ups
│   ├── config.py           # Environment settings and timezone
│   ├── catalog.py          # Local JSON loading, category mapping, and filtering
│   ├── routes.py           # Map and merchant APIRouters; HTTP inputs/outputs
│   ├── schemas.py          # Pydantic request and response contracts
│   ├── services.py         # Place filtering, check-in rules, quest validation
│   ├── database.py         # SQLite schema, queries, and persistence
│   ├── geometry.py         # Distance and fallback walking-zone calculations
│   ├── errors.py           # Domain error type
│   └── seed.py             # Fictional campus fixtures
├── tests/
│   ├── test_api.py         # API and persistence regression tests
│   ├── test_ask.py         # Planning, conversation, confirmation, and mocked AI tests
│   └── test_catalog.py     # Snapshot normalization and startup integration tests
├── pytest.ini
├── example.env             # Copy to .env and add a backend-only Groq key
├── docs/ask.md             # Ask integration guide
└── requirements.txt
```

Routes delegate to `MapService`, which uses `Database` for persistence. The app factory
creates one configured service per application and exposes it through a FastAPI dependency.
Change response contracts in `schemas.py`, domain rules in `services.py`, and SQL in `database.py`.

At startup, the app reads [`data/raw/entities.json`](data/raw/entities.json), validates
records, maps supported food/shopping categories, filters to Madison, and caches the catalog
in memory. It retains the six fictional demo places in `app/seed.py` for partner deals
and free-stop quest/check-in flows. Restart the app to reload a changed dataset.
See the [dataset guide](data/README.md) for source details and filtering rules.

The existing `uvicorn main:app` command and all API paths remain unchanged.
For a larger backend, use `app.application.create_app` as the app factory, or include
`map_router` and `merchant_router` from `app.routes`. When including routers directly,
the host app must load `MapService.catalog`, initialize the database, provide `app.state.map_service`, and register
the error handlers shown in `application.py`.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Server status and counts of loaded snapshot/demo places |
| POST | `/ask` | Extract intent and return a plan, affordability answer, or clarification |
| POST | `/ask/plans/{plan_id}/confirm` | Save confirmation and award planning XP once daily |
| GET | `/map/places` | Local snapshot and demo places within an estimated walking radius, deals, and GeoJSON boundary |
| POST | `/map/checkin` | Validate free-place check-ins, award XP, and return quest progress |
| GET | `/map/community-quests` | Active quests containing the query point or within approximately 2 km |
| POST | `/merchant/community-quests` | Validate and persist a polygon-based quest |

`GET` endpoints accept `lat` and `lng`, defaulting to campus: `43.0761, -89.3999`.
Places also accepts `walk_min=5|10|15` (default `10`) and comma-separated
`categories=coffee,lunch,groceries,free` (default all four).

Money uses integer cents. Distances use meters, durations use seconds, and
GeoJSON coordinates use `[lng, lat]`. The explicitly named `walk_min` query uses minutes.
All successful responses and application/validation errors include `demo`.
Map list responses include `source: "fallback_seeded"`; show the UI's live-places-unavailable notice.
This source value also covers the offline snapshot; it does not imply the listings are live.
Each place includes `cost_source: "category_table"`; prices are estimates, not menu quotes.
Show source attribution from `attributions` and each place's `attribution`.

## Frontend examples

```js
const base = "http://localhost:8000";
const headers = { "Content-Type": "application/json", "X-User-Id": "linh" };

const placesResponse = await fetch(
  `${base}/map/places?lat=43.0761&lng=-89.3999&walk_min=10&categories=coffee,free`
);
const radar = await placesResponse.json();
// Render radar.places and radar.isochrone_geojson.

const checkinResponse = await fetch(`${base}/map/checkin`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    place_id: "m_librarymall",
    location: { lat: 43.0753, lng: -89.3965 },
    accuracy_m: 18,
    simulated: false,
  }),
});
const checkin = await checkinResponse.json();
// HTTP 200 with ok:false means a rejected check-in; show checkin.reason.
// Non-2xx responses have { error, message, demo }; show message.

const quests = await fetch(`${base}/map/community-quests`, { headers })
  .then(response => response.json());
```

Use the same `X-User-Id` for check-ins and quest reads. Omitting it selects
`demo-user`. Separate IDs keep progress separate. Place IDs beginning `m_` are
local seeded fixtures; inspect `partner` to determine whether a place is a partner.
Imported places have stable `fsq:<source_id>` IDs, `attribution: "foursquare"`, and
`partner: false`. They are not Google places and do not use the `g:` prefix.

Quick manual checks:

```sh
curl http://localhost:8000/health

curl 'http://localhost:8000/map/places?walk_min=10&categories=free'

curl -X POST http://localhost:8000/map/checkin \
  -H 'Content-Type: application/json' -H 'X-User-Id: linh' \
  -d '{"place_id":"m_librarymall","location":{"lat":43.0753,"lng":-89.3965},"accuracy_m":18,"simulated":false}'

curl -X POST http://localhost:8000/merchant/community-quests \
  -H 'Content-Type: application/json' -H 'X-Merchant-Id: m_mamalin' \
  -d '{"title":"Explore campus","zone_geojson":{"type":"Polygon","coordinates":[[[-89.402,43.072],[-89.388,43.072],[-89.388,43.079],[-89.402,43.079],[-89.402,43.072]]]},"place_ids":["m_librarymall","m_lakeshore"],"needed_visits":2,"ends_at":"2026-11-09T23:59:00-06:00"}'
```

## Demo behavior and rules

- Demo mode defaults to enabled. `demo` contains
  `{ "frozen_at": "2026-11-04T12:30:00-06:00", "location": { "lat": 43.0761, "lng": -89.3999 } }`.
  The UI can pin its location from this metadata. Explicit query/body coordinates still apply,
  so GPS validation remains testable.
- `simulated: true` bypasses distance and accuracy checks only in demo mode.
  Returned `distance_m` still describes the supplied coordinates.
- A valid free-stop check-in requires distance at most 75 m and reported accuracy at most 50 m.
  Each free place awards 20 XP, once per user per Chicago calendar day, up to 100 check-in XP/day.
  League XP mirrors awarded check-in XP. Repeated/concurrent requests cannot award duplicate XP.
- Both seeded free places are treated as open 24 hours. Paid places return
  `paid_stop_uses_paypal`; no payment flow is implemented.
- Quest progress counts distinct participating places visited during the quest's active period.
  Visit both `m_librarymall` and `m_lakeshore` to complete the seeded quest without purchases.
  Quest badges and the 40 XP reward are preview metadata; completion reward issuance is deferred.
- Merchant creation accepts one closed polygon ring, without holes or self-intersections,
  with area at most 2 km². All selected places must exist and lie inside/on the zone.
  At least two distinct places are required; `needed_visits` must be between two and their count.
  `ends_at` must include a timezone and be in the next 14 days.
  `purchase_required` is always false; supplying it in a creation request is rejected.
- `places_in_zone` counts all catalog places inside the polygon, including unselected places.
  There is no participation consent workflow in this scaffold.
- Validation errors return HTTP 422 with `{ "error": "code", "message": "...", "demo": ... }`.
  Unknown check-in places return HTTP 404. Semantic check-in rejections return HTTP 200,
  `ok: false`, zero XP, and a `reason` from the contract.

## Configuration and persistence

Set environment variables before starting Uvicorn:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAP_DB_PATH` | `backend/map.sqlite3` (absolute path resolved beside `main.py`) | SQLite file; its parent directory must exist |
| `MAP_DEMO_MODE` | `true` | Set `false` for real Chicago time, `demo: null`, and disabled simulation |
| `MAP_CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated exact frontend origins |
| `MAP_PLACES_PATH` | `backend/data/raw/entities.json` (resolved beside `main.py`) | Normalized Foursquare JSON array loaded at startup; override paths are relative to the working directory |
| `GROQ_API_KEY` | Empty | Required for `/ask`; map endpoints still work without it |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Structured Outputs-capable model for extraction and narration |
| `GROQ_TIMEOUT_S` | `20` | Timeout per model request, up to 120 seconds; automatic retries disabled |
| `DEMO_SAFE_TO_SPEND_CENTS` | `6400` | Fictional balance used only in demo mode |

For example:

```sh
MAP_CORS_ORIGINS=http://localhost:8080 uvicorn main:app --reload
```

SQLite stores visits and created quests across restarts. Seeded places remain in `app/seed.py`.
Missing, malformed, or non-array place datasets fail startup. Invalid individual rows are skipped
and logged; inspect `/health` for loaded counts. An empty array loads only demo fixtures.
The default quest is inserted once with the current/demo week's window. It is not refreshed
after expiration. For a fresh local demo, stop the server and use a new `MAP_DB_PATH`.
Use separate database files when switching clock modes. Frozen demo time means daily limits
do not reset between restarts.

## Limits and next integration steps

This is a local integration scaffold. `X-User-Id` and `X-Merchant-Id` are spoofable development
identities, not authentication. Demo mode treats every caller as a judge account. Add verified
user/merchant roles and per-account judge authorization before shared deployment.

Imported listings come from an offline Foursquare snapshot, not a live feed. Imported prices
are fixed category estimates: coffee 500 cents, lunch 1400 cents, groceries 1200 cents.
Price tiers are not converted to exact costs. Demo listings, offers, and opening assumptions
remain fictional fixtures. Walking times use
great-circle distance / 1.3 m/s. The boundary is a circular estimate, not a routed isochrone;
polygon area uses a campus-scale local projection. No Google Places, routing provider,
payments, XP account balances, rate limiting, or production authorization is implemented.
The deal's `live_now` is its time-window status, not verified first-visit eligibility.
Imported opening schedules are not evaluated; the API does not promise a place is open now.
Ask uses the same catalog and SQLite database. Its walking routes are straight-line estimates,
not street navigation. See [Ask API limitations](docs/ask.md#initial-version-limits).

## Tests

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

Tests use isolated temporary SQLite databases. They cover filters, GeoJSON closure,
validation, check-in eligibility, duplicate/concurrent XP, daily caps, simulation permissions,
quest completion, persistence, polygon constraints, CORS, generated OpenAPI schemas,
catalog filtering/deduplication, startup failures, cached loading, real-snapshot integration,
ask intent validation, route totals/deadlines, follow-ups, ownership, concurrent confirmation,
and mocked Groq responses. Tests do not call the live Groq API or spend credits.
