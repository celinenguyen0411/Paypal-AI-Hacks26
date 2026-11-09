export interface BudgetTotals {
  cost_cents: number;
  budget_left_cents: number;
  over_budget: boolean;
}

export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  return `${sign}$${(Math.abs(cents) / 100).toFixed(2)}`;
}

export function budgetBar(totals: BudgetTotals) {
  const budgetCents = totals.cost_cents + totals.budget_left_cents;
  const left = totals.budget_left_cents;
  return {
    percent: budgetCents > 0 ? Math.min(100, Math.round((totals.cost_cents / budgetCents) * 100)) : 100,
    over: totals.over_budget,
    spent: formatCents(totals.cost_cents),
    budget: formatCents(budgetCents),
    status: totals.over_budget ? `${formatCents(-left)} over budget` : `${formatCents(left)} left`,
  };
}
