import { useCallback, useState } from "react";
import { CHECKIN_MESSAGES } from "../domain/places";
import type { CheckinResponse, DemoInfo, Place } from "../domain/types";
import { ApiError, type CheckinInput, type QuestApi } from "../infrastructure/questApi";

const PRETEND_ACCURACY_M = 10;

export interface CheckinNotice {
  placeId: string;
  ok: boolean;
  message: string;
}

function currentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) reject(new Error("unsupported"));
    else navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
  });
}

function successMessage(result: CheckinResponse): string {
  const reward = result.xp_awarded > 0 ? `+${result.xp_awarded} XP` : "Visit counted";
  const quest = result.community_progress[0];
  if (!quest) return `Checked in. ${reward}.`;
  return `Checked in. ${reward}. Quest: ${Math.min(quest.visited, quest.needed)}/${quest.needed} visited.`;
}

function failureMessage(failure: unknown): string {
  if (failure instanceof ApiError) return failure.message;
  return "We couldn't get your location. Allow location access and try again.";
}

export function useCheckin(api: QuestApi, demo: DemoInfo | null, onCheckedIn: () => void) {
  const [notice, setNotice] = useState<CheckinNotice | null>(null);
  const [busyPlaceId, setBusyPlaceId] = useState<string | null>(null);

  const realInput = useCallback(async (place: Place): Promise<CheckinInput> => {
    const { coords } = await currentPosition();
    return {
      placeId: place.place_id,
      location: { lat: coords.latitude, lng: coords.longitude },
      accuracyM: coords.accuracy,
      simulated: false,
    };
  }, []);

  const pretendInput = useCallback(
    async (place: Place): Promise<CheckinInput> => ({
      placeId: place.place_id,
      location: demo?.location ?? place.location,
      accuracyM: PRETEND_ACCURACY_M,
      simulated: true,
    }),
    [demo],
  );

  const checkIn = useCallback(
    async (place: Place, pretend: boolean) => {
      setBusyPlaceId(place.place_id);
      try {
        const result = await api.checkin(await (pretend ? pretendInput(place) : realInput(place)));
        const message = result.ok ? successMessage(result) : CHECKIN_MESSAGES[result.reason ?? "too_far"];
        setNotice({ placeId: place.place_id, ok: result.ok, message });
        if (result.ok) onCheckedIn();
      } catch (failure) {
        setNotice({ placeId: place.place_id, ok: false, message: failureMessage(failure) });
      } finally {
        setBusyPlaceId(null);
      }
    },
    [api, onCheckedIn, pretendInput, realInput],
  );

  const clearNotice = useCallback(() => setNotice(null), []);

  return { checkIn, notice, busyPlaceId, clearNotice, canPretend: demo !== null };
}

export type Checkin = ReturnType<typeof useCheckin>;
