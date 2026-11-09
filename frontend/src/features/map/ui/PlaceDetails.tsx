import type { Checkin } from "../application/useCheckin";
import { formatCents } from "../domain/money";
import { CATEGORY_LABELS, canCheckIn } from "../domain/places";
import { minutesLabel } from "../domain/route";
import type { Place } from "../domain/types";

interface PlaceDetailsProps {
  place: Place;
  checkin: Checkin;
}

export function PlaceDetails({ place, checkin }: PlaceDetailsProps) {
  const estimated = place.cost_source === "category_table";
  return (
    <div className="place-details">
      <div className="sname">
        {place.name}
        {place.sponsored && <span className="tag sp">Sponsored</span>}
      </div>
      <div className="smeta">
        {CATEGORY_LABELS[place.category]} · {minutesLabel(place.walk_s)} walk
        {place.category !== "free" && ` · ${estimated ? "~" : ""}${formatCents(place.est_cost_cents)}`}
      </div>
      {place.deal && (
        <div className="smeta">
          {place.deal.when}{" "}
          <span className={`tag ${place.deal.live_now ? "live" : "off"}`}>
            {place.deal.live_now ? "Live now" : "Not live now"}
          </span>
        </div>
      )}
      {place.checkin_xp > 0 && <div className="smeta">+{place.checkin_xp} XP for checking in</div>}
      {place.community_quest_ids.length > 0 && <span className="tag q">Part of a Community Quest</span>}
      {place.attribution === "foursquare" && <div className="smeta">Source: Foursquare</div>}
      {canCheckIn(place) && <CheckinButtons place={place} checkin={checkin} />}
    </div>
  );
}

export function CheckinButtons({ place, checkin }: PlaceDetailsProps) {
  const busy = checkin.busyPlaceId === place.place_id;
  const notice = checkin.notice?.placeId === place.place_id ? checkin.notice : null;
  return (
    <>
      <div className="chips">
        <button type="button" className="chip" disabled={busy} onClick={() => void checkin.checkIn(place, false)}>
          Check in
        </button>
        {checkin.canPretend && (
          <button type="button" className="chip" disabled={busy} onClick={() => void checkin.checkIn(place, true)}>
            Pretend I'm here
          </button>
        )}
      </div>
      {notice && <p className={`sub notice ${notice.ok ? "good" : "bad"}`}>{notice.message}</p>}
    </>
  );
}
