"""
Reverse geocoding for attendance punch locations — turns a punch's own
latitude/longitude into the fullest human-readable address Nominatim
provides (building/place, house number, road, locality, city, state,
country, postal code — whichever are available) for HR/Admin display.

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

_MAX_LABEL_LENGTH = 255  # AttendancePunch.location_label's max_length

# Named building / apartment / complex / place keys Nominatim may return in the
# address breakdown even when the matched object itself has no name.
_PLACE_KEYS = (
    'building', 'residential', 'amenity', 'shop', 'office', 'tourism', 'leisure',
    'commercial', 'industrial', 'retail', 'craft', 'man_made', 'historic',
)
# Locality components, all kept when present (duplicates are dropped below).
_LOCALITY_KEYS = ('hamlet', 'neighbourhood', 'suburb', 'quarter')
_CITY_KEYS = ('city', 'town', 'village', 'municipality', 'county')


def _fit_to_length(parts: list[str]) -> str:
    """Join whole components while they fit, so a long address never splits mid-word."""
    label = ''
    for part in parts:
        candidate = f'{label}, {part}' if label else part
        if len(candidate) > _MAX_LABEL_LENGTH:
            break
        label = candidate
    return label or parts[0][:_MAX_LABEL_LENGTH]


def reverse_geocode(latitude: float, longitude: float) -> str | None:
    """
    Returns the fullest address Nominatim provides, in the order: building or
    place name, house number, road, locality, city, state, country, postal
    code — e.g. "B3, Palanpur Road, Adajan, Surat, Gujarat, India, 395009".
    Returns None on any failure (timeout, rate limit, no result, bad
    coordinates) — callers must treat None as "leave location_label empty",
    never as an error to raise. Never fabricates a missing component: pieces
    Nominatim doesn't return are simply omitted, not guessed; a component that
    repeats an earlier one is dropped.
    """
    try:
        resp = requests.get(
            _NOMINATIM_REVERSE_URL,
            params={
                'format': 'jsonv2',
                'lat': f'{latitude:.8f}',
                'lon': f'{longitude:.8f}',
                'zoom': 18,  # building level — finer detail, still one request per punch
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

    candidates = [
        data.get('name'),
        address.get('house_name'),
        *(address.get(k) for k in _PLACE_KEYS),
        address.get('house_number'),
        address.get('road'),
        *(address.get(k) for k in _LOCALITY_KEYS),
        next((address[k] for k in _CITY_KEYS if address.get(k)), None),
        address.get('state'),
        address.get('country'),
        address.get('postcode'),
    ]
    parts, seen = [], set()
    for value in candidates:
        text = str(value).strip() if value is not None else ''
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            parts.append(text)
    if not parts:
        return None
    return _fit_to_length(parts)
