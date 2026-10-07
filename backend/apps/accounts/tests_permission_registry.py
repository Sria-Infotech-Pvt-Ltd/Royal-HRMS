"""
Phase 4 Task A.2 — scans the actual source tree for every literal
`has_perm('module.action')` call and asserts the codename exists in the
database. Re-scans live source on every run rather than trusting a
hand-maintained list, so it can never silently drift (see
permissions_registry.py's own docstring for why a hand-typed diff list
was deliberately NOT built instead).
"""
from __future__ import annotations

import pathlib
import re

from django.test import TestCase

from apps.accounts.models import Permission

_HAS_PERM_LITERAL_RE = re.compile(r"has_perm\(\s*[^,]+,\s*['\"]([a-zA-Z0-9_.]+)['\"]\s*\)")
_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]  # .../backend


def _scan_literal_codenames() -> set[str]:
    codenames = set()
    for py_file in _BACKEND_ROOT.rglob('*.py'):
        if any(part in {'migrations', '__pycache__', 'H'} for part in py_file.parts):
            continue
        try:
            text = py_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for match in _HAS_PERM_LITERAL_RE.finditer(text):
            codenames.add(match.group(1))
    return codenames


class PermissionRegistryScanTests(TestCase):
    def test_every_literal_has_perm_codename_exists_in_db(self):
        literal_codenames = _scan_literal_codenames()
        self.assertTrue(literal_codenames, 'The scan found zero has_perm(...) literals — the regex or root path is probably wrong, not that there are none.')

        known_codenames = set(Permission.objects.values_list('codename', flat=True))
        # settings.edit is the one deliberately-hidden universal bypass
        # (Task D is replacing it, not removing it) — always expected to exist.
        missing = literal_codenames - known_codenames
        self.assertEqual(missing, set(), f'has_perm() call sites reference codenames with no matching Permission row: {sorted(missing)}')
