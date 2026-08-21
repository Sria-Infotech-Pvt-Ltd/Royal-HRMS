"""
Functional Hindi-vs-English selection — one representative, cheaply-mockable
call per executor module touched in Phase 3 (executor.py's own shared
messages, plus all five domain executors), confirming
apps.voice_commands.language.set_current_language() actually changes what
text the FUNCTION returns, not just that the underlying `{'en','hi'}` dicts
are well-formed (see test_executor_hindi_strings.py for that half).

Each test sets the language, calls the executor function with just enough
mocking to reach the message under test without touching a real database,
and asserts on the exact Hindi or English string.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import (
    executor,
    executor_approval,
    executor_attendance,
    executor_greeting,
    executor_leave,
    executor_payroll,
    language,
)


class _LanguageIsolatedTestCase(SimpleTestCase):
    """Every test in this file starts from English — a Hindi value left set
    by one test (or by an earlier file in the same process) must never leak
    into the next."""

    def setUp(self):
        super().setUp()
        language.set_current_language(language.LANG_EN)

    def tearDown(self):
        language.set_current_language(language.LANG_EN)
        super().tearDown()


class ExecutorSharedMessagesTests(_LanguageIsolatedTestCase):
    def test_unrecognized_intent_falls_back_to_english_by_default(self):
        result = executor.execute_intent('__totally_unknown_intent__', MagicMock())
        self.assertEqual(result.message, "I didn't understand that command.")

    def test_unrecognized_intent_falls_back_to_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        result = executor.execute_intent('__totally_unknown_intent__', MagicMock())
        self.assertEqual(result.message, 'मुझे यह कमांड समझ नहीं आया।')


class GreetingExecutorTests(_LanguageIsolatedTestCase):
    @staticmethod
    def _fake_request():
        return SimpleNamespace(user=SimpleNamespace(full_name='Priya Sharma', email='priya@example.com'))

    def test_greeting_is_english_by_default(self):
        result = executor_greeting.execute_greeting(self._fake_request())
        self.assertTrue(result.message.startswith('Hi, Priya Sharma, good '))
        self.assertIn('How can I help you today?', result.message)

    def test_greeting_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        result = executor_greeting.execute_greeting(self._fake_request())
        self.assertTrue(result.message.startswith('नमस्ते Priya Sharma, शुभ '))
        self.assertIn('आज मैं आपकी कैसे मदद कर सकता हूं?', result.message)


class LeaveBalanceExecutorTests(_LanguageIsolatedTestCase):
    """execute_check_leave_balance's no-records branch — LeaveBalance.objects
    is mocked so the query never touches a real database; the message
    selection logic under test is unaffected by what the query returns, only
    by whether `data` ends up empty."""

    @patch('apps.voice_commands.executor_leave.LeaveBalanceSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveBalance')
    def test_no_balance_records_is_english_by_default(self, mock_model, mock_serializer):
        mock_model.objects.filter.return_value.order_by.return_value = []
        mock_serializer.return_value.data = []
        request = SimpleNamespace(user=MagicMock())

        result = executor_leave.execute_check_leave_balance(request)

        self.assertIn('You have no leave balance records for', result.message)

    @patch('apps.voice_commands.executor_leave.LeaveBalanceSerializer')
    @patch('apps.voice_commands.executor_leave.LeaveBalance')
    def test_no_balance_records_is_hindi_when_set(self, mock_model, mock_serializer):
        mock_model.objects.filter.return_value.order_by.return_value = []
        mock_serializer.return_value.data = []
        language.set_current_language(language.LANG_HI)
        request = SimpleNamespace(user=MagicMock())

        result = executor_leave.execute_check_leave_balance(request)

        self.assertIn('के लिए आपका कोई छुट्टी शेष रिकॉर्ड नहीं है।', result.message)


class PayslipSummaryMessageTests(_LanguageIsolatedTestCase):
    """_payslip_summary_message is a pure function (no DB, no request) —
    tested directly rather than through the DB-querying executor functions
    that call it."""

    _DATA = {
        'cycle_end': '2026-08-31', 'gross_earnings': 50000,
        'total_deductions': 5000, 'net_pay': 45000, 'status': 'sent',
    }

    def test_own_payslip_summary_is_english_by_default(self):
        message = executor_payroll._payslip_summary_message(self._DATA, subject_en='Your', subject_hi='आपकी')
        self.assertTrue(message.startswith('Your most recent payslip'))
        self.assertIn('₹50000', message)
        self.assertIn('Sent to Employee', message)

    def test_own_payslip_summary_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        message = executor_payroll._payslip_summary_message(self._DATA, subject_en='Your', subject_hi='आपकी')
        self.assertTrue(message.startswith('आपकी सबसे हाल की पेस्लिप'))
        self.assertIn('₹50000', message)
        self.assertIn('कर्मचारी को भेजी गई', message)

    def test_someone_elses_payslip_uses_the_hindi_possessive_subject(self):
        language.set_current_language(language.LANG_HI)
        message = executor_payroll._payslip_summary_message(
            self._DATA, subject_en="Rahul's", subject_hi='राहुल की',
        )
        self.assertTrue(message.startswith('राहुल की सबसे हाल की पेस्लिप'))


class TeamAttendanceExecutorTests(_LanguageIsolatedTestCase):
    """Mirrors test_check_team_attendance.py's own mocking of
    HRAttendanceDashboardView — same view-call shape, checking only this
    executor's message-construction logic here."""

    @staticmethod
    def _stat_cards(**overrides):
        stats = {'present_today': 42, 'absent': 3, 'late_arrivals': 2, 'on_leave': 5, 'total_employees': 50}
        stats.update(overrides)
        return stats

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRAttendanceDashboardView')
    def test_team_attendance_summary_is_english_by_default(self, mock_view_cls, _mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'data': {'stat_cards': self._stat_cards(), 'summary_chips': {'half_day': 1}}},
        )
        request = SimpleNamespace(user=MagicMock())

        result = executor_approval.execute_check_team_attendance(request)

        self.assertEqual(
            result.message,
            'Today, 42 of 50 team members are present, 3 absent, 5 on leave, 1 on half-day, and 2 arrived late.',
        )

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRAttendanceDashboardView')
    def test_team_attendance_summary_is_hindi_when_set(self, mock_view_cls, _mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'data': {'stat_cards': self._stat_cards(), 'summary_chips': {'half_day': 1}}},
        )
        language.set_current_language(language.LANG_HI)
        request = SimpleNamespace(user=MagicMock())

        result = executor_approval.execute_check_team_attendance(request)

        self.assertEqual(
            result.message,
            'आज, 50 में से 42 टीम सदस्य उपस्थित हैं, 3 अनुपस्थित, 5 छुट्टी पर, 1 आधे दिन पर, और 2 देर से आए।',
        )


