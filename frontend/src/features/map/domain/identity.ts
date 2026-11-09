const USER_ID_KEY = "quest.map.userId";

export type IdStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export type MakeId = () => string;

function saved(storage: IdStorage): string | null {
  try {
    return storage.getItem(USER_ID_KEY);
  } catch {
    return null;
  }
}

function save(storage: IdStorage, userId: string): void {
  try {
    storage.setItem(USER_ID_KEY, userId);
  } catch {
    return;
  }
}

export function resetUserId(storage: IdStorage, makeId: MakeId): string {
  const userId = `judge-${makeId()}`;
  save(storage, userId);
  return userId;
}

export function readUserId(storage: IdStorage, makeId: MakeId): string {
  return saved(storage) ?? resetUserId(storage, makeId);
}
