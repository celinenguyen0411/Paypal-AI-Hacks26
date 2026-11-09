import { useEffect, useState } from "react";
import type { Feature, LineString } from "geojson";
import type { Plan } from "../domain/types";
import type { Coordinate } from "../domain/route";
import { fetchWalkingLine } from "../infrastructure/mapboxRouting";

export interface WalkingLine {
  line: Feature<LineString>;
  followsStreets: boolean;
}

export function useWalkingLine(plan: Plan | null): WalkingLine | null {
  const [streetLine, setStreetLine] = useState<{ planId: string; line: Feature<LineString> } | null>(null);
  const planId = plan?.plan_id;

  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    const coordinates = plan.route_geojson.geometry.coordinates as Coordinate[];
    fetchWalkingLine(coordinates).then((line) => {
      if (!cancelled && line) setStreetLine({ planId: plan.plan_id, line });
    });
    return () => {
      cancelled = true;
    };
  }, [plan, planId]);

  if (!plan) return null;
  return streetLine?.planId === plan.plan_id
    ? { line: streetLine.line, followsStreets: true }
    : { line: plan.route_geojson, followsStreets: false };
}
