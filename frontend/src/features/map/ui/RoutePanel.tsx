import { useState, type FormEvent } from "react";
import type { RoutePlanner } from "../application/useRoutePlanner";
import { budgetBar, formatCents } from "../domain/money";
import { formatClock, minutesLabel } from "../domain/route";
import type { Leg, Plan, Stop, SwapOffer } from "../domain/types";
import { startRouteXpLabel } from "../domain/xp";

const WEDNESDAY_PROMPT = "Wed 12:30: lunch, coffee and a few groceries before my 2pm class. $30 max.";

export function RoutePanel({ planner }: { planner: RoutePlanner }) {
  const plan = planner.current?.plan;
  return (
    <div className="panel-body" aria-live="polite">
      <AskBar planner={planner} />
      {planner.reply && <p className="reply">{planner.reply}</p>}
      {planner.error && <p className="card warn">{planner.error}</p>}
      {plan ? <PlanDetails plan={plan} planner={planner} /> : <EmptyRoute busy={planner.busy === "asking"} />}
    </div>
  );
}

function EmptyRoute({ busy }: { busy: boolean }) {
  return (
    <p className="sub">
      {busy ? "Planning your route…" : "Say what you need, your budget and when you have to be back."}
    </p>
  );
}

function AskBar({ planner }: { planner: RoutePlanner }) {
  const [message, setMessage] = useState("");
  const busy = planner.busy !== null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (message.trim()) void planner.ask(message.trim());
  };

  return (
    <form className="ask" onSubmit={submit}>
      <label className="eyebrow" htmlFor="ask-input">
        Plan an outing
      </label>
      <textarea
        id="ask-input"
        rows={2}
        value={message}
        placeholder="Lunch and coffee under $20 before 2pm"
        onChange={(event) => setMessage(event.target.value)}
      />
      <div className="row">
        <button type="button" className="chip" disabled={busy} onClick={() => setMessage(WEDNESDAY_PROMPT)}>
          Wednesday lunch run
        </button>
        <button type="submit" className="btn compact" disabled={busy || !message.trim()}>
          {planner.busy === "asking" ? "Planning…" : "Plan"}
        </button>
      </div>
    </form>
  );
}

function PlanDetails({ plan, planner }: { plan: Plan; planner: RoutePlanner }) {
  const [showWhy, setShowWhy] = useState(false);
  return (
    <>
      <BudgetBar plan={plan} />
      <p className="sub">Preview: no payment is taken from this screen.</p>
      {plan.source === "fallback_seeded" && (
        <p className="sub">Live places unavailable: using a saved snapshot. Prices marked ~ are estimates.</p>
      )}
      {planner.current?.budgetCheck && (
        <p className="sub">
          {planner.current.budgetCheck.ok ? "Fits" : "Exceeds"} your{" "}
          {formatCents(planner.current.budgetCheck.safe_to_spend_cents)} safe to spend (demo balance).
        </p>
      )}
      {plan.swaps.map((offer) => (
        <SwapCard key={offer.with_place_id} offer={offer} disabled={planner.busy !== null} onSwap={planner.swap} />
      ))}
      {planner.undoStack.length > 0 && (
        <button type="button" className="link" onClick={planner.undoSwap}>
          Undo swap
        </button>
      )}
      <StopList plan={plan} />
      <button type="button" className="link" aria-expanded={showWhy} onClick={() => setShowWhy(!showWhy)}>
        Why this order?
      </button>
      {showWhy && <WhySheet plan={plan} />}
      <ConfirmArea plan={plan} planner={planner} />
      <button type="button" className="link" onClick={planner.startOver}>
        Start over
      </button>
    </>
  );
}

function BudgetBar({ plan }: { plan: Plan }) {
  const bar = budgetBar(plan.totals);
  const { cashback_cents: cashback, return_at: returnAt, distance_m: meters } = plan.totals;
  return (
    <section className={`bbar ${bar.over ? "over" : ""}`} aria-label="Budget">
      <div className="bbar-top">
        <b>
          {bar.spent} <small>of {bar.budget} today</small>
        </b>
        <span>{bar.status}</span>
      </div>
      <div className="track">
        <i style={{ width: `${bar.percent}%` }} />
      </div>
      {cashback > 0 && <p className="sub cbline">+{formatCents(cashback)} to house fund, clears in 7 days</p>}
      <p className="sub">
        Back by {formatClock(returnAt)} · {meters} m walk
      </p>
    </section>
  );
}

