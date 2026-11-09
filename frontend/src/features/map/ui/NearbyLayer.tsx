import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/mapbox";
import type { Nearby } from "../application/useNearby";
import { placesToFeatures } from "../domain/places";

export const CLUSTER_SOURCE = "nearby-places";
export const CLUSTER_LAYER = "nearby-clusters";
export const PIN_LAYERS = ["nearby-pins", "featured-pins"];

const PIN_COLORS = ["match", ["get", "kind"], "partner", "#B26F00", "free", "#1D7A4F", "#5D7285"] as const;
const NOT_CLUSTERED = ["!", ["has", "point_count"]] as const;

export function NearbyLayer({ nearby }: { nearby: Nearby }) {
  const { featured, others } = useMemo(
    () => ({
      featured: placesToFeatures(nearby.places.filter((place) => place.partner || place.category === "free")),
      others: placesToFeatures(nearby.places.filter((place) => !place.partner && place.category !== "free")),
    }),
    [nearby.places],
  );

  return (
    <>
      {nearby.zone && (
        <Source id="walk-zone" type="geojson" data={nearby.zone}>
          <Layer id="walk-zone-fill" type="fill" paint={{ "fill-color": "#1F5FD6", "fill-opacity": 0.08 }} />
          <Layer
            id="walk-zone-line"
            type="line"
            paint={{ "line-color": "#1F5FD6", "line-width": 1.5, "line-dasharray": [2, 2] }}
          />
        </Source>
      )}
      <Source id={CLUSTER_SOURCE} type="geojson" data={others} cluster clusterRadius={42} clusterMaxZoom={16}>
        <Layer
          id={CLUSTER_LAYER}
          type="circle"
          filter={["has", "point_count"]}
          paint={{ "circle-color": "#5D7285", "circle-radius": 15, "circle-opacity": 0.85 }}
        />
        <Layer
          id="nearby-cluster-count"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{ "text-field": ["get", "point_count_abbreviated"], "text-size": 12 }}
          paint={{ "text-color": "#FFFFFF" }}
        />
        <Layer
          id="nearby-pins"
          type="circle"
          filter={[...NOT_CLUSTERED]}
          paint={{
            "circle-color": [...PIN_COLORS],
            "circle-radius": 6,
            "circle-stroke-color": "#FFFFFF",
            "circle-stroke-width": 1.5,
          }}
        />
      </Source>
      <Source id="featured-places" type="geojson" data={featured}>
        <Layer
          id="featured-pins"
          type="circle"
          paint={{
            "circle-color": [...PIN_COLORS],
            "circle-radius": 9,
            "circle-stroke-color": "#FFFFFF",
            "circle-stroke-width": 2,
          }}
        />
      </Source>
    </>
  );
}
