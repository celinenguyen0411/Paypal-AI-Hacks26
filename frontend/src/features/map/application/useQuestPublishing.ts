import { useCallback, useState } from "react";
import type { NewQuest } from "../domain/types";
import { ApiError, type QuestApi } from "../infrastructure/questApi";

export function useQuestPublishing(api: QuestApi, onPublished: () => void) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const publish = useCallback(
    async (quest: NewQuest, merchantId: string) => {
      setSaving(true);
      setError(null);
      try {
        await api.createQuest(quest, merchantId);
        onPublished();
      } catch (failure) {
        setError(failure instanceof ApiError ? failure.message : "Couldn't save this quest. Please try again.");
      } finally {
        setSaving(false);
      }
    },
    [api, onPublished],
  );

  return { publish, saving, error };
}
