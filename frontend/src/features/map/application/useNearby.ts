import { useEffect, useRef, useState } from "react";
import type { FeatureCollection, Polygon } from "geojson";
import type { Category, LatLng, PlacesResponse, WalkMinutes } from "../domain/types";
import { fetchWalkZone } from "../infrastructure/mapboxRouting";
import { ApiError, type QuestApi } from "../infrastructure/questApi";

export const ALL_CATEGORIES: Category[] = ["lunch", "coffee", "groceries", "free"];

type ZoneCache = Partial<Record<WalkMinutes, FeatureCollection<Polygon>>>;

export function useNearby(api: QuestApi, center: LatLng) {
  const [categories, setCategories] = useState<Category[]>(ALL_CATEGORIES);
  const [walkMin, setWalkMin] = useState<WalkMinutes>(10);
  const [response, setResponse] = useState<PlacesResponse | null>(null);
  const [streetZone, setStreetZone] = useState<FeatureCollection<Polygon> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const zones = useRef<ZoneCache>({});
  const { lat, lng } = center;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .places({ center: { lat, lng }, walkMin, categories: categories.length ? categories : ALL_CATEGORIES })
      .then((result) => {
        if (cancelled) return;
        setResponse(result);
        setError(null);
      })
      .catch((failure: unknown) => {
        if (!cancelled) setError(failure instanceof ApiError ? failure.message : "Couldn't load nearby places.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, lat, lng, walkMin, categories]);

  useEffect(() => {
    let cancelled = false;
    const cached = zones.current[walkMin];
    if (cached) {
      setStreetZone(cached);
      return;
    }
    fetchWalkZone({ lat, lng }, walkMin).then((zone) => {
      if (zone) zones.current[walkMin] = zone;
      if (!cancelled) setStreetZone(zone);
    });
    return () => {
      cancelled = true;
    };
  }, [lat, lng, walkMin]);

  const toggleCategory = (category: Category) =>
    setCategories((current) =>
      current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
    );

  return {
    categories,
    toggleCategory,
    walkMin,
    setWalkMin,
    places: categories.length ? (response?.places ?? []) : [],
    attributions: response?.attributions ?? [],
    zone: streetZone ?? response?.isochrone_geojson ?? null,
    zoneIsEstimate: !streetZone,
    loading,
    error,
  };
}

export type Nearby = ReturnType<typeof useNearby>;
