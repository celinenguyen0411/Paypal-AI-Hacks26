import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from .seed import PLACES, SEEDED_QUEST_ID, ZONE


class Database:
    """SQLite persistence; callers own transaction boundaries for multi-step awards."""

    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, now):
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS visits (
                    user_id TEXT, place_id TEXT, day TEXT, visited_at TEXT, xp INTEGER,
                    PRIMARY KEY(user_id, place_id, day)
                );
                CREATE TABLE IF NOT EXISTS quests (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL,
                    confirmed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS plan_contexts (
                    plan_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plan_awards (
                    user_id TEXT, day TEXT, PRIMARY KEY(user_id, day)
                );
            """)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start -= timedelta(days=start.weekday())
            quest = dict(id=SEEDED_QUEST_ID, title="Explore State Street: visit 2 local spots this week",
                         sponsor={"merchant_id": "m_mamalin", "name": "Mama Lin's Noodles"},
                         zone_geojson=ZONE, place_ids=[p["place_id"] for p in PLACES],
                         needed_visits=2, purchase_required=False,
                         starts_at=start.isoformat(), ends_at=(start + timedelta(days=7, seconds=-1)).isoformat(),
                         reward={"badge": "state_street_explorer", "xp": 40})
            connection.execute("INSERT OR IGNORE INTO quests VALUES (?, ?)",
                               (quest["id"], json.dumps(quest)))

    def active_quests(self, connection, now):
        return [q for row in connection.execute("SELECT payload FROM quests")
                if datetime.fromisoformat((q := json.loads(row[0]))["starts_at"]) <= now
                < datetime.fromisoformat(q["ends_at"])]

    def progress(self, connection, quest, user):
        placeholders = ",".join("?" for _ in quest["place_ids"])
        count = connection.execute(
            f"SELECT COUNT(DISTINCT place_id) FROM visits WHERE user_id=? "
            f"AND place_id IN ({placeholders}) AND julianday(visited_at)>=julianday(?) "
            "AND julianday(visited_at)<=julianday(?)",
            [user, *quest["place_ids"], quest["starts_at"], quest["ends_at"]],
        ).fetchone()[0]
        return dict(quest_id=quest["id"], visited=count, needed=quest["needed_visits"],
                    completed=count >= quest["needed_visits"])

    def record_visit(self, connection, user, place_id, day, timestamp, xp, daily_cap):
        """Return a rejection reason or insert a visit; requires an IMMEDIATE transaction."""
        if connection.execute("SELECT 1 FROM visits WHERE user_id=? AND place_id=? AND day=?",
                              (user, place_id, day)).fetchone():
            return "already_today"
        awarded = connection.execute(
            "SELECT COALESCE(SUM(xp),0) FROM visits WHERE user_id=? AND day=?", (user, day),
        ).fetchone()[0]
        if awarded + xp > daily_cap:
            return "daily_cap"
        connection.execute("INSERT INTO visits VALUES (?,?,?,?,?)", (user, place_id, day, timestamp, xp))
        return None

    def remove_live_quests(self, connection, merchant_id, now):
        for quest in self.active_quests(connection, now):
            if quest["sponsor"]["merchant_id"] == merchant_id and quest["id"] != SEEDED_QUEST_ID:
                connection.execute("DELETE FROM quests WHERE id=?", (quest["id"],))

    def save_quest(self, connection, quest):
        connection.execute("INSERT INTO quests VALUES (?,?)", (quest["id"], json.dumps(quest)))

    def conversation(self, conversation_id, user):
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM conversations WHERE id=? AND user_id=?",
                                     (conversation_id, user)).fetchone()
        return json.loads(row[0]) if row else None

    def save_exchange(self, conversation_id, user, state, plan, context=None):
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO conversations VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (conversation_id, user, json.dumps(state)),
            )
            if plan:
                connection.execute("INSERT INTO plans (id,user_id,payload) VALUES (?,?,?)",
                                   (plan["plan_id"], user, json.dumps(plan)))
                connection.execute("INSERT INTO plan_contexts VALUES (?,?,?)",
                                   (plan["plan_id"], user, json.dumps(context)))

    def plan_with_context(self, plan_id, user):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT plans.payload, plan_contexts.payload FROM plans "
                "JOIN plan_contexts ON plan_contexts.plan_id = plans.id "
                "WHERE plans.id=? AND plans.user_id=?", (plan_id, user)).fetchone()
        return (json.loads(row[0]), json.loads(row[1])) if row else None

    def confirm_plan(self, plan_id, user, day):
        """Confirm a saved plan once; serialize daily awards across plans and retries."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload,confirmed FROM plans WHERE id=? AND user_id=?",
                                     (plan_id, user)).fetchone()
            if row is None:
                return None
            awarded = 0
            if not row["confirmed"]:
                connection.execute("UPDATE plans SET confirmed=1 WHERE id=?", (plan_id,))
                inserted = connection.execute("INSERT OR IGNORE INTO plan_awards VALUES (?,?)", (user, day))
                awarded = 30 if inserted.rowcount else 0
            return json.loads(row["payload"]), awarded
