# Place datasets

`raw/` holds unchanged copies of the supplied Madison place datasets. Keep these
files as source snapshots; put any future cleaned API-ready dataset in `processed/`.
The API currently uses `map_api/seed.py`; it does not load these files yet.

| File | Records | Contents | Intended role |
| --- | ---: | --- | --- |
| `raw/entities.json` | 1,708 | Normalized Foursquare places, categories, coordinates, and price tiers | Primary input for the places catalog |
| `raw/foursquare_places.json` | 1,709 | Detailed Foursquare records with weekly hours and optional photos/ratings | Enrich normalized places by matching `source_id` to `fsq_place_id` |
| `raw/amenities.json` | 1,104 | OpenStreetMap amenities with coordinates and tags | Supplement the catalog after deduplication |

The files were copied from the user-provided `banhmi-cheesehacks` project.
Original filenames and contents are preserved. Counts describe these snapshots,
not current live availability. Source collection methods and licensing metadata
were not supplied with this copy.

Before loading the data into the API:

- Map source categories to `lunch`, `coffee`, `groceries`, and curated `free` stops.
- Normalize coordinates to `{lat, lng}` and retain source-specific IDs and provenance.
- Join the two Foursquare datasets instead of appending both as separate places.
- Filter unsuitable entries and deduplicate overlapping OSM/Foursquare places.
- Preserve weekly hours; treat costs as explicit estimates rather than converting price tiers directly into prices.
- Keep demo deals, merchant partnerships, and XP rules separate from source listings.

Point GeoJSON can be generated from the coordinates. These files do not contain
walking routes or isochrone polygons.