class PunchValidationFailureTests(_LanguageIsolatedTestCase):
    """_execute_punch's invalid-payload branch — PunchWriteSerializer is
    mocked to fail validation so this never reaches PunchService/the
    database; the message selection logic under test only depends on
    is_valid() being False."""

    @patch('apps.voice_commands.executor_attendance.PunchWriteSerializer')
    def test_invalid_punch_payload_is_english_by_default(self, mock_serializer_cls):
        mock_serializer_cls.return_value.is_valid.return_value = False
        mock_serializer_cls.return_value.errors = {}
        request = SimpleNamespace(user=MagicMock())

        result = executor_attendance.execute_clock_in(request, attendance_mode='office')

        self.assertEqual(result.message, 'Could not process the request.')

    @patch('apps.voice_commands.executor_attendance.PunchWriteSerializer')
    def test_invalid_punch_payload_is_hindi_when_set(self, mock_serializer_cls):
        mock_serializer_cls.return_value.is_valid.return_value = False
        mock_serializer_cls.return_value.errors = {}
        language.set_current_language(language.LANG_HI)
        request = SimpleNamespace(user=MagicMock())

        result = executor_attendance.execute_clock_in(request, attendance_mode='office')

        self.assertEqual(result.message, 'अनुरोध संसाधित नहीं किया जा सका।')
