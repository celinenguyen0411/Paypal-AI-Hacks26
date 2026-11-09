# Place datasets

`raw/` holds unchanged copies of the supplied Madison place datasets. Keep these
files as source snapshots; put any future cleaned API-ready dataset in `processed/`.
The API loads `raw/entities.json` once at startup and combines eligible records with
the seven demo fixtures from `app/seed.py`. The other two files remain source snapshots
for future enrichment; they are not loaded into the running API.

| File | Records | Contents | Intended role |
| --- | ---: | --- | --- |
| `raw/entities.json` | 1,708 | Normalized Foursquare places, categories, coordinates, and price tiers | Primary input for the places catalog |
| `raw/foursquare_places.json` | 1,709 | Detailed Foursquare records with weekly hours and optional photos/ratings | Enrich normalized places by matching `source_id` to `fsq_place_id` |
| `raw/amenities.json` | 1,104 | OpenStreetMap amenities with coordinates and tags | Supplement the catalog after deduplication |

The files were copied from the user-provided `banhmi-cheesehacks` project.
Original filenames and contents are preserved. Counts describe these snapshots,
not current live availability. Source collection methods and licensing metadata
were not supplied with this copy.

## Current import rules

- Validate source/type, IDs, names, finite coordinates, and category lists.
- Include only Madison records within latitude `43.02–43.15`, longitude `-89.55–-89.30`.
- Exclude private-place categories and unsupported categories. Blank names/IDs are skipped.
- Map grocery stores, supermarkets, convenience stores, and farmers markets to `groceries`.
- Map coffee shops, cafés, and tea rooms to `coffee`; these take precedence over restaurant categories.
- Map restaurant categories and selected food venues (pizzerias, sandwich spots, burger joints,
  taco places, delis, food courts) to `lunch`.
- Use stable `fsq:<source_id>` IDs; deduplicate by that ID. Normalize `lon` to `lng`.
- Use fixed estimated costs: coffee 500 cents, lunch 1400 cents, groceries 1200 cents.
  These do not represent verified menu prices and do not depend on `price_tier`.
- Imported places have no partner status, deals, sponsorship, or check-in XP.
  Only the curated demo fixtures provide free stops and partner flows.
- Return `attribution: "foursquare"` and `cost_source: "category_table"` for imported places.
  Top-level `source` remains `fallback_seeded` because the data and walking estimates are offline.

`GET /health` reports the total, snapshot, and demo place counts. `MAP_PLACES_PATH`
can point to another normalized Foursquare JSON array. Restart after changing it.
Missing/broken files fail startup; invalid individual records are skipped and logged.

## Future enrichment

- Join the two Foursquare datasets instead of appending both as separate places.
- Curate additional free stops and deduplicate overlapping OSM/Foursquare places.
- Preserve weekly hours from the detailed snapshot before implementing open-now filtering.
- Keep demo deals, merchant partnerships, and XP rules separate from source listings.

Point GeoJSON can be generated from the coordinates. These files do not contain
walking routes or isochrone polygons.
