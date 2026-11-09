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
