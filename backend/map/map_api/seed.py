"""Fictional campus fixtures; these are not verified merchant listings or offers."""

CAMPUS = {"lat": 43.0761, "lng": -89.3999}
FROZEN_AT = "2026-11-04T12:30:00-06:00"


def place(place_id, name, category, lat, lng, cost, partner=False, sponsored=False):
    return dict(place_id=place_id, name=name, category=category,
                location=dict(lat=lat, lng=lng), partner=partner, sponsored=sponsored,
                deal=None, est_cost_cents=cost, checkin_xp=20 if category == "free" else 0,
                attribution=None)


PLACES = [
    place("m_mamalin", "Mama Lin's Noodles", "lunch", 43.0738, -89.3912, 1400, True, True),
    place("m_bean", "Bean Café", "coffee", 43.0745, -89.3940, 650, True),
    place("m_inkoat", "Ink & Oat Café", "coffee", 43.0750, -89.3970, 500, True, True),
    place("m_grocer", "Campus Grocer", "groceries", 43.0735, -89.3950, 1200, True),
    place("m_librarymall", "Library Mall (free)", "free", 43.0752, -89.3966, 0),
    place("m_lakeshore", "Lakeshore Rest Stop (free)", "free", 43.0770, -89.3990, 0),
]
PLACES[0]["deal"] = dict(id="d_mamalin_welcome", pct=15, flat_cents=None,
                         when="First visit · Tue–Thu 2–5pm", cap_cents=600, live_now=False)

ZONE = {"type": "Polygon", "coordinates": [[
    [-89.402, 43.072], [-89.388, 43.072], [-89.388, 43.079],
    [-89.402, 43.079], [-89.402, 43.072],
]]}
