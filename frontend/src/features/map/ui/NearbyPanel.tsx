import { ALL_CATEGORIES, type Nearby } from "../application/useNearby";
import { CATEGORY_LABELS } from "../domain/places";
import { minutesLabel } from "../domain/route";
import type { Place, WalkMinutes } from "../domain/types";

const WALK_OPTIONS: WalkMinutes[] = [5, 10, 15];
const LIST_LIMIT = 40;

interface NearbyPanelProps {
  nearby: Nearby;
  selectedId: string | null;
  onSelect: (place: Place) => void;
}

function featuredFirst(places: Place[]): Place[] {
  const featured = (place: Place) => place.partner || place.category === "free";
  return [...places.filter(featured), ...places.filter((place) => !featured(place))].slice(0, LIST_LIMIT);
}

export function NearbyPanel({ nearby, selectedId, onSelect }: NearbyPanelProps) {
  return (
    <div className="panel-body">
      <div className="chips" role="group" aria-label="Filter places">
        {ALL_CATEGORIES.map((category) => (
          <button
            key={category}
            type="button"
            className="chip"
            aria-pressed={nearby.categories.includes(category)}
            onClick={() => nearby.toggleCategory(category)}
          >
            {CATEGORY_LABELS[category]}
          </button>
        ))}
      </div>
      <div className="chips" role="group" aria-label="Walking time">
        {WALK_OPTIONS.map((minutes) => (
          <button
            key={minutes}
            type="button"
            className="chip"
            aria-pressed={nearby.walkMin === minutes}
            onClick={() => nearby.setWalkMin(minutes)}
          >
            {minutes} min
          </button>
        ))}
      </div>
      {nearby.error && <p className="card warn">{nearby.error}</p>}
      <p className="sub">
        {nearby.loading ? "Loading places…" : `${nearby.places.length} places in a ${nearby.walkMin}-minute walk`}
      </p>
      {!nearby.loading && nearby.places.length === 0 && !nearby.error && (
        <p className="sub">Nothing to show. Turn on a filter or try a longer walk.</p>
      )}
      <ul className="plist">
        {featuredFirst(nearby.places).map((place) => (
          <li key={place.place_id}>
            <button
              type="button"
              className={place.place_id === selectedId ? "sel" : ""}
              onClick={() => onSelect(place)}
            >
              <i className={`dot ${dotKind(place)}`} />
              <span className="grow">
                <b>{place.name}</b>
                {place.sponsored && <span className="tag sp">Sponsored</span>}
                {place.deal?.live_now && <span className="tag live">Deal live</span>}
              </span>
              <span className="smeta">{minutesLabel(place.walk_s)}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="sub">
        Places come from a saved snapshot, not live listings. Prices marked ~ are estimates.
        {nearby.attributions.includes("foursquare") && " Data: Foursquare."}
        {nearby.zoneIsEstimate && " The walk zone is an estimate."}
      </p>
    </div>
  );
}

function dotKind(place: Place): string {
  if (place.category === "free") return "free";
  return place.partner ? "partner" : "other";
}
