from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class Demo(BaseModel):
    frozen_at: datetime
    location: Location


class Envelope(BaseModel):
    demo: Demo | None


class Error(Envelope):
    error: str
    message: str


class HealthResponse(Envelope):
    status: Literal["ok"]
    source: Literal["fallback_seeded"]
    places_loaded: int
    snapshot_places_loaded: int
    demo_places_loaded: int


class Polygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]


class Deal(BaseModel):
    id: str
    pct: int | None = None
    flat_cents: int | None = None
    when: str
    cap_cents: int
    live_now: bool


class Place(BaseModel):
    place_id: str
    name: str
    category: Literal["coffee", "lunch", "groceries", "free"]
    location: Location
    partner: bool
    sponsored: bool
    deal: Deal | None
    est_cost_cents: int
    cost_source: Literal["merchant", "category_table", "user"] = "category_table"
    checkin_xp: int
    walk_s: int
    community_quest_ids: list[str]
    attribution: str | None


class PlacesResponse(Envelope):
    source: Literal["fallback_seeded"] = "fallback_seeded"
    isochrone_geojson: dict
    places: list[Place]
    attributions: list[str]


class CheckinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    place_id: str
    location: Location
    accuracy_m: float = Field(ge=0, allow_inf_nan=False)
    simulated: bool = False


class Progress(BaseModel):
    quest_id: str
    visited: int
    needed: int
    completed: bool


class CheckinResponse(Envelope):
    ok: bool
    distance_m: int
    xp_awarded: int
    league_xp_awarded: int
    reason: Literal["too_far", "low_accuracy", "already_today", "daily_cap",
                    "closed_hours", "paid_stop_uses_paypal", "simulation_not_allowed"] | None
    community_progress: list[Progress]


class Quest(BaseModel):
    id: str
    title: str
    sponsor: dict[str, str]
    zone_geojson: Polygon
    place_ids: list[str]
    needed_visits: int
    purchase_required: Literal[False] = False
    ends_at: datetime
    reward: dict[str, str | int]
    progress: dict[str, int]


class QuestsResponse(Envelope):
    source: Literal["fallback_seeded"] = "fallback_seeded"
    quests: list[Quest]


class CreateQuestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    zone_geojson: Polygon
    place_ids: list[str] = Field(min_length=2, max_length=50)
    needed_visits: int = Field(ge=2)
    ends_at: datetime


class CreateQuestResponse(Envelope):
    id: str
    status: Literal["live"] = "live"
    places_in_zone: int
