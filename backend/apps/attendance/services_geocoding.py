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
from django.conf import settings

logger = logging.getLogger(__name__)

_NOMINATIM_REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse'
_GOOGLE_REVERSE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
_USER_AGENT ='RoyalHRMS-AttendanceGeocoder/1.0'
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


def _google_reverse_geocode(latitude: float, longitude: float, api_key: str) -> str | None:
    """
    Google Geocoding API reverse lookup. Returns the formatted_address of the
    most precise result, or None on any failure (bad status, quota, timeout,
    no usable result). Plus-code-only results are skipped — they are not an
    address a person can read.
    """
    try:
        resp = requests.get(
            _GOOGLE_REVERSE_URL,
            params={
                'latlng': f'{latitude:.8f},{longitude:.8f}',
                'key': api_key,
                'language': 'en',
                # Most precise address types only; Google falls back to
                # coarser results when none of these exist.
                'result_type': 'street_address|premise|subpremise|route',
            },
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get('status')
        if status == 'ZERO_RESULTS':
            # Retry without the result_type filter so rural/coarse points still
            # get a locality-level address instead of nothing.
            resp = requests.get(
                _GOOGLE_REVERSE_URL,
                params={'latlng': f'{latitude:.8f},{longitude:.8f}', 'key': api_key, 'language': 'en'},
                timeout=_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get('status')
        if status != 'OK':
            # Never log the key; status + Google's message are enough to debug.
            logger.warning('Google reverse geocode status=%s: %s', status, data.get('error_message', ''))
            return None
    except Exception as exc:
        # str(exc) from requests can embed the request URL (which carries the key).
        logger.warning('Google reverse geocode failed for (%s, %s): %s', latitude, longitude, type(exc).__name__)
        return None

    for result in data.get('results') or []:
        types = result.get('types') or []
        address = (result.get('formatted_address') or '').strip()
        if address and types != ['plus_code']:
            return address[:_MAX_LABEL_LENGTH]
    return None


def reverse_geocode(latitude: float, longitude: float) -> str | None:
    """
    Uses Google when GOOGLE_MAPS_API_KEY is set (falling back to Nominatim if
    Google returns nothing); otherwise Nominatim only. Never raises.
    """
    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or ''
    if api_key:
        label = _google_reverse_geocode(latitude, longitude, api_key)
        if label:
            return label
    return _nominatim_reverse_geocode(latitude, longitude)


def _nominatim_reverse_geocode(latitude: float, longitude: float) -> str | None:
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
