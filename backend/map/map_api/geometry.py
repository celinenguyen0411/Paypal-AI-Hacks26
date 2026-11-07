import math


def distance(a, b):
    """Return great-circle meters between {lat, lng} points."""
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(b["lng"] - a["lng"])
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, value)))


def walking_zone(lat, lng, radius):
    # A geodesic circle is only a fallback estimate, not a street-network isochrone.
    points = []
    angular = radius / 6371000
    lat1, lng1 = math.radians(lat), math.radians(lng)
    for step in range(65):
        bearing = 2 * math.pi * step / 64
        lat2 = math.asin(math.sin(lat1) * math.cos(angular)
                         + math.cos(lat1) * math.sin(angular) * math.cos(bearing))
        lng2 = lng1 + math.atan2(math.sin(bearing) * math.sin(angular) * math.cos(lat1),
                                math.cos(angular) - math.sin(lat1) * math.sin(lat2))
        points.append([((math.degrees(lng2) + 180) % 360) - 180, math.degrees(lat2)])
    points[-1] = points[0]
    return {"type": "FeatureCollection", "features": [{"type": "Feature",
            "properties": {"estimated": True},
            "geometry": {"type": "Polygon", "coordinates": [points]}}]}
