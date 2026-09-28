"""
IFSC -> Bank/Branch lookup, used by the onboarding wizard's Bank Details
step (both self-service and HR-assisted, plus the Hire wizard's Statutory
& accounts step) to auto-fill Bank name/Branch once a valid 11-character
IFSC code is entered, instead of asking for both separately — same
"don't make the user type what a code already implies" pattern
views_pincode.py already established for PIN code -> District/State.

Calls Razorpay's public IFSC lookup API (ifsc.razorpay.com) — no API key,
no rate-limit auth required, backed by the RBI's published IFSC master
list. Proxied through this backend endpoint (rather than called directly
from the browser) for the same reason PincodeLookupView proxies its own
lookup: keeps this a same-origin call (no CORS handling needed client-side)
and centralizes the one place this integration can ever need to change.
"""
from __future__ import annotations

import logging
import re

import requests
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

logger = logging.getLogger(__name__)

IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
_IFSC_LOOKUP_URL = 'https://ifsc.razorpay.com/{code}'
_REQUEST_TIMEOUT_SECONDS = 5


class IfscLookupView(APIView):
    """GET /onboarding/ifsc-lookup/<code>/ — {bank, branch, address, city, state} for a valid IFSC code."""
    permission_classes = [IsAuthenticated]

    def get(self, request, ifsc):
        code = (ifsc or '').strip().upper()
        if not IFSC_RE.match(code):
            return error('Enter a valid 11-character IFSC code.', http_status=status.HTTP_400_BAD_REQUEST)

        try:
            resp = requests.get(_IFSC_LOOKUP_URL.format(code=code), timeout=_REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.warning('IFSC lookup network failure code=%s: %s', code, exc)
            return error('Could not look up this IFSC code right now.', http_status=status.HTTP_502_BAD_GATEWAY)

        if resp.status_code == 404:
            return error('No bank found for this IFSC code.', http_status=status.HTTP_404_NOT_FOUND)
        if resp.status_code != 200:
            logger.warning('IFSC lookup unexpected status code=%s status=%s', code, resp.status_code)
            return error('Could not look up this IFSC code right now.', http_status=status.HTTP_502_BAD_GATEWAY)

        try:
            data = resp.json()
        except ValueError:
            return error('Could not look up this IFSC code right now.', http_status=status.HTTP_502_BAD_GATEWAY)

        return success('OK', {
            'bank':    data.get('BANK', ''),
            'branch':  data.get('BRANCH', ''),
            'address': data.get('ADDRESS', ''),
            'city':    data.get('CITY', ''),
            'state':   data.get('STATE', ''),
        })
