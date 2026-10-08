"""
Phase 6B Task F.3 — point-in-geofence validation for the new `Geofence`
model, reusing the EXISTING `haversine_distance()`/`GpsCoordinate` from
`services_geofencing.py` rather than reimplementing distance math (no
second Haversine implementation). Polygon support uses a standard
ray-casting point-in-polygon algorithm — circle is the only type proven
for parity against the legacy branch-based check in this pass.
"""
from __future__ import annotations

from apps.attendance.services_geofencing import GpsCoordinate, haversine_distance


def validate_circle(point: GpsCoordinate, geofence) -> tuple[bool, float]:
    """Returns (is_inside, distance_metres). Mirrors
    `GeofencingService._validate_office()`'s own `distance <= radius`
    check exactly (no accuracy-tolerance added here — Task F.3 asks only
    for parity with today's circle calculation, which this matches)."""
    center = GpsCoordinate(latitude=float(geofence.center_latitude), longitude=float(geofence.center_longitude))
    distance = haversine_distance(point, center)
    return distance <= geofence.radius_meters, distance


def validate_polygon(point: GpsCoordinate, geofence) -> bool:
    """Standard ray-casting point-in-polygon test. `geofence.polygon_points`
    is a list of [lat, lng] pairs forming a closed ring (first/last point
    need not be identical)."""
    points = geofence.polygon_points
    inside = False
    n = len(points)
    j = n - 1
    for i in range(n):
        yi, xi = points[i]
        yj, xj = points[j]
        if ((yi > point.latitude) != (yj > point.latitude)) and (
            point.longitude < (xj - xi) * (point.latitude - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def validate_point(point: GpsCoordinate, geofence) -> tuple[bool, float | None]:
    if geofence.type == geofence.TYPE_CIRCLE:
        return validate_circle(point, geofence)
    return validate_polygon(point, geofence), None
