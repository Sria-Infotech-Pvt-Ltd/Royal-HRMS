"""Keeps each state's City list complete for the Company Code form.

The `branch_cities` table was filled once with a short list of well-known towns per state (13 for Telangana, which has 33 districts),
so the City drop-down offered only those. The address screens already have every district of every state (the bundled PIN code
dataset, `apps.accounts.views_location.list_districts`). `ensure_state_districts` adds the districts a state is missing, so the
drop-down offers the towns that were already there plus every district.

It only ever ADDS rows. A city that already exists (active or switched off) is never changed or removed, and a district whose
name is a near-copy of an existing city ("Mahabubnagar" / "Mahbubnagar") is not added a second time, so branches already linked
to a city are untouched and no duplicates appear.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from functools import lru_cache

from apps.branch.models import City, State

logger = logging.getLogger(__name__)

# Two spellings this alike (ignoring case, spaces and punctuation) are treated as the same place.
NEAR_DUPLICATE_RATIO = 0.9
CITY_NAME_MAX_LENGTH = 100


def _key(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.casefold())


@lru_cache(maxsize=64)
def _official_districts(state_name: str) -> tuple[str, ...]:
    from apps.accounts.views_location import list_districts
    return tuple(list_districts(state_name))


def _is_listed(name: str, known_keys: set[str]) -> bool:
    key = _key(name)
    if not key:
        return True    # nothing usable in the name: skip it
    return any(key == known or SequenceMatcher(None, key, known).ratio() >= NEAR_DUPLICATE_RATIO for known in known_keys)


def ensure_state_districts(state: State) -> int:
    """Add the state's missing districts as cities; returns how many were added. Never raises: the list just stays as it was."""
    try:
        districts = _official_districts(state.name)
    except Exception as exc:    # the dataset must never break the drop-down
        logger.warning('District list unavailable for state=%s: %s', state.name, exc)
        return 0
    if not districts:
        return 0

    known_keys = {_key(name) for name in City.objects.filter(state=state).values_list('name', flat=True)}
    added = 0
    for name in districts:
        if _is_listed(name, known_keys):
            continue
        _, was_created = City.objects.get_or_create(name=name[:CITY_NAME_MAX_LENGTH], state=state, defaults={'is_active': True})
        known_keys.add(_key(name))
        added += int(was_created)
    if added:
        logger.info('Added %d districts as cities for state=%s', added, state.name)
    return added
