import type { Checkin } from "../application/useCheckin";
import type { Quests } from "../application/useQuests";
import type { Place, Quest } from "../domain/types";
import { formatClock } from "../domain/route";
import { CheckinButtons } from "./PlaceDetails";

interface QuestsPanelProps {
  quests: Quests;
  checkin: Checkin;
  onOpenStudio: () => void;
}

const MADISON_DATE = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Chicago",
  weekday: "short",
  month: "short",
  day: "numeric",
});

export function QuestsPanel({ quests, checkin, onOpenStudio }: QuestsPanelProps) {
  return (
    <div className="panel-body" aria-live="polite">
      {quests.error && <p className="card warn">{quests.error}</p>}
      {quests.loading && <p className="sub">Loading quests…</p>}
      {!quests.loading && quests.quests.length === 0 && !quests.error && (
        <p className="sub">No Community Quests near you right now.</p>
      )}
      {quests.quests.map((quest) => (
        <QuestCard key={quest.id} quest={quest} catalog={quests.catalog} checkin={checkin} />
      ))}
      <button type="button" className="btn ghost" onClick={onOpenStudio}>
        Create a quest as a merchant
      </button>
    </div>
  );
}

interface QuestCardProps {
  quest: Quest;
  catalog: Place[];
  checkin: Checkin;
}

function QuestCard({ quest, catalog, checkin }: QuestCardProps) {
  const visited = Math.min(quest.progress.visited, quest.needed_visits);
  const complete = visited >= quest.needed_visits;
  const earned = quest.progress.rewarded > 0;
  const places = catalog.filter((place) => quest.place_ids.includes(place.place_id));
  return (
    <section className="card quest">
      <h2 className="quest-title">{quest.title}</h2>
      <p className="sub">
        Sponsored by {quest.sponsor.name} · ends {MADISON_DATE.format(new Date(quest.ends_at))},{" "}
        {formatClock(quest.ends_at)}
      </p>
      <div className="prog">
        <i style={{ width: `${(visited / quest.needed_visits) * 100}%` }} />
      </div>
      <p>
        <b>
          {visited}/{quest.needed_visits} visited
        </b>{" "}
        · No purchase needed. A check-in counts.
      </p>
      <p className={complete ? "notice good" : "sub"}>
        {earned ? "Quest complete! Earned: " : complete ? "Quest complete. Reward: " : "Reward: "}
        {quest.reward.badge.replaceAll("_", " ")} badge + {quest.reward.xp} XP
      </p>
      <ul className="quest-places">
        {places.map((place) => (
          <li key={place.place_id}>
            <b>
              {place.name}
              {place.sponsored && <span className="tag sp">Sponsored</span>}
            </b>
            <CheckinButtons place={place} checkin={checkin} />
          </li>
        ))}
      </ul>
    </section>
  );
}
