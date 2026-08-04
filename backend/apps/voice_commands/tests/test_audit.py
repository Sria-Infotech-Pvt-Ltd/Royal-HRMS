"""
apps.voice_commands.audit wires permission-denial and no-match/low-confidence
voice events into the real audit trail (apps.accounts.models.AuditLog — the
same table AuditLogListView/the /dashboard/audit page read for every other
app's security-relevant events), plus a count-based threshold that flags
unusual volume from one user. Uses real TestCase + DB + real users (via
apps.accounts.factories) rather than the MagicMock-request pattern the rest
of this test package uses — an actual AuditLog row is the entire point here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.voice_commands.audit import (
    ACTION_NO_MATCH,
    ACTION_PERMISSION_DENIED,
    ACTION_UNUSUAL_ACTIVITY,
    ANOMALY_THRESHOLD,
    MODULE,
    log_no_match,
    log_permission_denied,
)
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import execute_intent

_api_request_factory = APIRequestFactory()

_FAKE_INTENT = '__test_only_gated_intent__'
_FAKE_PERMISSION = 'voice_test.fake_permission'


def _authenticated_request(user):
    request = _api_request_factory.post('/api/voice/parse/', {}, format='json')
    force_authenticate(request, user=user)
    request.user = user
    return request


class PermissionDeniedAuditTests(TestCase):
    def setUp(self):
        self.role = make_role('employee')
        self.user = make_user('employee@test.com', role=self.role)

    @patch('apps.voice_commands.executor.has_required_permission')
    @patch('apps.voice_commands.executor.get_required_permission')
    def test_permission_denied_writes_an_audit_log_row(self, mock_get_required, mock_has_permission):
        mock_get_required.return_value = _FAKE_PERMISSION
        mock_has_permission.return_value = False
        request = _authenticated_request(self.user)

        result = execute_intent(_FAKE_INTENT, request)

        self.assertFalse(result.success)
        row = AuditLog.objects.get(user=self.user, action=ACTION_PERMISSION_DENIED, module=MODULE)
        self.assertEqual(row.changes['intent'], _FAKE_INTENT)
        self.assertEqual(row.changes['required_permission'], _FAKE_PERMISSION)

    @patch('apps.voice_commands.executor.has_required_permission')
    @patch('apps.voice_commands.executor.get_required_permission')
    def test_permission_granted_writes_no_audit_log_row(self, mock_get_required, mock_has_permission):
        mock_get_required.return_value = _FAKE_PERMISSION
        mock_has_permission.return_value = True
        request = _authenticated_request(self.user)

        execute_intent(_FAKE_INTENT, request)

        self.assertFalse(AuditLog.objects.filter(user=self.user, action=ACTION_PERMISSION_DENIED).exists())


class NoMatchAuditTests(TestCase):
    def setUp(self):
        self.role = make_role('employee')
        self.user = make_user('employee2@test.com', role=self.role)

    def test_flat_no_match_writes_an_audit_log_row(self):
        request = _authenticated_request(self.user)

        handle_transcript(request, 'what is the weather today in paris')

        row = AuditLog.objects.get(user=self.user, action=ACTION_NO_MATCH, module=MODULE)
        self.assertEqual(row.changes['transcript'], 'what is the weather today in paris')
        self.assertIsNone(row.changes['candidate_intent'])

    def test_did_you_mean_candidate_also_writes_an_audit_log_row(self):
        """The clarification band (a candidate_intent offered, still
        NO_MATCH_INTENT) is a low-confidence event too, not just a flat
        no-match — both must reach the audit trail."""
        request = _authenticated_request(self.user)

        handle_transcript(request, 'raise a queryAbout my Paisley')

        row = AuditLog.objects.get(user=self.user, action=ACTION_NO_MATCH, module=MODULE)
        self.assertEqual(row.changes['candidate_intent'], 'raise_payslip_query')

    def test_confident_match_writes_no_no_match_audit_row(self):
        request = _authenticated_request(self.user)

        with patch('apps.voice_commands.conversation.execute_intent') as mock_execute:
            from apps.voice_commands.executor_result import ExecutionResult
            mock_execute.return_value = ExecutionResult(success=True, message='ok')
            handle_transcript(request, 'check my leave balance')

        self.assertFalse(AuditLog.objects.filter(user=self.user, action=ACTION_NO_MATCH).exists())


class AnomalyThresholdTests(TestCase):
    def setUp(self):
        self.role = make_role('employee')
        self.user = make_user('employee3@test.com', role=self.role)
        self.request = _authenticated_request(self.user)

    def test_flags_only_once_the_threshold_is_reached(self):
        for _ in range(ANOMALY_THRESHOLD - 1):
            log_no_match(self.request, 'gibberish', 10.0, None)
        self.assertFalse(
            AuditLog.objects.filter(user=self.user, action=ACTION_UNUSUAL_ACTIVITY).exists()
        )

        with self.assertLogs('apps.voice_commands.audit', level='WARNING'):
            log_no_match(self.request, 'gibberish', 10.0, None)

        unusual = AuditLog.objects.get(user=self.user, action=ACTION_UNUSUAL_ACTIVITY, module=MODULE)
        self.assertEqual(unusual.changes['event_count'], ANOMALY_THRESHOLD)

    def test_does_not_flag_again_until_the_next_multiple(self):
        for _ in range(ANOMALY_THRESHOLD):
            log_no_match(self.request, 'gibberish', 10.0, None)
        self.assertEqual(
            AuditLog.objects.filter(user=self.user, action=ACTION_UNUSUAL_ACTIVITY).count(), 1,
        )

        # One more event (still short of the next multiple) must not flag again.
        log_no_match(self.request, 'gibberish', 10.0, None)
        self.assertEqual(
            AuditLog.objects.filter(user=self.user, action=ACTION_UNUSUAL_ACTIVITY).count(), 1,
        )

    def test_mixed_permission_denied_and_no_match_events_both_count_toward_the_threshold(self):
        for _ in range(ANOMALY_THRESHOLD - 1):
            log_permission_denied(self.request, 'some_intent', 'some.codename')
        log_no_match(self.request, 'gibberish', 10.0, None)

        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action=ACTION_UNUSUAL_ACTIVITY).exists()
        )


class AuditFailureIsolationTests(TestCase):
    """The audit write is a side effect, never a precondition — a broken
    request double (or a real DB hiccup) must not turn an otherwise-normal
    response into a crash. Mirrors the request-double pattern the rest of
    this test package's SimpleTestCase suites use."""

    def test_a_non_user_request_double_does_not_raise(self):
        request = MagicMock()
        request.META = {}
        request.user = MagicMock()  # not a real User instance — AuditLog.user assignment would fail
        request.user.is_authenticated = True

        with self.assertLogs('apps.voice_commands.audit', level='ERROR'):
            log_no_match(request, 'gibberish', 10.0, None)  # must not raise
