import type { Feature, FeatureCollection, LineString, Polygon } from "geojson";

export type Category = "coffee" | "lunch" | "groceries" | "free";
export type WalkMinutes = 5 | 10 | 15;
export type CostSource = "merchant" | "category_table" | "user";

export interface LatLng {
  lat: number;
  lng: number;
}

export interface DemoInfo {
  frozen_at: string;
  location: LatLng;
}

export interface Deal {
  id: string;
  pct: number | null;
  flat_cents: number | null;
  when: string;
  cap_cents: number;
  live_now: boolean;
}

export interface Place {
  place_id: string;
  name: string;
  category: Category;
  location: LatLng;
  partner: boolean;
  sponsored: boolean;
  deal: Deal | null;
  est_cost_cents: number;
  cost_source: CostSource;
  checkin_xp: number;
  walk_s: number;
  community_quest_ids: string[];
  attribution: string | null;
}

export interface PlacesResponse {
  demo: DemoInfo | null;
  source: string;
  isochrone_geojson: FeatureCollection<Polygon>;
  places: Place[];
  attributions: string[];
}

export interface Stop {
  order: number;
  place_id: string;
  name: string;
  category: Category;
  location: LatLng;
  partner: boolean;
  sponsored: boolean;
  est_cost_cents: number;
  cost_source: CostSource;
  cashback_cents: number;
  deal_id: string | null;
  pay_via: "quest" | "as_usual";
  checkin_xp: number;
  arrive_at: string;
  wait_s: number;
  dwell_s: number;
  deal_live_at_arrival: boolean;
  cashback_to_goal: boolean;
  cashback_clears_at: string | null;
  why: string[];
  attribution: string | null;
}

export interface Leg {
  from: string | number;
  to: string | number;
  distance_m: number;
  duration_s: number;
}

export interface Totals {
  cost_cents: number;
  cashback_cents: number;
  net_cents: number;
  budget_left_cents: number;
  over_budget: boolean;
  distance_m: number;
  duration_s: number;
  return_at: string;
}

export interface SwapOffer {
  replace_order: number;
  with_place_id: string;
  name: string;
  partner: boolean;
  sponsored: boolean;
  est_cost_cents: number;
  cashback_cents: number;
  pay_less_today_cents: number;
  saves_after_cashback_cents: number;
  extra_walk_s: number;
  fixes_over_budget: boolean;
}

export interface HiddenPlace {
  place_id: string;
  name: string;
  reason: string;
  label: string;
}

export interface XpPreview {
  quest: string;
  xp: number;
  checkable: boolean;
  when: string;
}

export interface Plan {
  plan_id: string;
  source: string;
  stops: Stop[];
  legs: Leg[];
  route_geojson: Feature<LineString>;
  totals: Totals;
  xp_preview: XpPreview[];
  swaps: SwapOffer[];
  hidden: HiddenPlace[];
  ranking: string;
}

export interface BudgetCheck {
  safe_to_spend_cents: number;
  plan_cents: number;
  ok: boolean;
}

export interface Start extends LatLng {
  label: string;
}

export interface AskResponse {
  demo: DemoInfo | null;
  kind: "route_plan" | "answer" | "clarify";
  conversation_id: string;
  reply: string;
  intent: { start: Start; deadline: string | null };
  budget_check: BudgetCheck | null;
  plan: Plan | null;
}

export interface SwapResponse {
  demo: DemoInfo | null;
  plan: Plan;
  budget_check: BudgetCheck | null;
}

export interface ConfirmResponse {
  plan: Plan;
  xp_awarded: number;
  league_xp_awarded: number;
}

export interface QuestProgress {
  quest_id: string;
  visited: number;
  needed: number;
  completed: boolean;
}

export type CheckinReason =
  | "too_far"
  | "low_accuracy"
  | "already_today"
  | "daily_cap"
  | "closed_hours"
  | "paid_stop_uses_paypal"
  | "simulation_not_allowed";

export interface QuestReward {
  quest_id: string;
  badge: string;
  xp: number;
}

export interface CheckinResponse {
  ok: boolean;
  distance_m: number;
  xp_awarded: number;
  league_xp_awarded: number;
  reason: CheckinReason | null;
  community_progress: QuestProgress[];
  quest_rewards: QuestReward[];
}

export interface Quest {
  id: string;
  title: string;
  sponsor: { merchant_id: string; name: string };
  zone_geojson: Polygon;
  place_ids: string[];
  needed_visits: number;
  ends_at: string;
  reward: { badge: string; xp: number };
  progress: { visited: number; rewarded: number };
}

export interface QuestsResponse {
  demo: DemoInfo | null;
  quests: Quest[];
}

export interface NewQuest {
  title: string;
  zone_geojson: Polygon;
  place_ids: string[];
  needed_visits: number;
  ends_at: string;
}
