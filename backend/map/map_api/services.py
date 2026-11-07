import math
from datetime import datetime, timedelta
from uuid import uuid4

from shapely.affinity import scale as scale_geometry
from shapely.geometry import Point, shape

from .config import TZ, Settings
from .database import Database
from .errors import APIError
from .geometry import distance, walking_zone
from .schemas import CheckinRequest, CreateQuestRequest
from .seed import CAMPUS, FROZEN_AT, PLACES

WALK_SPEED_M_S = 1.3
CHECKIN_RADIUS_M = 75
MAX_ACCURACY_M = 50
DAILY_XP_CAP = 100


class MapService:
    """Map rules shared by the HTTP routes, with one configured clock and store."""

    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database

    def now(self):
        return datetime.fromisoformat(FROZEN_AT) if self.settings.demo_mode else datetime.now(TZ)

    def demo(self):
        return {"frozen_at": FROZEN_AT, "location": CAMPUS} if self.settings.demo_mode else None

    def places(self, lat, lng, walk_min, categories):
        if walk_min not in (5, 10, 15):
            raise APIError("invalid_walk_min", "Use a walking limit of 5, 10, or 15 minutes.")
        selected = {category.strip() for category in categories.split(",")}
        if not selected <= {"coffee", "lunch", "groceries", "free"}:
            raise APIError("invalid_categories", "Use coffee, lunch, groceries, or free.")
        origin, radius = dict(lat=lat, lng=lng), walk_min * 60 * WALK_SPEED_M_S
        with self.database.connect() as connection:
            quests = self.database.active_quests(connection, self.now())
        result = []
        for seed in PLACES:
            meters = distance(origin, seed["location"])
            if seed["category"] not in selected or meters > radius:
                continue
            item = dict(seed, walk_s=math.ceil(meters / WALK_SPEED_M_S),
                        community_quest_ids=[q["id"] for q in quests if seed["place_id"] in q["place_ids"]])
            if item["deal"]:
                local = self.now().astimezone(TZ)
                item["deal"] = dict(item["deal"], live_now=local.weekday() in (1, 2, 3)
                                    and 14 <= local.hour < 17)
            result.append(item)
        return dict(demo=self.demo(), source="fallback_seeded", places=sorted(result, key=lambda p: p["walk_s"]),
                    isochrone_geojson=walking_zone(lat, lng, radius), attributions=[])

    def community_quests(self, lat, lng, x_user_id):
        result = []
        with self.database.connect() as connection:
            for quest in self.database.active_quests(connection, self.now()):
                polygon = shape(quest["zone_geojson"])
                # Approximate the closest boundary point, then measure its great-circle distance.
                nearest = polygon.exterior.interpolate(polygon.exterior.project(Point(lng, lat)))
                if not polygon.covers(Point(lng, lat)) and distance(
                        dict(lat=lat, lng=lng), dict(lat=nearest.y, lng=nearest.x)) > 2000:
                    continue
                result.append(dict(quest, progress={"visited": self.database.progress(connection, quest, x_user_id)["visited"]}))
        return dict(demo=self.demo(), source="fallback_seeded", quests=result)

    def checkin(self, body: CheckinRequest, x_user_id):
        place = next((p for p in PLACES if p["place_id"] == body.place_id), None)
        if place is None:
            raise APIError("place_not_found", "This place is not in the seeded map.", 404)
        meters = round(distance(body.location.model_dump(), place["location"]))
        reason = None
        if body.simulated and not self.settings.demo_mode:
            reason = "simulation_not_allowed"
        elif place["category"] != "free":
            reason = "paid_stop_uses_paypal"
        elif not body.simulated and body.accuracy_m > MAX_ACCURACY_M:
            reason = "low_accuracy"
        elif not body.simulated and distance(body.location.model_dump(), place["location"]) > CHECKIN_RADIUS_M:
            reason = "too_far"
        today, timestamp = self.now().date().isoformat(), self.now().isoformat()
        with self.database.connect() as connection:
            # Serialize the read/check/award so concurrent retries cannot duplicate XP or exceed the cap.
            connection.execute("BEGIN IMMEDIATE")
            if reason is None:
                reason = self.database.record_visit(
                    connection, x_user_id, body.place_id, today, timestamp,
                    place["checkin_xp"], DAILY_XP_CAP,
                )
            quests = [q for q in self.database.active_quests(connection, self.now()) if body.place_id in q["place_ids"]]
            updates = [self.database.progress(connection, q, x_user_id) for q in quests]
        xp = place["checkin_xp"] if reason is None else 0
        return dict(demo=self.demo(), ok=reason is None, distance_m=meters, xp_awarded=xp,
                    league_xp_awarded=xp, reason=reason, community_progress=updates)

    def create_quest(self, body: CreateQuestRequest, x_merchant_id):
        merchant = next((p for p in PLACES if p["place_id"] == x_merchant_id and p["partner"]), None)
        if merchant is None:
            raise APIError("invalid_merchant", "Choose a seeded partner merchant.")
        rings = body.zone_geojson.coordinates
        if (len(rings) != 1 or len(rings[0]) < 4 or rings[0][0] != rings[0][-1]
                or any(not (math.isfinite(lng) and math.isfinite(lat) and -180 <= lng <= 180 and -90 <= lat <= 90)
                       for ring in rings for lng, lat in ring)):
            raise APIError("invalid_zone", "Use one closed polygon ring with valid longitude/latitude coordinates.")
        polygon = shape(body.zone_geojson.model_dump())
        if not polygon.is_valid or polygon.is_empty or polygon.area == 0:
            raise APIError("invalid_zone", "The zone must be a valid polygon without self-intersections.")
        # Equirectangular meters are sufficient for these small campus zones; this is not cadastral geometry.
        scale = 111195 * math.cos(math.radians(polygon.centroid.y))
        area = scale_geometry(polygon, xfact=scale, yfact=111195, origin=(0, 0)).area
        if area > 2_000_000:
            raise APIError("zone_too_large", "Keep the zone under 2 km² so it stays walkable.", max_km2=2)
        if body.ends_at.utcoffset() is None or not self.now() < body.ends_at <= self.now() + timedelta(days=14):
            raise APIError("invalid_end_time", "Use a timezone-aware future time within 14 days.")
        ids = set(body.place_ids)
        if len(ids) != len(body.place_ids) or not 2 <= body.needed_visits <= len(ids):
            raise APIError("invalid_places", "Use distinct places and a visit goal between 2 and the place count.")
        inside = {p["place_id"] for p in PLACES if polygon.covers(Point(p["location"]["lng"], p["location"]["lat"]))}
        if not ids <= inside:
            raise APIError("invalid_places", "Every participating place must exist and lie inside the zone.")
        if not body.title.strip():
            raise APIError("invalid_title", "Give the quest a title.")
        quest_id = "cq_" + uuid4().hex[:12]
        quest = dict(id=quest_id, **body.model_dump(mode="json"),
                     sponsor={"merchant_id": x_merchant_id, "name": merchant["name"]},
                     starts_at=self.now().isoformat(), purchase_required=False,
                     reward={"badge": "local_explorer", "xp": 40})
        quest["ends_at"] = body.ends_at.astimezone(TZ).isoformat()
        with self.database.connect() as connection:
            self.database.save_quest(connection, quest)
        return dict(demo=self.demo(), id=quest_id, status="live", places_in_zone=len(inside))
