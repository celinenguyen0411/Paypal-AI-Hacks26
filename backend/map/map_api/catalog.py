"""Load the normalized local snapshot without adding live provider dependencies."""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .schemas import Location
from .seed import PLACES

logger = logging.getLogger(__name__)
MADISON_BOUNDS = (43.02, -89.55, 43.15, -89.30)
CATEGORY_COST_CENTS = {"coffee": 500, "lunch": 1400, "groceries": 1200}


class SourcePlace(BaseModel):
    entity_type: Literal["place"]
    source: Literal["foursquare"]
    source_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    categories: list[str]


def category_for(categories):
    """Allow only supported shopping/food categories; free stops require curation."""
    names = {name.strip().casefold() for name in categories}
    if any("private" in name for name in names):
        return None
    if names & {"grocery store", "supermarket", "convenience store", "farmers market"}:
        return "groceries"
    if names & {"coffee shop", "café", "cafe", "tea room"}:
        return "coffee"
    if any("restaurant" in name or name in {
        "pizzeria", "sandwich spot", "burger joint", "taco place", "deli", "food court",
    } for name in names):
        return "lunch"
    return None


def load_places(path: Path):
    """Return demo fixtures plus eligible snapshot places, deduplicated by source ID.

    Invalid rows are skipped. Missing, malformed, or non-array files fail startup
    so the frontend never silently receives a fixture-only catalog.
    """
    with Path(path).open(encoding="utf-8") as source:
        rows = json.load(source)
    if not isinstance(rows, list):
        raise ValueError(f"Place dataset must contain a JSON array: {path}")

    places = list(PLACES)
    seen = {place["place_id"] for place in places}
    invalid = 0
    min_lat, min_lng, max_lat, max_lng = MADISON_BOUNDS
    for row in rows:
        try:
            record = SourcePlace.model_validate(row)
        except ValidationError:
            invalid += 1
            continue
        category = category_for(record.categories)
        place_id = f"fsq:{record.source_id.strip()}"
        if (not category or not record.name.strip() or not record.source_id.strip()
                or place_id in seen
                or not (min_lat <= record.lat <= max_lat and min_lng <= record.lon <= max_lng)):
            continue
        seen.add(place_id)
        places.append(dict(
            place_id=place_id, name=record.name.strip(), category=category,
            location=Location(lat=record.lat, lng=record.lon).model_dump(),
            partner=False, sponsored=False, deal=None,
            est_cost_cents=CATEGORY_COST_CENTS[category], cost_source="category_table",
            checkin_xp=0, attribution="foursquare",
        ))
    logger.info("Loaded %d snapshot places and %d demo fixtures; skipped %d invalid rows",
                len(places) - len(PLACES), len(PLACES), invalid)
    return places
