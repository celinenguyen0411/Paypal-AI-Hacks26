import type { XpPreview } from "./types";

export function startRouteXpLabel(preview: XpPreview[]): string | null {
  const xp = preview.filter((item) => item.when === "on_confirm").reduce((total, item) => total + item.xp, 0);
  return xp > 0 ? `+${xp} XP when you start your first route today` : null;
}
