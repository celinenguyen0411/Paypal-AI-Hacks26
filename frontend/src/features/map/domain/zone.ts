import area from "@turf/area";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import type { Polygon } from "geojson";

export const MAX_ZONE_KM2 = 2;
export const MIN_ZONE_PLACES = 2;

interface Located {
  location: { lat: number; lng: number };
}

export interface ZoneCheck {
  ok: boolean;
  text: string;
}

export function zoneAreaKm2(zone: Polygon): number {
  return area(zone) / 1_000_000;
}

export function placesInside<T extends Located>(zone: Polygon, places: T[]): T[] {
  return places.filter(({ location }) =>
    booleanPointInPolygon([location.lng, location.lat], zone),
  );
}

export function zoneChecks(zone: Polygon, participating: Located[]): ZoneCheck[] {
  const km2 = zoneAreaKm2(zone);
  return [
    { ok: km2 <= MAX_ZONE_KM2, text: `Under ${MAX_ZONE_KM2} km² (now ${km2.toFixed(2)} km²)` },
    {
      ok: participating.length >= MIN_ZONE_PLACES,
      text: `At least ${MIN_ZONE_PLACES} places taking part (now ${participating.length})`,
    },
  ];
}

const MAX_END_DAYS = 13;
const SUGGESTED_END_DAYS = 7;
const DAY_MS = 86_400_000;

function addDays(day: string, days: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

export function endDateRange(clockIso: string) {
  const today = clockIso.slice(0, 10);
  return {
    min: addDays(today, 1),
    max: addDays(today, MAX_END_DAYS),
    suggested: addDays(today, SUGGESTED_END_DAYS),
  };
}

export function endOfDay(day: string, clockIso: string): string {
  return `${day}T23:59:00${clockIso.slice(-6)}`;
}
