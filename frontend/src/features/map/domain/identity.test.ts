import { describe, expect, it } from "vitest";
import { readUserId, resetUserId } from "./identity";

function memoryStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
  };
}

const brokenStorage = {
  getItem: () => { throw new Error("blocked"); },
  setItem: () => { throw new Error("blocked"); },
  removeItem: () => { throw new Error("blocked"); },
};

describe("identity", () => {
  it("creates one id and keeps it", () => {
    const storage = memoryStorage();
    const first = readUserId(storage, () => "abc");
    expect(first).toBe("judge-abc");
    expect(readUserId(storage, () => "other")).toBe("judge-abc");
  });
  it("still returns an id when storage is blocked", () => {
    expect(readUserId(brokenStorage, () => "abc")).toBe("judge-abc");
  });
  it("gives a fresh id after a reset", () => {
    const storage = memoryStorage();
    readUserId(storage, () => "abc");
    expect(resetUserId(storage, () => "new")).toBe("judge-new");
    expect(readUserId(storage, () => "later")).toBe("judge-new");
  });
});
