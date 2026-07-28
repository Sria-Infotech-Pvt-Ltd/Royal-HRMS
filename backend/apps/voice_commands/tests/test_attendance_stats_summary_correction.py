from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import (
    INTENT_CHECK_ATTENDANCE_STATS,
    INTENT_CHECK_ATTENDANCE_SUMMARY,
    INTENT_REQUEST_ATTENDANCE_CORRECTION,
    execute_intent,
)
from apps.voice_commands.executor_attendance import _CORRECTION_NEEDS_DASHBOARD_MESSAGE


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


# ── check_attendance_stats ────────────────────────────────────────────────────
# AttendanceDashboardService.get_stats and StatsSerializer are both mocked —
# this isolates the executor's own logic (target user, month/year args,
# message construction) from the real service query and the live Neon
# Postgres DATABASE_URL in backend/.env.

class CheckAttendanceStatsTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_attendance.StatsSerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_reports_stats_in_message(self, mock_service, mock_serializer_cls):
        mock_service.get_stats.return_value = {'raw': True}
        mock_serializer_cls.return_value.data = {
            'days_present': 18,
            'late_arrivals': 2,
            'lop_pending': 0,
            'avg_hours_per_day': 8.5,
            'attendance_percentage': 90,
            'working_days': 20,
        }

        result = execute_intent(INTENT_CHECK_ATTENDANCE_STATS, _fake_request())

        self.assertTrue(result.success)
        self.assertIn('18', result.message)
        self.assertIn('20', result.message)
        self.assertIn('90%', result.message)
        self.assertIn('2 late arrival', result.message)
        self.assertIn('8.5 hours', result.message)

    @patch('apps.voice_commands.executor_attendance.StatsSerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_queries_own_stats_for_current_month_and_year_no_employee_id(self, mock_service, mock_serializer_cls):
        from datetime import date

        mock_serializer_cls.return_value.data = {
            'days_present': 0, 'late_arrivals': 0, 'lop_pending': 0,
            'avg_hours_per_day': 0.0, 'attendance_percentage': 0, 'working_days': 0,
        }
        request = _fake_request()
        today = date.today()

        execute_intent(INTENT_CHECK_ATTENDANCE_STATS, request)

        mock_service.get_stats.assert_called_once_with(request.user, today.year, today.month)


# ── check_attendance_summary ──────────────────────────────────────────────────

class CheckAttendanceSummaryTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_attendance.MonthlySummarySerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_reports_summary_in_message(self, mock_service, mock_serializer_cls):
        mock_service.get_monthly_summary.return_value = {'raw': True}
        mock_serializer_cls.return_value.data = {
            'working_days': 20,
            'days_present': 17,
            'days_absent': 1,
            'leave_days': 2,
            'half_days': 0,
            'ot_hours': '3.5',
        }

        result = execute_intent(INTENT_CHECK_ATTENDANCE_SUMMARY, _fake_request())

        self.assertTrue(result.success)
        self.assertIn('17 days present', result.message)
        self.assertIn('1 absent', result.message)
        self.assertIn('2 leave day', result.message)
        self.assertIn('20 working days', result.message)

    @patch('apps.voice_commands.executor_attendance.MonthlySummarySerializer')
    @patch('apps.voice_commands.executor_attendance.AttendanceDashboardService')
    def test_queries_own_summary_for_current_month_and_year_no_employee_id(self, mock_service, mock_serializer_cls):
        from datetime import date

        mock_serializer_cls.return_value.data = {
            'working_days': 0, 'days_present': 0, 'days_absent': 0,
            'leave_days': 0, 'half_days': 0, 'ot_hours': '0',
        }
        request = _fake_request()
        today = date.today()

        execute_intent(INTENT_CHECK_ATTENDANCE_SUMMARY, request)

        mock_service.get_monthly_summary.assert_called_once_with(request.user, today.year, today.month)


# ── request_attendance_correction ─────────────────────────────────────────────

class RequestAttendanceCorrectionTests(SimpleTestCase):
    def test_always_defers_to_dashboard(self):
        """
        No slot-filling infrastructure exists yet, so this intent never
        attempts partial voice capture — it always asks the user to use the
        dashboard, regardless of what else was in the transcript.
        """
        result = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, _fake_request())

        self.assertFalse(result.success)
        self.assertEqual(result.message, _CORRECTION_NEEDS_DASHBOARD_MESSAGE)
        self.assertIn('dashboard', result.message)