interface SwapCardProps {
  offer: SwapOffer;
  disabled: boolean;
  onSwap: (offer: SwapOffer) => Promise<void>;
}

function SwapCard({ offer, disabled, onSwap }: SwapCardProps) {
  return (
    <section className="card swap">
      <div className="row">
        <b className="grow">Swap to {offer.name}</b>
        {offer.sponsored && <span className="tag sp">Sponsored</span>}
      </div>
      <p>
        {formatCents(offer.pay_less_today_cents)} less today
        {offer.cashback_cents > 0 && `, +${formatCents(offer.cashback_cents)} to your house fund`},{" "}
        {minutesLabel(offer.extra_walk_s)} off route
        {offer.fixes_over_budget && ". Brings you under budget"}
      </p>
      <button type="button" className="btn compact" disabled={disabled} onClick={() => void onSwap(offer)}>
        Take this swap
      </button>
    </section>
  );
}

function StopList({ plan }: { plan: Plan }) {
  const finalLeg = plan.legs.at(-1);
  return (
    <ol className="stops">
      {plan.stops.map((stop, index) => (
        <StopRow key={stop.place_id} stop={stop} leg={plan.legs[index]} />
      ))}
      {finalLeg && (
        <li className="stop">
          <span className="num end">End</span>
          <div className="smeta">Walk back · {minutesLabel(finalLeg.duration_s)}</div>
        </li>
      )}
    </ol>
  );
}

function StopRow({ stop, leg }: { stop: Stop; leg: Leg }) {
  return (
    <li className="stop">
      <span className={`num ${stop.partner ? "p" : ""}`}>{stop.order}</span>
      <div>
        <div className="sname">
          {stop.name}
          {stop.sponsored && <span className="tag sp">Sponsored</span>}
          {stop.attribution === "foursquare" && <span className="tag g">Foursquare</span>}
        </div>
        <div className="smeta">
          {minutesLabel(leg.duration_s)} walk · arrive {formatClock(stop.arrive_at)}
          {stop.wait_s > 0 && ` · wait ${minutesLabel(stop.wait_s)} for the deal`}
        </div>
        <div className="smeta">{stop.pay_via === "quest" ? "Pay through Quest" : "Pay as usual"}</div>
      </div>
      <div className="sprice">
        <span>
          {stop.cost_source === "category_table" && "~"}
          {formatCents(stop.est_cost_cents)}
        </span>
        {stop.cashback_cents > 0 && <small className="cb">+{formatCents(stop.cashback_cents)} back</small>}
      </div>
    </li>
  );
}

function WhySheet({ plan }: { plan: Plan }) {
  return (
    <section className="why">
      <p>{plan.ranking}</p>
      <ul>
        {plan.stops.map((stop) => (
          <li key={stop.place_id}>
            <b>{stop.name}:</b> {stop.why.join(" ")}
          </li>
        ))}
        {plan.hidden.map((place) => (
          <li key={place.place_id}>
            <b>Not {place.name}:</b> {place.label}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ConfirmArea({ plan, planner }: { plan: Plan; planner: RoutePlanner }) {
  if (planner.confirmedXp !== null) {
    return (
      <p className="card done">
        {planner.confirmedXp > 0
          ? `Route saved. +${planner.confirmedXp} XP for planning.`
          : "Route saved. You've already earned today's planning XP."}
      </p>
    );
  }
  const xpLabel = startRouteXpLabel(plan.xp_preview);
  return (
    <>
      {xpLabel && <p className="sub xpline">{xpLabel}</p>}
      <button type="button" className="btn" disabled={planner.busy !== null} onClick={() => void planner.confirm()}>
        {planner.busy === "confirming" ? "Saving…" : "Start this route"}
      </button>
    </>
  );
}
