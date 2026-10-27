"""Sanity checks for a branch's office coordinates.

Two kinds of result, deliberately separate:
  * ERRORS  — the value cannot be a coordinate (out of range, "null island"). These reject the save.
  * WARNINGS — a valid coordinate that looks wrong for the branch's state or city (e.g. Mumbai coordinates on a
    Hyderabad branch). These never block a save, because only the business knows where the office really is; they
    tell the admin to double-check.

The state boxes and city centres below are approximate reference data used ONLY to raise warnings. They are never
written to a branch.
"""
from __future__ import annotations

import math

MIN_RADIUS_METERS = 10
MAX_RADIUS_METERS = 5000
# A coordinate this far from the known centre of the branch's city is flagged.
CITY_DISTANCE_WARNING_KM = 60

# (lat_min, lat_max, lon_min, lon_max) — generous boxes around each state / union territory.
_STATE_BOXES: dict[str, tuple[float, float, float, float]] = {
    'andhra pradesh': (12.6, 19.95, 76.7, 84.8),
    'telangana': (15.8, 19.95, 77.2, 81.8),
    'karnataka': (11.5, 18.5, 74.0, 78.6),
    'tamil nadu': (8.0, 13.6, 76.2, 80.4),
    'kerala': (8.2, 12.8, 74.8, 77.5),
    'maharashtra': (15.6, 22.1, 72.6, 80.9),
    'gujarat': (20.1, 24.7, 68.1, 74.5),
    'rajasthan': (23.0, 30.2, 69.4, 78.3),
    'delhi': (28.4, 28.9, 76.8, 77.4),
    'uttar pradesh': (23.8, 30.4, 77.0, 84.7),
    'madhya pradesh': (21.0, 26.9, 74.0, 82.9),
    'west bengal': (21.5, 27.3, 85.8, 89.9),
    'odisha': (17.8, 22.6, 81.3, 87.5),
    'bihar': (24.2, 27.6, 83.3, 88.3),
    'punjab': (29.5, 32.6, 73.8, 77.0),
    'haryana': (27.6, 30.95, 74.4, 77.6),
    'goa': (14.9, 15.8, 73.6, 74.4),
    'jharkhand': (21.9, 25.4, 83.3, 87.9),
    'chhattisgarh': (17.7, 24.1, 80.2, 84.4),
    'assam': (24.0, 28.3, 89.7, 96.1),
    'uttarakhand': (28.7, 31.5, 77.5, 81.1),
    'himachal pradesh': (30.3, 33.3, 75.5, 79.1),
    'chandigarh': (30.6, 30.8, 76.65, 76.9),
}
_STATE_ALIASES = {'nct of delhi': 'delhi', 'new delhi': 'delhi', 'orissa': 'odisha'}

# Approximate city centres, with common locality names that map onto them.
_CITY_CENTRES: dict[str, tuple[float, float]] = {
    'hyderabad': (17.3850, 78.4867),
    'mumbai': (19.0760, 72.8777),
    'pune': (18.5204, 73.8567),
    'bengaluru': (12.9716, 77.5946),
    'chennai': (13.0827, 80.2707),
    'delhi': (28.6139, 77.2090),
    'kolkata': (22.5726, 88.3639),
    'ahmedabad': (23.0225, 72.5714),
    'visakhapatnam': (17.6868, 83.2185),
    'kochi': (9.9312, 76.2673),
    'jaipur': (26.9124, 75.7873),
    'lucknow': (26.8467, 80.9462),
    'chandigarh': (30.7333, 76.7794),
}
_CITY_ALIASES = {
    'bangalore': 'bengaluru', 'bombay': 'mumbai', 'madras': 'chennai', 'calcutta': 'kolkata', 'new delhi': 'delhi',
    'secunderabad': 'hyderabad', 'kondapur': 'hyderabad', 'gachibowli': 'hyderabad', 'madhapur': 'hyderabad',
    'hitec city': 'hyderabad', 'kothaguda': 'hyderabad',
}


def _norm(name: str | None) -> str:
    return ' '.join((name or '').lower().split())


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def coordinate_errors(latitude, longitude) -> dict[str, str]:
    """Field -> message for a latitude/longitude pair that cannot be real. Empty when fine (or both absent)."""
    errors: dict[str, str] = {}
    if latitude is None and longitude is None:
        return errors
    if latitude is None or longitude is None:
        missing = 'latitude' if latitude is None else 'longitude'
        errors[missing] = 'Enter both latitude and longitude together.'
        return errors
    lat, lon = float(latitude), float(longitude)
    if not -90 <= lat <= 90:
        errors['latitude'] = 'Latitude must be between -90 and 90 degrees.'
    if not -180 <= lon <= 180:
        errors['longitude'] = 'Longitude must be between -180 and 180 degrees.'
    if not errors and lat == 0 and lon == 0:
        errors['latitude'] = 'Latitude 0, longitude 0 is not a real office location. Enter the office coordinates.'
    return errors


def location_warnings(latitude, longitude, state_name: str | None, city_name: str | None) -> list[str]:
    """Advisory messages when valid coordinates look wrong for the branch's state or city."""
    if latitude is None or longitude is None or coordinate_errors(latitude, longitude):
        return []
    lat, lon = float(latitude), float(longitude)
    warnings: list[str] = []

    state_key = _STATE_ALIASES.get(_norm(state_name), _norm(state_name))
    box = _STATE_BOXES.get(state_key)
    if box and not (box[0] <= lat <= box[1] and box[2] <= lon <= box[3]):
        warnings.append(
            f'These coordinates ({lat:.4f}, {lon:.4f}) are outside {state_name}. '
            f'Check the latitude and longitude of the office.'
        )

    city_key = _CITY_ALIASES.get(_norm(city_name), _norm(city_name))
    centre = _CITY_CENTRES.get(city_key)
    if centre:
        km = distance_km(lat, lon, centre[0], centre[1])
        if km > CITY_DISTANCE_WARNING_KM:
            warnings.append(
                f'These coordinates are about {km:.0f} km from the centre of {city_name}. '
                f'Punches from the real office will be rejected if this is wrong.'
            )
    return warnings
