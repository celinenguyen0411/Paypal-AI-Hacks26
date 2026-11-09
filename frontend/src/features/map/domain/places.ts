import type { FeatureCollection, Point } from "geojson";
import type { Category, CheckinReason, Place } from "./types";

export const CATEGORY_LABELS: Record<Category, string> = {
  lunch: "Food",
  coffee: "Coffee",
  groceries: "Groceries",
  free: "Free",
};

export const CHECKIN_MESSAGES: Record<CheckinReason, string> = {
  too_far: "You're not close enough. Get within 75 m and try again.",
  low_accuracy: "Your GPS signal is too weak to confirm you're here.",
  already_today: "You've already checked in here today.",
  daily_cap: "You've reached today's check-in XP limit.",
  closed_hours: "Check-ins are open from 7am to 9pm.",
  paid_stop_uses_paypal: "This place isn't part of a live quest, so there's nothing to check in to.",
  simulation_not_allowed: "Pretend mode only works in the demo.",
};

export function canCheckIn(place: Place): boolean {
  return place.category === "free" || place.community_quest_ids.length > 0;
}

export function placesToFeatures(
  places: Place[],
): FeatureCollection<Point, { place_id: string; kind: string }> {
  return {
    type: "FeatureCollection",
    features: places.map((place) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [place.location.lng, place.location.lat] },
      properties: { place_id: place.place_id, kind: pinKind(place) },
    })),
  };
}

function pinKind(place: Place): string {
  if (place.category === "free") return "free";
  return place.partner ? "partner" : "other";
}
