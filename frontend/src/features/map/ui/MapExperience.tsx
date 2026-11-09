import { useEffect, useRef, useState } from "react";
import { Popup, type MapMouseEvent, type MapRef } from "react-map-gl/mapbox";
import type { GeoJSONSource } from "mapbox-gl";
import { useCheckin } from "../application/useCheckin";
import { useNearby } from "../application/useNearby";
import { useQuests } from "../application/useQuests";
import { useRoutePlanner } from "../application/useRoutePlanner";
import { useSession } from "../application/useSession";
import { useWalkingLine } from "../application/useWalkingLine";
import { useZoneDrawing } from "../application/useZoneDrawing";
import { boundsOf, formatClock, type Coordinate } from "../domain/route";
import type { LatLng, Place } from "../domain/types";
import { MAPBOX_TOKEN } from "../infrastructure/mapboxRouting";
import { MerchantStudio } from "./MerchantStudio";
import { CLUSTER_LAYER, CLUSTER_SOURCE, NearbyLayer, PIN_LAYERS } from "./NearbyLayer";
import { NearbyPanel } from "./NearbyPanel";
import { PlaceDetails } from "./PlaceDetails";
import { QuestMap } from "./QuestMap";
import { QuestsLayer } from "./QuestsLayer";
import { QuestsPanel } from "./QuestsPanel";
import { RouteLayer } from "./RouteLayer";
import { RoutePanel } from "./RoutePanel";
import "./map.css";

const CAMPUS: LatLng = { lat: 43.0761, lng: -89.3999 };
const FIT_PADDING = 70;
const TABS = [
  { id: "route", label: "Route" },
  { id: "nearby", label: "Nearby" },
  { id: "quests", label: "Quests" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function MapExperience() {
  const { api, demo, offline, resetDemo } = useSession();
  const center = demo?.location ?? CAMPUS;
  const [tab, setTab] = useState<TabId>("route");
  const [selected, setSelected] = useState<Place | null>(null);
  const planner = useRoutePlanner(api, demo?.location ?? null);
  const nearby = useNearby(api, center);
  const quests = useQuests(api, center);
  const checkin = useCheckin(api, demo, quests.refresh);
  const plan = planner.current?.plan ?? null;
  const walkingLine = useWalkingLine(plan);
  const mapRef = useRef<MapRef>(null);
  const [studioOpen, setStudioOpen] = useState(false);
  const drawing = useZoneDrawing(mapRef, tab === "quests" && studioOpen);

  useEffect(() => {
    if (!plan || tab !== "route") return;
    const coordinates = plan.route_geojson.geometry.coordinates as Coordinate[];
    mapRef.current?.fitBounds(boundsOf(coordinates), { padding: FIT_PADDING, maxZoom: 16, duration: 700 });
  }, [plan, tab]);

  const selectPlace = (place: Place) => {
    setSelected(place);
    checkin.clearNotice();
    mapRef.current?.easeTo({ center: [place.location.lng, place.location.lat], duration: 400 });
  };

  const expandCluster = (clusterId: number, coordinates: Coordinate) => {
    const source = mapRef.current?.getSource(CLUSTER_SOURCE) as GeoJSONSource | undefined;
    source?.getClusterExpansionZoom(clusterId, (error, zoom) => {
      if (!error && zoom !== null && zoom !== undefined) {
        mapRef.current?.easeTo({ center: coordinates, zoom, duration: 400 });
      }
    });
  };

  const handleMapClick = (event: MapMouseEvent) => {
    const feature = event.features?.[0];
    if (!feature) return;
    if (feature.layer?.id === CLUSTER_LAYER) {
      expandCluster(feature.properties?.cluster_id, [event.lngLat.lng, event.lngLat.lat]);
      return;
    }
    const place = nearby.places.find((item) => item.place_id === feature.properties?.place_id);
    if (place) selectPlace(place);
  };

  const openTab = (id: TabId) => {
    setTab(id);
    setSelected(null);
  };

  const openStudio = () => {
    setSelected(null);
    setStudioOpen(true);
  };

  const reset = () => {
    planner.startOver();
    setSelected(null);
    setStudioOpen(false);
    checkin.clearNotice();
    resetDemo();
  };

  return (
    <div className="quest-map">
      <aside className="side">
        <header className="side-head">
          <h1>Quest Map</h1>
          {demo && (
            <button type="button" className="link" onClick={reset}>
              Reset demo
            </button>
          )}
        </header>
        <div className="tabs" role="tablist" aria-label="Map views">
          {TABS.map(({ id, label }) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => openTab(id)}>
              {label}
            </button>
          ))}
        </div>
        {tab === "route" && <RoutePanel planner={planner} />}
        {tab === "nearby" && (
          <NearbyPanel nearby={nearby} selectedId={selected?.place_id ?? null} onSelect={selectPlace} />
        )}
        {tab === "quests" && !studioOpen && (
          <QuestsPanel quests={quests} checkin={checkin} onOpenStudio={openStudio} />
        )}
        {tab === "quests" && studioOpen && (
          <MerchantStudio
            api={api}
            catalog={quests.catalog}
            clockIso={demo?.frozen_at ?? new Date().toISOString().replace("Z", "+00:00")}
            zone={drawing.zone}
            onRedraw={drawing.redraw}
            onCreated={() => {
              void quests.refresh();
              setStudioOpen(false);
            }}
            onClose={() => setStudioOpen(false)}
          />
        )}
      </aside>
      <main className="map-area">
        <QuestMap
          ref={mapRef}
          center={center}
          interactiveLayerIds={tab === "nearby" ? [CLUSTER_LAYER, ...PIN_LAYERS] : undefined}
          onClick={tab === "nearby" ? handleMapClick : undefined}
        >
          {tab === "route" && plan && <RouteLayer plan={plan} start={planner.start} walkingLine={walkingLine} />}
          {tab === "nearby" && <NearbyLayer nearby={nearby} />}
          {tab === "quests" && (
            <QuestsLayer quests={quests.quests} catalog={quests.catalog} onSelect={selectPlace} />
          )}
          {tab !== "route" && selected && (
            <Popup
              latitude={selected.location.lat}
              longitude={selected.location.lng}
              closeOnClick={false}
              onClose={() => setSelected(null)}
              maxWidth="280px"
            >
              <PlaceDetails place={selected} checkin={checkin} />
            </Popup>
          )}
        </QuestMap>
        <div className="banners">
          {offline && <span className="banner down">{offline}</span>}
          {demo && <span className="banner demo">Demo: Wednesday {formatClock(demo.frozen_at)}, near campus</span>}
          {MAPBOX_TOKEN && tab === "route" && plan && !walkingLine?.followsStreets && (
            <span className="banner">Route line is a straight-line estimate</span>
          )}
        </div>
      </main>
    </div>
  );
}
