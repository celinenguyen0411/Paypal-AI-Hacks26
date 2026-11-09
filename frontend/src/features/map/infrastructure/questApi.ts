import type {
  AskResponse,
  Category,
  CheckinResponse,
  ConfirmResponse,
  DemoInfo,
  LatLng,
  NewQuest,
  PlacesResponse,
  QuestsResponse,
  SwapOffer,
  SwapResponse,
  WalkMinutes,
} from "../domain/types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const OFFLINE_MESSAGE = "Can't reach the Quest server. Check that the backend is running.";
const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("offline", OFFLINE_MESSAGE);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.error ?? "server_error", body?.message ?? FALLBACK_MESSAGE);
  }
  return body as T;
}

export interface CheckinInput {
  placeId: string;
  location: LatLng;
  accuracyM: number;
  simulated: boolean;
}

export interface PlacesQuery {
  center: LatLng;
  walkMin: WalkMinutes;
  categories: Category[];
}

export function createQuestApi(userId: string) {
  const jsonHeaders = { "Content-Type": "application/json", "X-User-Id": userId };
  const post = <T>(path: string, body: unknown, headers: Record<string, string> = jsonHeaders) =>
    request<T>(path, { method: "POST", headers, body: JSON.stringify(body) });

  return {
    health: () => request<{ demo: DemoInfo | null }>("/health"),
    ask: (message: string, conversationId: string | null, location: LatLng | null) =>
      post<AskResponse>("/ask", {
        message,
        location,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      }),
    swap: (planId: string, offer: SwapOffer) =>
      post<SwapResponse>(`/ask/plans/${planId}/swap`, {
        replace_order: offer.replace_order,
        with_place_id: offer.with_place_id,
      }),
    confirm: (planId: string) => post<ConfirmResponse>(`/ask/plans/${planId}/confirm`, {}),
    places: ({ center, walkMin, categories }: PlacesQuery) =>
      request<PlacesResponse>(
        `/map/places?lat=${center.lat}&lng=${center.lng}&walk_min=${walkMin}&categories=${categories.join(",")}`,
      ),
    checkin: ({ placeId, location, accuracyM, simulated }: CheckinInput) =>
      post<CheckinResponse>("/map/checkin", {
        place_id: placeId,
        location,
        accuracy_m: accuracyM,
        simulated,
      }),
    quests: (center: LatLng) =>
      request<QuestsResponse>(`/map/community-quests?lat=${center.lat}&lng=${center.lng}`, {
        headers: { "X-User-Id": userId },
      }),
    createQuest: (quest: NewQuest, merchantId: string) =>
      post<{ id: string; places_in_zone: number }>("/merchant/community-quests", quest, {
        "Content-Type": "application/json",
        "X-Merchant-Id": merchantId,
      }),
  };
}

export type QuestApi = ReturnType<typeof createQuestApi>;
