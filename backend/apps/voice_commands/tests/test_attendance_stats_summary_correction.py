import json
from datetime import date, time
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import (
    INTENT_CHECK_ATTENDANCE_STATS,
    INTENT_CHECK_ATTENDANCE_SUMMARY,
    INTENT_REQUEST_ATTENDANCE_CORRECTION,
    execute_intent,
)


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


def _fake_correction_slots():
    return {
        'date': date(2026, 7, 22),
        'punch_type': 'IN',
        'correct_in_time': time(9, 15),
        'reason': 'forgot_to_punch',
    }


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
# execute_request_attendance_correction (executor_attendance.py) submits
# through AttendanceCorrectionView directly (APIRequestFactory +
# force_authenticate) rather than duplicating its conflict-check/audit-log
# logic — same pattern test_apply_leave_executor.py uses for
# LeaveRequestListCreateView. These tests mock the view call itself,
# isolating the executor's own request-building and message-passthrough logic.

class RequestAttendanceCorrectionTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_successful_submission_returns_the_views_success_message(
        self, mock_force_authenticate, mock_view_cls,
    ):
        mock_response = MagicMock(
            status_code=201,
            data={
                'success': True,
                'message': 'Attendance correction request submitted successfully. '
                            'Your manager will review it within the regularization window.',
                'data': {'id': 'corr-1'},
            },
        )
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=_fake_correction_slots())

        self.assertTrue(result.success)
        self.assertIn('regularization window', result.message)
        self.assertEqual(result.data, {'id': 'corr-1'})

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_authenticates_the_synthetic_request_as_the_calling_user(self, mock_force_authenticate, mock_view_cls):
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=201, data={'data': {}})
        request = _fake_request()

        execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=_fake_correction_slots())

        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_conflict_failure_surfaces_the_views_error_message(self, mock_force_authenticate, mock_view_cls):
        """AttendanceCorrectionView.post() rejects a second pending correction
        for the same date with a 409 — this executor is a thin passthrough,
        it doesn't duplicate that check itself."""
        mock_response = MagicMock(
            status_code=409,
            data={'message': 'A correction request is already pending for this date. '
                              'Please wait for it to be reviewed before submitting another.'},
        )
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=_fake_correction_slots())

        self.assertFalse(result.success)
        self.assertIn('already pending', result.message)

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_failure_without_a_message_falls_back_to_generic_message(self, mock_force_authenticate, mock_view_cls):
        mock_response = MagicMock(status_code=500, data={})
        mock_view_cls.as_view.return_value.return_value = mock_response
        request = _fake_request()

        result = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=_fake_correction_slots())

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Could not submit the attendance correction request.')

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_payload_sent_to_the_view_has_iso_date_and_hhmm_time(self, mock_force_authenticate, mock_view_cls):
        captured = {}

        def _capture_view(django_request):
            captured['body'] = json.loads(django_request.body)
            return MagicMock(status_code=201, data={'data': {}})

        mock_view_cls.as_view.return_value = _capture_view
        request = _fake_request()

        execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=_fake_correction_slots())

        self.assertEqual(captured['body'], {
            'date': '2026-07-22',
            'punch_type': 'IN',
            'reason': 'forgot_to_punch',
            'correct_in_time': '09:15',
        })

    @patch('apps.voice_commands.executor_attendance.AttendanceCorrectionView')
    @patch('apps.voice_commands.executor_attendance.force_authenticate')
    def test_out_only_payload_omits_correct_in_time(self, mock_force_authenticate, mock_view_cls):
        captured = {}

        def _capture_view(django_request):
            captured['body'] = json.loads(django_request.body)
            return MagicMock(status_code=201, data={'data': {}})

        mock_view_cls.as_view.return_value = _capture_view
        request = _fake_request()
        slots = {
            'date': date(2026, 7, 22), 'punch_type': 'OUT',
            'correct_out_time': time(18, 30), 'reason': 'system_downtime',
        }

        execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=slots)

        self.assertNotIn('correct_in_time', captured['body'])
        self.assertEqual(captured['body']['correct_out_time'], '18:30')
