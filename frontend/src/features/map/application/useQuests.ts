import { useCallback, useEffect, useState } from "react";
import type { LatLng, Place, Quest } from "../domain/types";
import { ApiError, type QuestApi } from "../infrastructure/questApi";
import { ALL_CATEGORIES } from "./useNearby";

const CATALOG_WALK_MIN = 15;

export function useQuests(api: QuestApi, center: LatLng) {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [catalog, setCatalog] = useState<Place[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { lat, lng } = center;

  const refresh = useCallback(async () => {
    try {
      const [questResult, placeResult] = await Promise.all([
        api.quests({ lat, lng }),
        api.places({ center: { lat, lng }, walkMin: CATALOG_WALK_MIN, categories: ALL_CATEGORIES }),
      ]);
      setQuests(questResult.quests);
      setCatalog(placeResult.places);
      setError(null);
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Couldn't load quests.");
    } finally {
      setLoading(false);
    }
  }, [api, lat, lng]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { quests, catalog, loading, error, refresh };
}

export type Quests = ReturnType<typeof useQuests>;
