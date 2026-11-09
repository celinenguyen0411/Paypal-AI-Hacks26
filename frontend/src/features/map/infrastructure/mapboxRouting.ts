import type { Feature, FeatureCollection, LineString, Polygon } from "geojson";
import type { LatLng, WalkMinutes } from "../domain/types";
import type { Coordinate } from "../domain/route";

export const MAPBOX_TOKEN: string = import.meta.env.VITE_MAPBOX_TOKEN ?? "";
const MAPBOX_API = "https://api.mapbox.com";

async function getJson<T>(url: string): Promise<T | null> {
  if (!MAPBOX_TOKEN) return null;
  try {
    const response = await fetch(`${url}&access_token=${MAPBOX_TOKEN}`);
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}

interface DirectionsResponse {
  routes: { geometry: LineString }[];
}

export async function fetchWalkingLine(coordinates: Coordinate[]): Promise<Feature<LineString> | null> {
  const path = coordinates.map(([lng, lat]) => `${lng},${lat}`).join(";");
  const data = await getJson<DirectionsResponse>(
    `${MAPBOX_API}/directions/v5/mapbox/walking/${path}?geometries=geojson&overview=full`,
  );
  const geometry = data?.routes[0]?.geometry;
  return geometry ? { type: "Feature", properties: {}, geometry } : null;
}

export async function fetchWalkZone(
  center: LatLng,
  minutes: WalkMinutes,
): Promise<FeatureCollection<Polygon> | null> {
  return getJson<FeatureCollection<Polygon>>(
    `${MAPBOX_API}/isochrone/v1/mapbox/walking/${center.lng},${center.lat}?contours_minutes=${minutes}&polygons=true`,
  );
}
