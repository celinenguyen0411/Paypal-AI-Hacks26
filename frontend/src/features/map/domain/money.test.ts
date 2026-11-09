import { describe, expect, it } from "vitest";
import { budgetBar, formatCents } from "./money";

describe("formatCents", () => {
  it("shows dollars and cents", () => expect(formatCents(3050)).toBe("$30.50"));
  it("shows zero", () => expect(formatCents(0)).toBe("$0.00"));
  it("puts the minus before the dollar sign", () => expect(formatCents(-50)).toBe("-$0.50"));
});

describe("budgetBar", () => {
  it("flags the over-budget Wednesday plan", () => {
    expect(budgetBar({ cost_cents: 3050, budget_left_cents: -50, over_budget: true }))
      .toEqual({ percent: 100, over: true, spent: "$30.50", budget: "$30.00", status: "$0.50 over budget" });
  });
  it("shows what is left after the swap", () => {
    expect(budgetBar({ cost_cents: 2900, budget_left_cents: 100, over_budget: false }))
      .toEqual({ percent: 97, over: false, spent: "$29.00", budget: "$30.00", status: "$1.00 left" });
  });
});
