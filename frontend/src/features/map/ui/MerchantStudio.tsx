import { useMemo, useState, type FormEvent } from "react";
import type { Polygon } from "geojson";
import { endDateRange, endOfDay, MIN_ZONE_PLACES, placesInside, zoneChecks } from "../domain/zone";
import type { Place } from "../domain/types";
import { ApiError, type QuestApi } from "../infrastructure/questApi";

interface MerchantStudioProps {
  api: QuestApi;
  catalog: Place[];
  clockIso: string;
  zone: Polygon | null;
  onRedraw: () => void;
  onCreated: () => void;
  onClose: () => void;
}

export function MerchantStudio({ api, catalog, clockIso, zone, onRedraw, onCreated, onClose }: MerchantStudioProps) {
  const merchants = useMemo(() => catalog.filter((place) => place.partner), [catalog]);
  const range = useMemo(() => endDateRange(clockIso), [clockIso]);
  const [merchantId, setMerchantId] = useState("m_bean");
  const [title, setTitle] = useState("");
  const [endDate, setEndDate] = useState(range.suggested);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [neededVisits, setNeededVisits] = useState(MIN_ZONE_PLACES);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inZone = useMemo(
    () => (zone ? placesInside(zone, catalog.filter((place) => place.partner || place.category === "free")) : []),
    [zone, catalog],
  );
  const chosen = inZone.filter((place) => !excluded.includes(place.place_id));
  const checks = zone ? zoneChecks(zone, chosen) : [];
  const ready = Boolean(title.trim()) && checks.length > 0 && checks.every((check) => check.ok);

  const toggle = (placeId: string) =>
    setExcluded((current) =>
      current.includes(placeId) ? current.filter((id) => id !== placeId) : [...current, placeId],
    );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!zone) return;
    setSaving(true);
    setError(null);
    try {
      await api.createQuest(
        {
          title: title.trim(),
          zone_geojson: zone,
          place_ids: chosen.map((place) => place.place_id),
          needed_visits: Math.min(neededVisits, chosen.length),
          ends_at: endOfDay(endDate, clockIso),
        },
        merchantId,
      );
      onCreated();
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Couldn't save this quest. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="panel-body" onSubmit={(event) => void submit(event)}>
      <h2 className="quest-title">Merchant studio</h2>
      <p className="sub">
        {zone ? "Zone drawn. Choose who takes part." : "Click the map to add corners. Click the first corner again to finish."}
      </p>
      <label className="field">
        Your shop
        <select value={merchantId} onChange={(event) => setMerchantId(event.target.value)}>
          {merchants.map((place) => (
            <option key={place.place_id} value={place.place_id}>
              {place.name}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Quest title
        <input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="field">
        Last day
        <input
          type="date"
          value={endDate}
          min={range.min}
          max={range.max}
          onChange={(event) => setEndDate(event.target.value)}
        />
      </label>
      {zone && (
        <>
          <ul className="checks">
            {checks.map((check) => (
              <li key={check.text} className={check.ok ? "ok" : ""}>
                {check.text}
              </li>
            ))}
          </ul>
          <fieldset className="field-group">
            <legend>Places taking part</legend>
            {inZone.map((place) => (
              <label key={place.place_id} className="toggle">
                <input
                  type="checkbox"
                  checked={!excluded.includes(place.place_id)}
                  onChange={() => toggle(place.place_id)}
                />
                {place.name}
              </label>
            ))}
          </fieldset>
          <label className="field">
            Visits needed
            <input
              type="number"
              min={MIN_ZONE_PLACES}
              max={Math.max(MIN_ZONE_PLACES, chosen.length)}
              value={neededVisits}
              onChange={(event) => setNeededVisits(Number(event.target.value))}
            />
          </label>
          <button type="button" className="link" onClick={onRedraw}>
            Redraw zone
          </button>
        </>
      )}
      <p className="sub">Purchases are never required. A new quest replaces your shop's previous one.</p>
      {error && <p className="card warn">{error}</p>}
      <button type="submit" className="btn" disabled={!ready || saving}>
        {saving ? "Publishing…" : "Publish quest"}
      </button>
      <button type="button" className="link" onClick={onClose}>
        Back to quests
      </button>
    </form>
  );
}
