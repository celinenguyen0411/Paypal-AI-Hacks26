import { describe, expect, it } from "vitest";
import { boundsOf, formatClock, minutesLabel } from "./route";

describe("minutesLabel", () => {
  it("keeps one decimal under ten minutes", () => expect(minutesLabel(223)).toBe("3.7 min"));
  it("rounds long walks", () => expect(minutesLabel(1500)).toBe("25 min"));
});

describe("formatClock", () => {
  it("reads the time in Madison", () => expect(formatClock("2026-11-04T12:32:00-06:00")).toBe("12:32 PM"));
  it("converts other offsets to Madison", () => expect(formatClock("2026-11-04T20:00:00+00:00")).toBe("2:00 PM"));
});

describe("boundsOf", () => {
  it("wraps every coordinate", () => {
    expect(boundsOf([[-89.4, 43.07], [-89.39, 43.08], [-89.41, 43.075]]))
      .toEqual([[-89.41, 43.07], [-89.39, 43.08]]);
  });
});
