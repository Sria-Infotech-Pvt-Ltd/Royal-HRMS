"""
Live address lists for the address drop-downs: states, the districts of a state, and countries.

States and districts come from the SAME PIN code dataset (`indiapins`) that answers the PIN code lookup and the district's PIN
code list, spelled the same way (views_pincode._smart_title), so a state or district chosen here always matches what a PIN
code returns, character for character. Countries come from the ISO 3166 list in `pycountry` (already in requirements.txt).
"""
from __future__ import annotations

import logging

import indiapins
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.views_pincode import STATE_LOOKUP, _closest, _smart_title
from core.responses import error, success

logger = logging.getLogger(__name__)


def list_states() -> list[str]:
    """Every state / union territory, A to Z, in this codebase's canonical spelling."""
    names = {STATE_LOOKUP.get(raw.upper(), _smart_title(raw)) for raw in indiapins.states()}
    return sorted(names, key=str.casefold)


def list_districts(state: str) -> list[str]:
    """Every district of a state, A to Z, spelled exactly as the PIN code lookup spells it. Empty for an unknown state."""
    state_name = _closest(state, indiapins.states())
    if not state_name:
        return []
    names = {_smart_title(raw) for raw in indiapins.districts_in_state(state_name)}
    return sorted(names, key=str.casefold)


def list_countries() -> list[str]:
    """Every country's common name, A to Z (ISO 3166-1)."""
    import pycountry
    names = {getattr(country, 'common_name', None) or country.name for country in pycountry.countries}
    return sorted(names, key=str.casefold)


class StateListView(APIView):
    """GET /onboarding/location/states/ — {states: [name, ...]}."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return success('OK', {'states': list_states()})
        except Exception as exc:
            logger.warning('State list failed: %s', exc)
            return error('Could not load the states right now.', http_status=status.HTTP_502_BAD_GATEWAY)


class DistrictListView(APIView):
    """GET /onboarding/location/districts/?state=<state> — {districts: [name, ...]}, empty if the state is not known."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = (request.query_params.get('state') or '').strip()[:100]
        if not state:
            return error('State is required.', http_status=status.HTTP_400_BAD_REQUEST)
        try:
            return success('OK', {'districts': list_districts(state)})
        except Exception as exc:
            logger.warning('District list failed state=%s: %s', state, exc)
            return error('Could not load the districts right now.', http_status=status.HTTP_502_BAD_GATEWAY)


class CountryListView(APIView):
    """GET /onboarding/location/countries/ — {countries: [name, ...]}."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return success('OK', {'countries': list_countries()})
        except Exception as exc:
            logger.warning('Country list failed: %s', exc)
            return error('Could not load the countries right now.', http_status=status.HTTP_502_BAD_GATEWAY)
