import { useMemo } from "react";
import { Layer, Marker, Source } from "react-map-gl/mapbox";
import type { FeatureCollection, Polygon } from "geojson";
import type { Place, Quest } from "../domain/types";

interface QuestsLayerProps {
  quests: Quest[];
  catalog: Place[];
  onSelect: (place: Place) => void;
  interactive: boolean;
}

export function QuestsLayer({ quests, catalog, onSelect, interactive }: QuestsLayerProps) {
  const zones = useMemo<FeatureCollection<Polygon>>(
    () => ({
      type: "FeatureCollection",
      features: quests.map((quest) => ({ type: "Feature", properties: {}, geometry: quest.zone_geojson })),
    }),
    [quests],
  );
  const participating = useMemo(() => {
    const ids = new Set(quests.flatMap((quest) => quest.place_ids));
    return catalog.filter((place) => ids.has(place.place_id));
  }, [quests, catalog]);

  return (
    <>
      <Source id="quest-zones" type="geojson" data={zones}>
        <Layer id="quest-zone-fill" type="fill" paint={{ "fill-color": "#B26F00", "fill-opacity": 0.1 }} />
        <Layer id="quest-zone-line" type="line" paint={{ "line-color": "#B26F00", "line-width": 2 }} />
      </Source>
      {participating.map((place) => (
        <Marker
          key={place.place_id}
          latitude={place.location.lat}
          longitude={place.location.lng}
          style={interactive ? undefined : { pointerEvents: "none" }}
          onClick={(event) => {
            if (!interactive) return;
            event.originalEvent.stopPropagation();
            onSelect(place);
          }}
        >
          <button
            type="button"
            className={`pin pin-small ${place.category === "free" ? "pin-free" : "pin-partner"}`}
            aria-label={place.name}
          />
        </Marker>
      ))}
    </>
  );
}
