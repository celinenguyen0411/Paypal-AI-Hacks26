import { forwardRef, type ReactNode } from "react";
import Map, { NavigationControl, type MapMouseEvent, type MapRef } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";
import type { LatLng } from "../domain/types";
import { MAPBOX_TOKEN } from "../infrastructure/mapboxRouting";

const STREET_STYLE = "mapbox://styles/mapbox/light-v11";

interface QuestMapProps {
  center: LatLng;
  interactiveLayerIds?: string[];
  onClick?: (event: MapMouseEvent) => void;
  children?: ReactNode;
}

export const QuestMap = forwardRef<MapRef, QuestMapProps>(function QuestMap(
  { center, interactiveLayerIds, onClick, children },
  ref,
) {
  if (!MAPBOX_TOKEN) {
    return (
      <div className="no-token">
        <h2>Map needs a Mapbox token</h2>
        <p>Paste your public token into VITE_MAPBOX_TOKEN in frontend/.env.local, then restart the dev server.</p>
      </div>
    );
  }
  return (
    <Map
      ref={ref}
      mapboxAccessToken={MAPBOX_TOKEN}
      mapStyle={STREET_STYLE}
      initialViewState={{ latitude: center.lat, longitude: center.lng, zoom: 14.5 }}
      interactiveLayerIds={interactiveLayerIds}
      onClick={onClick}
      style={{ width: "100%", height: "100%" }}
    >
      <NavigationControl position="bottom-right" showCompass={false} />
      {children}
    </Map>
  );
});
