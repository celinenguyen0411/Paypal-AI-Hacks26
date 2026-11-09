from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import Envelope, Location


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    location: Location | None = None
    conversation_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value):
        if not value.strip():
            raise ValueError("Message cannot be blank.")
        return value.strip()


class Need(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["lunch", "coffee", "groceries", "free"]
    amount_cents: int | None = Field(default=None, ge=0, le=1_000_000)


class ExtractedIntent(BaseModel):
    """Model output is untrusted input; bounds are checked again before planning."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["route_plan", "answer", "clarify"]
    budget_cents: int | None = Field(default=None, ge=0, le=1_000_000)
    needs: list[Need] = Field(default_factory=list, max_length=4)
    diet: list[str] = Field(default_factory=list, max_length=10)
    party_size: int = Field(default=1, ge=1, le=8)
    max_walk_min: int = Field(default=15, ge=1, le=30)
    deadline: datetime | None = None
    clarification: str | None = Field(default=None, max_length=500)
    exclude_place_ids: list[str] = Field(default_factory=list, max_length=50)


class Start(Location):
    label: str = "Starting point"


class Intent(BaseModel):
    budget_cents: int | None
    needs: list[Need]
    diet: list[str]
    party_size: int
    max_walk_min: int
    deadline: datetime | None
    start: Start


class BudgetCheck(BaseModel):
    safe_to_spend_cents: int
    plan_cents: int
    ok: bool
    bills_covered: list[str]
    as_of: datetime
    source: Literal["demo"] = "demo"


class Stop(BaseModel):
    order: int
    place_id: str
    name: str
    category: str
    location: Location
    partner: bool
    sponsored: bool
    est_cost_cents: int
    cost_source: Literal["merchant", "category_table", "user"]
    cashback_cents: int = 0
    deal_id: str | None = None
    pay_via: Literal["quest", "as_usual"] = "as_usual"
    checkin_xp: int
    arrive_at: datetime
    wait_s: int = 0
    dwell_s: int
    deal_live_at_arrival: bool = False
    cashback_to_goal: bool = False
    cashback_clears_at: datetime | None = None
    why: list[str]
    attribution: str | None


class Leg(BaseModel):
    from_: str | int = Field(alias="from")
    to: str | int
    distance_m: int
    duration_s: int


class Totals(BaseModel):
    cost_cents: int
    cashback_cents: int = 0
    net_cents: int
    budget_left_cents: int
    over_budget: bool
    distance_m: int
    duration_s: int
    return_at: datetime


class XPPreview(BaseModel):
    quest: str
    xp: int
    checkable: bool
    when: str
    verify: str | None = None


class SwapOffer(BaseModel):
    replace_order: int
    with_place_id: str
    name: str
    partner: bool
    sponsored: bool
    est_cost_cents: int
    cashback_cents: int
    pay_less_today_cents: int
    saves_after_cashback_cents: int
    extra_walk_s: int
    fixes_over_budget: bool


class HiddenPlace(BaseModel):
    place_id: str
    name: str
    reason: Literal["deal_not_today", "deal_window_misses_deadline", "too_far"]
    label: str


class Plan(BaseModel):
    plan_id: str
    source: Literal["fallback_seeded"] = "fallback_seeded"
    profile: Literal["walking"] = "walking"
    stops: list[Stop]
    legs: list[Leg]
    route_geojson: dict
    totals: Totals
    xp_preview: list[XPPreview]
    swaps: list[SwapOffer] = Field(default_factory=list)
    hidden: list[HiddenPlace] = Field(default_factory=list)
    ranking: str


class AskResponse(Envelope):
    kind: Literal["route_plan", "answer", "clarify"]
    conversation_id: str
    reply: str
    intent: Intent
    budget_check: BudgetCheck | None
    plan: Plan | None


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    swaps_applied: list[int] = Field(default_factory=list)


class ConfirmResponse(Envelope):
    plan: Plan
    xp_awarded: int
    league_xp_awarded: int


class SwapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    replace_order: int = Field(ge=1)
    with_place_id: str = Field(min_length=1)


class SwapResponse(Envelope):
    plan: Plan
    budget_check: BudgetCheck | None


class PlanReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(min_length=1, max_length=1200)
