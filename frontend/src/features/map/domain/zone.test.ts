import { describe, expect, it } from "vitest";
import type { Polygon } from "geojson";
import { endDateRange, endOfDay, placesInside, zoneAreaKm2, zoneChecks } from "./zone";

const campus: Polygon = {
  type: "Polygon",
  coordinates: [[[-89.402, 43.072], [-89.388, 43.072], [-89.388, 43.079], [-89.402, 43.079], [-89.402, 43.072]]],
};
const inside = { place_id: "in", location: { lat: 43.075, lng: -89.395 } };
const alsoInside = { place_id: "in2", location: { lat: 43.076, lng: -89.39 } };
const outside = { place_id: "out", location: { lat: 43.09, lng: -89.395 } };

describe("zone", () => {
  it("measures the seeded campus zone", () => expect(zoneAreaKm2(campus)).toBeCloseTo(0.885, 1));
  it("finds only places inside", () => {
    expect(placesInside(campus, [inside, outside]).map((p) => p.place_id)).toEqual(["in"]);
  });
  it("passes a walkable zone with two places", () => {
    expect(zoneChecks(campus, [inside, alsoInside]).every((c) => c.ok)).toBe(true);
  });
  it("fails a zone with one place", () => {
    expect(zoneChecks(campus, [inside]).map((c) => c.ok)).toEqual([true, false]);
  });
  it("fails a zone over 2 square kilometres", () => {
    const huge: Polygon = {
      type: "Polygon",
      coordinates: [[[-89.5, 43.0], [-89.3, 43.0], [-89.3, 43.1], [-89.5, 43.1], [-89.5, 43.0]]],
    };
    expect(zoneChecks(huge, [inside, alsoInside]).map((c) => c.ok)).toEqual([false, true]);
  });
});

describe("quest end dates", () => {
  const frozen = "2026-11-04T12:30:00-06:00";
  it("offers tomorrow through thirteen days out", () => {
    expect(endDateRange(frozen)).toEqual({ min: "2026-11-05", max: "2026-11-17", suggested: "2026-11-11" });
  });
  it("crosses a month end", () => {
    expect(endDateRange("2026-11-25T09:00:00-06:00").max).toBe("2026-12-08");
  });
  it("ends the chosen day in the same offset as the clock", () => {
    expect(endOfDay("2026-11-11", frozen)).toBe("2026-11-11T23:59:00-06:00");
  });
});
