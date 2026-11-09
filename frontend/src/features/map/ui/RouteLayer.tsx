import { Layer, Marker, Source } from "react-map-gl/mapbox";
import type { Plan, Start } from "../domain/types";
import type { WalkingLine } from "../application/useWalkingLine";

interface RouteLayerProps {
  plan: Plan;
  start: Start | null;
  walkingLine: WalkingLine | null;
}

export function RouteLayer({ plan, start, walkingLine }: RouteLayerProps) {
  return (
    <>
      {walkingLine && (
        <Source id="route" type="geojson" data={walkingLine.line}>
          <Layer
            id="route-line"
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{
              "line-color": "#1F5FD6",
              "line-width": 4,
              ...(walkingLine.followsStreets ? {} : { "line-dasharray": [1.5, 2] }),
            }}
          />
        </Source>
      )}
      {start && (
        <Marker latitude={start.lat} longitude={start.lng}>
          <span className="pin pin-start" aria-label="Start">
            You
          </span>
        </Marker>
      )}
      {plan.stops.map((stop) => (
        <Marker key={stop.place_id} latitude={stop.location.lat} longitude={stop.location.lng}>
          <span className={`pin ${stop.partner ? "pin-partner" : "pin-other"}`} aria-label={stop.name}>
            {stop.order}
          </span>
        </Marker>
      ))}
    </>
  );
}
