"""
PIN code -> District/State lookup, used by the onboarding wizard's address
fields (both self-service and HR-assisted) to auto-fill District/State once
a 6-digit PIN code is entered, instead of asking for all three separately.

Originally called the free India Post PIN code API (api.postalpincode.in)
over HTTP, but that dataset still carries pre-2016 district boundaries for
several states (e.g. pincode 509152 comes back as "Mahabub Nagar" even
though that PIN was moved into the newly-carved Jogulamba Gadwal district
in 2016) — confirmed live, not a one-off. Switched to the `indiapins`
package instead: a local, offline lookup table (no network call, so no
CORS/User-Agent issues either) that's kept current with district
reorganizations — same pincode above correctly returns "Jogulamba Gadwal".
"""
from __future__ import annotations

import difflib
import logging
import re

import indiapins
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

logger = logging.getLogger(__name__)

PINCODE_RE = re.compile(r'^\d{6}$')

# Same 36 India states/UTs the address dropdown itself uses
# (0130_seed_address_field_configs.py's STATES / frontend's company address
# STATES list) — indiapins returns state names in all caps, so this maps
# back to this codebase's exact canonical spelling/capitalization (matters
# for the State <select>, whose <option> values must match exactly).
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
STATE_LOOKUP = {s.upper(): s for s in STATES}

_LOWERCASE_WORDS = {'and', 'of'}


def _smart_title(text: str) -> str:
    """Title-case, but keep small connector words lowercase (except as the
    first word) — plain str.title() would turn "Jammu and Kashmir" into
    "Jammu And Kashmir"."""
    words = text.strip().split()
    return ' '.join(
        w.lower() if i > 0 and w.lower() in _LOWERCASE_WORDS else w.capitalize()
        for i, w in enumerate(words)
    )


_OFFICE_SUFFIX_RE = re.compile(r'\s+[SHB]\.?O\.?$', re.IGNORECASE)


def _locality_from_office_name(name: str) -> str:
    """indiapins' `Name` is the post office name (e.g. "Cyberabad S.O",
    "Kondapur B.O") — a real, genuine locality/area name for the PIN code,
    just with the postal Sub/Head/Branch Office suffix stripped so it reads
    as a place name rather than a post-office record."""
    return _smart_title(_OFFICE_SUFFIX_RE.sub('', name or '').strip())


def lookup_pincode(pincode: str) -> dict | None:
    """{locality, district, state} for a valid Indian PIN code, or None when it is malformed or unknown. Never raises."""
    if not PINCODE_RE.match(pincode or ''):
        return None
    try:
        match = indiapins.matching(pincode)[0]
    except (ValueError, IndexError):
        return None
    except Exception as exc:
        logger.warning('Pincode lookup failed pincode=%s: %s', pincode, exc)
        return None
    raw_state = (match.get('State') or '').strip()
    return {
        'locality': _locality_from_office_name(match.get('Name', '')),
        'district': _smart_title(match.get('District', '')),
        'state': STATE_LOOKUP.get(raw_state.upper(), _smart_title(raw_state)),
    }


def fill_state_and_district(profile_fields: dict) -> None:
    """Hire completion: where an address has a PIN code but no State/District, derive them from the PIN. Anything the person
    entered is left alone (pre-fill only), and an unknown PIN changes nothing."""
    for prefix in ('current', 'permanent'):
        location = lookup_pincode(str(profile_fields.get(f'{prefix}_pin_code') or '').strip())
        if not location:
            continue
        if not profile_fields.get(f'{prefix}_state') and location['state']:
            profile_fields[f'{prefix}_state'] = location['state']
        if not profile_fields.get(f'{prefix}_district') and location['district']:
            profile_fields[f'{prefix}_district'] = location['district']


class PincodeLookupView(APIView):
    """GET /onboarding/pincode-lookup/<pincode>/ — {locality, district, state} for a valid Indian PIN code."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pincode):
        if not PINCODE_RE.match(pincode):
            return error('Enter a valid 6-digit PIN code.', http_status=status.HTTP_400_BAD_REQUEST)

        try:
            match = indiapins.matching(pincode)[0]
        except (ValueError, IndexError):
            return error('No location found for this PIN code.', http_status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.warning('Pincode lookup failed pincode=%s: %s', pincode, exc)
            return error('Could not look up this PIN code right now.', http_status=status.HTTP_502_BAD_GATEWAY)

        district = _smart_title(match.get('District', ''))
        raw_state = (match.get('State') or '').strip()
        state = STATE_LOOKUP.get(raw_state.upper(), _smart_title(raw_state))
        locality = _locality_from_office_name(match.get('Name', ''))
        return success('OK', {'locality': locality, 'district': district, 'state': state})


# ── All PIN codes in one district (the address form's PIN code drop-down) ─────────────────────────────────────────────
def _normalise(text: str) -> str:
    """Lower-case letters and digits only, one space between words, so "Medchal–Malkajgiri" and "MEDCHAL MALKAJGIRI" are the same."""
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()


def _closest(wanted: str, candidates: list):
    """The candidate that is the same name written another way: exactly, or after normalising, or by a close spelling (the PIN
    dataset writes some districts differently, e.g. "Jangoan" for Jangaon, "Jagitial" for Jagtial)."""
    key = _normalise(wanted)
    if not key:
        return None
    by_key = {_normalise(candidate): candidate for candidate in candidates}
    if key in by_key:
        return by_key[key]
    close = difflib.get_close_matches(key, list(by_key), n=1, cutoff=0.8)
    return by_key[close[0]] if close else None


def pincodes_for_district(state: str, district: str) -> list:
    """[{'pincode', 'area'}] for every PIN code in that district of that state, lowest first. Empty when the state or district is not
    known to the PIN dataset. Never raises."""
    try:
        state_name = _closest(state, indiapins.states())
        if not state_name:
            return []
        district_name = _closest(district, indiapins.districts_in_state(state_name))
        if not district_name:
            return []
        in_state = set(indiapins.pincodes_in_state(state_name))
        pincodes = sorted(code for code in indiapins.pincodes_in_district(district_name) if code in in_state)
        rows = []
        for code in pincodes:
            try:
                area = _locality_from_office_name(indiapins.matching(code)[0].get('Name', ''))
            except (ValueError, IndexError):
                area = ''
            rows.append({'pincode': code, 'area': area})
        return rows
    except Exception as exc:
        logger.warning('PIN codes for district failed state=%s district=%s: %s', state, district, exc)
        return []


class PincodesInDistrictView(APIView):
    """GET /onboarding/pincodes/?state=<state>&district=<district> — {pincodes: [{pincode, area}]}, empty if not known."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = (request.query_params.get('state') or '').strip()[:100]
        district = (request.query_params.get('district') or '').strip()[:100]
        if not state or not district:
            return error('Both state and district are required.', http_status=status.HTTP_400_BAD_REQUEST)
        return success('OK', {'pincodes': pincodes_for_district(state, district)})
