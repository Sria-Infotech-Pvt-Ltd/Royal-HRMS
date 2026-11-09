"""Tests for the read-only `face_clockin_report` management command."""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.attendance.models import FaceCaptureTelemetry, FaceVerificationAttempt


def _run(*args: str) -> str:
    out = StringIO()
    call_command('face_clockin_report', *args, stdout=out)
    return out.getvalue()


def _telemetry(user, **overrides) -> FaceCaptureTelemetry:
    base = {
        'employee': user, 'purpose': 'verify', 'outcome': 'captured', 'duration_ms': 6000,
        'tf_backend': 'webgl', 'avg_fps': 15.0, 'user_agent': 'Mozilla/5.0 (Windows NT 10.0)',
        'details': {},
    }
    base.update(overrides)
    return FaceCaptureTelemetry.objects.create(**base)


def _attempt(user, *, is_match=True, distance=0.3, reason='') -> FaceVerificationAttempt:
    return FaceVerificationAttempt.objects.create(
        employee=user, source='web', embedding_fingerprint='f' * 64,
        is_match=is_match, distance=distance, rejection_reason=reason,
    )


class FaceClockinReportTests(TestCase):
    def setUp(self):
        self.user = make_user('report-a@test.com', employee_id='EMP-RPT-1', full_name='Secret Person')

    def test_empty_database_reports_no_data_without_error(self):
        out = _run()
        self.assertIn('No telemetry yet', out)
        self.assertIn('No attempts in this window.', out)

    def test_telemetry_summary_figures(self):
        _telemetry(self.user)                                                   # first try
        _telemetry(self.user, manual_retries=2, duration_ms=14000,
                   user_agent='Mozilla/5.0 (Linux; Android 14)',
                   details={'failure_reasons': {'too_dark': 4}, 'liveness_timeouts': 1})
        _telemetry(self.user, outcome='cancelled')
        out = _run()
        self.assertIn('Sessions:                3', out)
        self.assertIn('Ended in a capture:      2 (66.7%)', out)
        self.assertIn('First-try success:       50.0% of captures', out)
        self.assertIn('BELOW TARGET', out)
        self.assertIn('Needed 3+ tries:         50.0%', out)
        self.assertIn('too_dark: 4', out)
        self.assertIn('timeouts=1', out)
        self.assertIn('Windows: 100.0% of 1', out)
        self.assertIn('Android: 0.0% of 1', out)

    def test_register_sessions_and_old_rows_are_excluded(self):
        _telemetry(self.user, purpose='register')
        old = _telemetry(self.user)
        FaceCaptureTelemetry.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))
        self.assertIn('No telemetry yet', _run())

    def test_weak_reference_flagged_by_employee_id_only(self):
        for dist in (0.52, 0.55, 0.58):
            _attempt(self.user, distance=dist)
        strong = make_user('report-b@test.com', employee_id='EMP-RPT-2')
        for dist in (0.2, 0.25, 0.3):
            _attempt(strong, distance=dist)
        _attempt(self.user, is_match=False, distance=0.57, reason='low_confidence_pending')
        out = _run()
        self.assertIn('Attempts: 7, matched: 6', out)
        self.assertIn('EMP-RPT-1: median=0.550', out)
        self.assertNotIn('EMP-RPT-2:', out)
        self.assertIn('low_conf_rejects=1', out)
        # privacy: no name or email in the output
        self.assertNotIn('Secret Person', out)
        self.assertNotIn('report-a@test.com', out)

    def test_min_attempts_and_lockout_count(self):
        _attempt(self.user, distance=0.58)
        _attempt(self.user, distance=0.59)                      # only 2 matched < default 3
        _attempt(self.user, is_match=False, distance=None, reason='attempt_cap_exceeded')
        out = _run()
        self.assertNotIn('EMP-RPT-1: median', out)
        self.assertIn('hit the failed-attempt lockout in this window: 1', out)
        self.assertIn('EMP-RPT-1: median', _run('--min-attempts', '2'))

    def test_command_is_read_only(self):
        _telemetry(self.user)
        _attempt(self.user)
        before = (FaceCaptureTelemetry.objects.count(), FaceVerificationAttempt.objects.count())
        _run('--days', '7', '--weak-median', '0.4')
        self.assertEqual(before, (FaceCaptureTelemetry.objects.count(), FaceVerificationAttempt.objects.count()))
