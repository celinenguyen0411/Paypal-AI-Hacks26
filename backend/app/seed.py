"""Fictional campus fixtures; these are not verified merchant listings or offers."""

CAMPUS = {"lat": 43.0761, "lng": -89.3999}
FROZEN_AT = "2026-11-04T12:30:00-06:00"
SEEDED_QUEST_ID = "cq_state_st"


def place(place_id, name, category, lat, lng, cost, partner=False, sponsored=False):
    return dict(place_id=place_id, name=name, category=category,
                location=dict(lat=lat, lng=lng), partner=partner, sponsored=sponsored,
                deal=None, est_cost_cents=cost, cost_source="merchant",
                checkin_xp=20 if category == "free" else 0, attribution=None)


PLACES = [
    place("m_mamalin", "Mama Lin's Noodles", "lunch", 43.0738, -89.3912, 1400, True, True),
    place("m_bean", "Bean Café", "coffee", 43.0749, -89.3955, 650, True),
    place("m_inkoat", "Ink & Oat Café", "coffee", 43.0732, -89.4014, 500, True, True),
    place("m_grocer", "Campus Grocer", "groceries", 43.0743, -89.3983, 1200, True),
    place("m_librarymall", "Library Mall (free)", "free", 43.0752, -89.3966, 0),
    place("m_lakeshore", "Lakeshore Rest Stop (free)", "free", 43.0770, -89.3990, 0),
    place("m_lakeview", "Lakeview Deli", "lunch", 43.0756, -89.3974, 1200, True),
]
PLACES[0]["deal"] = dict(id="d_mamalin_welcome", pct=15, flat_cents=None,
                         when="First visit · Tue–Thu 2–5pm", cap_cents=600, live_now=False,
                         days=(1, 2, 3), from_hour=14, to_hour=17)
PLACES[2]["deal"] = dict(id="d_inkoat_coffee", pct=None, flat_cents=100,
                         when="$1 back · Every day 7am–9pm", cap_cents=100, live_now=False,
                         days=(0, 1, 2, 3, 4, 5, 6), from_hour=7, to_hour=21)

ZONE = {"type": "Polygon", "coordinates": [[
    [-89.402, 43.072], [-89.388, 43.072], [-89.388, 43.079],
    [-89.402, 43.079], [-89.402, 43.072],
]]}
