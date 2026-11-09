import { useCallback, useEffect, useMemo, useState } from "react";
import { readUserId, resetUserId } from "../domain/identity";
import type { DemoInfo } from "../domain/types";
import { ApiError, createQuestApi } from "../infrastructure/questApi";

const newId = () => crypto.randomUUID();

export function useSession() {
  const [userId, setUserId] = useState(() => readUserId(window.localStorage, newId));
  const [demo, setDemo] = useState<DemoInfo | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const api = useMemo(() => createQuestApi(userId), [userId]);

  useEffect(() => {
    api
      .health()
      .then((health) => {
        setDemo(health.demo);
        setOffline(null);
      })
      .catch((failure: unknown) => {
        setOffline(failure instanceof ApiError ? failure.message : "The Quest server is unavailable.");
      });
  }, [api]);

  const resetDemo = useCallback(() => setUserId(resetUserId(window.localStorage, newId)), []);

  return { userId, api, demo, offline, resetDemo };
}
