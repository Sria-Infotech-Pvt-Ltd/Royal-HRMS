"""
Reverse geocoding for attendance punch locations — turns a punch's own
latitude/longitude into a short human-readable "City, State, Country" (or
finer, when available) label for HR/Admin display.

Provider: OpenStreetMap Nominatim public API — free, no API key/signup, no
new dependency (uses the `requests` library already in this project).
Chosen because this app had no geocoding integration of any kind before this
(see apps/hrms/models.py's WorkFromHomeRequest docstring) and Nominatim is
the only option that needs no new credential/billing setup to add.

Usage policy (https://operations.osmfoundation.org/policies/nominatim/):
  - Max ~1 request/second — this module does not queue/throttle across
    processes; at real punch volume a handful of 429s are expected and are
    just swallowed (see reverse_geocode()'s docstring) rather than engineered
    around, since this is best-effort enrichment, not a core feature.
  - A meaningful User-Agent identifying the application is required.
  - Results are for display only here — never used for any attendance
    calculation or validation, so Nominatim's redistribution/caching terms
    for bulk use don't apply to this single-lookup-per-punch usage.

Never called from the employee-facing punch request — see
apps.attendance.tasks.reverse_geocode_punch_task, dispatched fire-and-forget
after the punch is already committed (PunchService.record_punch()).
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_NOMINATIM_REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse'
_USER_AGENT = 'RoyalHRMS-AttendanceGeocoder/1.0'
_TIMEOUT_SECONDS = 5

# Preferred level of locality detail, finest first — the first one present
# in Nominatim's address breakdown is used as the "area" component.
_AREA_KEYS = ('road', 'neighbourhood', 'suburb')
_CITY_KEYS = ('city', 'town', 'village', 'municipality', 'county')


def reverse_geocode(latitude: float, longitude: float) -> str | None:
    """
    Returns a short label like "Hyderabad, Telangana, India" (or, when a
    finer locality is available, "Banjara Hills, Hyderabad, Telangana,
    India"), or None on any failure (timeout, rate limit, no result, bad
    coordinates) — callers must treat None as "leave location_label empty",
    never as an error to raise. Never fabricates a missing component: pieces
    Nominatim doesn't return are simply omitted, not guessed.
    """
    try:
        resp = requests.get(
            _NOMINATIM_REVERSE_URL,
            params={
                'format': 'jsonv2',
                'lat': f'{latitude:.8f}',
                'lon': f'{longitude:.8f}',
                'zoom': 14,
                'addressdetails': 1,
            },
            headers={'User-Agent': _USER_AGENT},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.info('Reverse geocode failed for (%s, %s): %s', latitude, longitude, exc)
        return None

    address = data.get('address') or {}
    if not address:
        return None

    area = next((address[k] for k in _AREA_KEYS if address.get(k)), None)
    city = next((address[k] for k in _CITY_KEYS if address.get(k)), None)
    state = address.get('state') or ''
    country = address.get('country') or ''

    parts = [p for p in (area, city, state, country) if p]
    if not parts:
        return None
    label = ', '.join(parts)
    return label[:255]  # matches AttendancePunch.location_label's max_length
