"""
Phase 7.4: the Face consent version has ONE source of truth - apps.attendance.models.FACE_CONSENT_TEXT_VERSION.

The frontend holds the consent WORDING only (frontend/lib/faceApi/consentText.ts) and has no version constant: the server
stamps the version on every new registration, the browser never sends it. What could still drift is the wording changing
without the version being bumped, so this module pins a hash of the wording to each version. Changing the wording makes
`test_wording_matches_the_hash_pinned_for_the_current_version` fail until the version is bumped AND the new hash is added
below - older versions stay in the table, so an old registration's stored version still maps to the wording it agreed to.

Stamping itself (new self-service and HR registrations record the current version, v1 rows are untouched) is proven
against the real endpoints in tests_face_registration.py and tests_face_mode_matrix.py::ConsentVersionContractTests.
These tests need no database.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.attendance import models as attendance_models
from apps.attendance.models import FACE_CONSENT_TEXT_VERSION

_BACKEND_ROOT = Path(attendance_models.__file__).resolve().parents[2]
_CONSENT_TS = _BACKEND_ROOT.parent / 'frontend' / 'lib' / 'faceApi' / 'consentText.ts'

# version -> sha256 of "<employee notice>\n<HR notice>" exactly as written in consentText.ts.
# To change the wording: bump FACE_CONSENT_TEXT_VERSION in models.py, then ADD a row here (never edit an old one).
PINNED_WORDING_SHA256 = {
    'v2': '6e6e438d76a0578493899c9c57a979251c39013baf73b1b3acf0a0ba1d783660',
}


def _notice(source: str, name: str) -> str:
    match = re.search(r'export const ' + name + r'\s*=\s*(.*?);', source, re.S)
    assert match, f'{name} not found in consentText.ts'
    return ''.join(re.findall(r'"([^"]*)"', match.group(1)))


def _wording_hash() -> str:
    source = _CONSENT_TS.read_text(encoding='utf8')
    text = _notice(source, 'FACE_CONSENT_NOTICE_EMPLOYEE') + '\n' + _notice(source, 'FACE_CONSENT_NOTICE_HR')
    return hashlib.sha256(text.encode('utf8')).hexdigest()


class ConsentVersionSingleSourceTests(SimpleTestCase):
    def test_the_current_version_is_the_one_the_wording_was_pinned_under(self):
        self.assertEqual(FACE_CONSENT_TEXT_VERSION, 'v2')
        self.assertIn(FACE_CONSENT_TEXT_VERSION, PINNED_WORDING_SHA256)

    def test_wording_matches_the_hash_pinned_for_the_current_version(self):
        self.assertEqual(
            _wording_hash(), PINNED_WORDING_SHA256[FACE_CONSENT_TEXT_VERSION],
            'The consent wording in frontend/lib/faceApi/consentText.ts changed. Bump FACE_CONSENT_TEXT_VERSION in '
            'apps/attendance/models.py and add the new hash for the new version to PINNED_WORDING_SHA256.',
        )

    def test_the_frontend_has_no_second_copy_of_the_version(self):
        source = _CONSENT_TS.read_text(encoding='utf8')
        self.assertNotIn('FACE_CONSENT_TEXT_VERSION', re.sub(r'//.*', '', source))  # comments may mention it; code may not
        self.assertNotRegex(re.sub(r'//.*', '', source), r'["\']v\d+["\']')

    def test_both_registration_endpoints_stamp_the_shared_constant_not_a_literal(self):
        for relative in ('views/face_registration.py', 'views/face_registration_hr.py'):
            with self.subTest(relative):
                source = (_BACKEND_ROOT / 'apps' / 'attendance' / relative).read_text(encoding='utf8')
                self.assertIn('consent_text_version=FACE_CONSENT_TEXT_VERSION', source)
                self.assertRegex(source, r'import[^\n]*\n?[^\n]*FACE_CONSENT_TEXT_VERSION|FACE_CONSENT_TEXT_VERSION,')

    def test_no_backend_code_writes_a_hard_coded_consent_version(self):
        offenders = []
        for path in (_BACKEND_ROOT / 'apps').rglob('*.py'):
            relative = path.relative_to(_BACKEND_ROOT).as_posix()
            if '/migrations/' in relative or 'tests' in path.name or '/tests/' in relative:
                continue
            for number, line in enumerate(path.read_text(encoding='utf8').splitlines(), start=1):
                if re.search(r"consent_text_version\s*=\s*['\"]v\d+['\"]", line):
                    offenders.append(f'{relative}:{number}')
        self.assertEqual(offenders, [], 'consent_text_version must come from FACE_CONSENT_TEXT_VERSION')

    def test_the_model_field_has_no_choices_so_old_versions_stay_valid(self):
        field = attendance_models.FaceRegistrationRequest._meta.get_field('consent_text_version')
        self.assertFalse(field.choices)
        self.assertEqual(field.max_length, 20)
