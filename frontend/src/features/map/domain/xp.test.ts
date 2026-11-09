import { describe, expect, it } from "vitest";
import { startRouteXpLabel } from "./xp";

const planRoute = { quest: "plan_route", xp: 30, checkable: true, when: "on_confirm" };
const finishWithinBudget = { quest: "finish_within_budget", xp: 30, checkable: false, when: "end_of_day" };

describe("startRouteXpLabel", () => {
  it("promises planning XP only for the first route of the day", () =>
    expect(startRouteXpLabel([planRoute])).toBe("+30 XP when you start your first route today"));

  it("leaves out XP that starting the route does not earn", () =>
    expect(startRouteXpLabel([planRoute, finishWithinBudget])).toBe("+30 XP when you start your first route today"));

  it("shows nothing when starting the route earns no XP", () =>
    expect(startRouteXpLabel([finishWithinBudget])).toBeNull());
});
