# Quest Map

The map part of Quest: route planning, the Rewards Radar, check-ins, and Community Quests.
Built with Vite, React, TypeScript, and react-map-gl on Mapbox GL.

## Run

Start the backend first (see `backend/README.md`). Then, from `frontend/`:

```sh
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:5173. The backend already allows this origin.

## Settings

Set these in `.env.local`, which git ignores.

| Variable | Purpose |
| --- | --- |
| `VITE_MAPBOX_TOKEN` | Mapbox **public** token (starts with `pk.`). Without it the map area shows a setup message; the panels still work. |
| `VITE_API_BASE` | Backend URL. Defaults to `http://localhost:8000`. |

## Code layout

```text
src/features/map/
├── domain/          # Money, route, zone and identity rules; no React or network
├── infrastructure/  # Quest API and Mapbox calls
├── application/     # React hooks that connect the rules to the API
└── ui/              # Panels and map layers
```

`MapExperience` is the single entry point, exported from `src/features/map`, so the map can be
dropped into the full Quest app.

## Tests

```sh
npm test
npm run build
```

## Limits

- `Pay through Quest` is a label. No payment is taken.
- If Mapbox routing fails, the route falls back to the backend's straight-line estimate.
- Places come from a saved Foursquare snapshot, so listings are not live and `~` prices are estimates.
