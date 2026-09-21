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
