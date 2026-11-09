import { useCallback, useState } from "react";
import type { BudgetCheck, LatLng, Plan, Start, SwapOffer } from "../domain/types";
import { ApiError, type QuestApi } from "../infrastructure/questApi";

type Busy = "asking" | "swapping" | "confirming" | null;

interface PlannedRoute {
  plan: Plan;
  budgetCheck: BudgetCheck | null;
}

interface RouteState {
  busy: Busy;
  error: string | null;
  reply: string | null;
  start: Start | null;
  conversationId: string | null;
  current: PlannedRoute | null;
  undoStack: PlannedRoute[];
  confirmedXp: number | null;
}

const EMPTY: RouteState = {
  busy: null,
  error: null,
  reply: null,
  start: null,
  conversationId: null,
  current: null,
  undoStack: [],
  confirmedXp: null,
};

function errorMessage(failure: unknown): string {
  return failure instanceof ApiError ? failure.message : "Something went wrong. Please try again.";
}

export function useRoutePlanner(api: QuestApi, location: LatLng | null) {
  const [state, setState] = useState<RouteState>(EMPTY);

  const run = useCallback(async (busy: Busy, action: () => Promise<Partial<RouteState>>) => {
    setState((previous) => ({ ...previous, busy, error: null }));
    try {
      const changes = await action();
      setState((previous) => ({ ...previous, ...changes, busy: null }));
    } catch (failure) {
      setState((previous) => ({ ...previous, busy: null, error: errorMessage(failure) }));
    }
  }, []);

  const ask = useCallback(
    (message: string) =>
      run("asking", async () => {
        const response = await api.ask(message, state.conversationId, location);
        const planned = response.plan
          ? { current: { plan: response.plan, budgetCheck: response.budget_check }, undoStack: [], confirmedXp: null }
          : {};
        return {
          reply: response.reply,
          start: response.intent.start,
          conversationId: response.conversation_id,
          ...planned,
        };
      }),
    [api, location, run, state.conversationId],
  );

  const swap = useCallback(
    (offer: SwapOffer) => {
      const { current, undoStack } = state;
      if (!current) return Promise.resolve();
      return run("swapping", async () => {
        const response = await api.swap(current.plan.plan_id, offer);
        return {
          current: { plan: response.plan, budgetCheck: response.budget_check },
          undoStack: [...undoStack, current],
          confirmedXp: null,
          reply: null,
        };
      });
    },
    [api, run, state],
  );

  const undoSwap = useCallback(() => {
    setState((previous) => {
      const restored = previous.undoStack.at(-1);
      return restored
        ? { ...previous, current: restored, undoStack: previous.undoStack.slice(0, -1), confirmedXp: null }
        : previous;
    });
  }, []);

  const confirm = useCallback(() => {
    const { current } = state;
    if (!current) return Promise.resolve();
    return run("confirming", async () => {
      const response = await api.confirm(current.plan.plan_id);
      return { confirmedXp: response.xp_awarded };
    });
  }, [api, run, state]);

  const startOver = useCallback(() => setState(EMPTY), []);

  return { ...state, ask, swap, undoSwap, confirm, startOver };
}

export type RoutePlanner = ReturnType<typeof useRoutePlanner>;
