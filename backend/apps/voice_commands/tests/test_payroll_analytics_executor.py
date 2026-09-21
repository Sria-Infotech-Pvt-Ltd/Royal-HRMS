from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import (
    INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN,
    INTENT_CHECK_PAYROLL_COST_SUMMARY,
    INTENT_CHECK_PENDING_PAYROLL_CYCLES,
    execute_intent,
)
from apps.voice_commands.matcher import get_conversational, get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."

_ANALYTICS_INTENTS = (
    INTENT_CHECK_PENDING_PAYROLL_CYCLES, INTENT_CHECK_PAYROLL_COST_SUMMARY, INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN,
)


def _fake_request(has_payroll_view: bool, user_id: int = 7):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_payroll_view
    user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions), id=user_id, pk=user_id)
    request = MagicMock()
    request.META = {}
    request.user = user
    return request


class PayrollAnalyticsRegistryTests(SimpleTestCase):
    def test_all_three_intents_require_payroll_view(self):
        for intent in _ANALYTICS_INTENTS:
            self.assertEqual(get_required_permission(intent), 'payroll.view')

    def test_all_three_intents_are_not_conversational(self):
        for intent in _ANALYTICS_INTENTS:
            self.assertFalse(get_conversational(intent))


class PayrollAnalyticsPermissionDeniedTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll_analytics.AttendancePendingCyclesView')
    def test_pending_cycles_denied_without_payroll_view(self, mock_view_cls):
        request = _fake_request(has_payroll_view=False)
        result = execute_intent(INTENT_CHECK_PENDING_PAYROLL_CYCLES, request)
        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_cost_summary_denied_without_payroll_view(self, mock_view_cls):
        request = _fake_request(has_payroll_view=False)
        result = execute_intent(INTENT_CHECK_PAYROLL_COST_SUMMARY, request)
        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll_analytics.BranchPayrollBreakdownView')
    def test_branch_breakdown_denied_without_payroll_view(self, mock_view_cls):
        request = _fake_request(has_payroll_view=False)
        result = execute_intent(INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN, request)
        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()


class CheckPendingPayrollCyclesExecutorTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.AttendancePendingCyclesView')
    def test_no_cycles_found(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': []})
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_PENDING_PAYROLL_CYCLES, request)

        self.assertTrue(result.success)
        self.assertIn('No payroll cycles', result.message)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.AttendancePendingCyclesView')
    def test_reports_count_of_pending_cycles(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200, data={'data': [{'id': '1'}, {'id': '2'}]},
        )
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_PENDING_PAYROLL_CYCLES, request)

        self.assertTrue(result.success)
        self.assertIn('2', result.message)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.AttendancePendingCyclesView')
    def test_view_403_gets_the_friendly_access_denied_message(self, mock_view_cls, mock_force_authenticate):
        """
        AttendancePendingCyclesView's own 403 (its finer-grained
        _can_view_approvals check — see registry/intents_en.yaml's own note
        on this intent's two-layer permission shape) is normalized to this
        module's own friendlier message rather than relayed verbatim —
        unlike a non-403 failure (see the other view-backed executors'
        "surfaces its own message" behavior), since the raw view message
        here is written for an HR admin UI context, not a spoken reply.
        """
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=403, data={'message': 'Access denied.'},
        )
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_PENDING_PAYROLL_CYCLES, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, "You don't have permission to view payroll analytics.")

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.AttendancePendingCyclesView')
    def test_view_non_403_failure_surfaces_its_own_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=500, data={'message': 'Something went wrong.'},
        )
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_PENDING_PAYROLL_CYCLES, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Something went wrong.')


class CheckPayrollCostSummaryExecutorTests(SimpleTestCase):
    def _mock_success(self, mock_view_cls, **data_overrides):
        data = {'gross_earnings': '150000', 'net_pay': '135000', 'employee_count': 3, 'branches_included': []}
        data.update(data_overrides)
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': data})
        return data

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_reads_figures_aloud_in_full(self, mock_view_cls, mock_force_authenticate):
        """Company/branch-wide aggregate data the caller already has
        payroll.view for — unlike check_my_payslip, no speech_message
        redaction is applied."""
        self._mock_success(mock_view_cls)
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(
            INTENT_CHECK_PAYROLL_COST_SUMMARY, request, slots={'raw_text': 'what is our payroll cost'},
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.speech_message)
        self.assertIn('150000', result.message)
        self.assertIn('135000', result.message)
        self.assertIn('3', result.message)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_no_data_found_for_period(self, mock_view_cls, mock_force_authenticate):
        self._mock_success(mock_view_cls, gross_earnings='0', net_pay='0', employee_count=0)
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_PAYROLL_COST_SUMMARY, request)

        self.assertTrue(result.success)
        self.assertIn('No payroll data', result.message)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_last_month_phrase_resolves_to_offset_one(self, mock_view_cls, mock_force_authenticate):
        self._mock_success(mock_view_cls, employee_count=0)
        request = _fake_request(has_payroll_view=True)

        execute_intent(
            INTENT_CHECK_PAYROLL_COST_SUMMARY, request,
            slots={'raw_text': 'what was our payroll cost last month'},
        )

        django_request = mock_view_cls.as_view.return_value.call_args.args[0]
        self.assertEqual(django_request.GET.get('offset'), '1')
        self.assertNotIn('month', django_request.GET)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_explicit_month_phrase_wins_over_offset(self, mock_view_cls, mock_force_authenticate):
        self._mock_success(mock_view_cls, employee_count=0)
        request = _fake_request(has_payroll_view=True)

        execute_intent(
            INTENT_CHECK_PAYROLL_COST_SUMMARY, request, slots={'raw_text': 'payroll cost for march'},
        )

        django_request = mock_view_cls.as_view.return_value.call_args.args[0]
        self.assertTrue(django_request.GET.get('month', '').endswith('-03'))
        self.assertNotIn('offset', django_request.GET)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.PayrollCostSummaryView')
    def test_absent_raw_text_falls_back_to_view_default(self, mock_view_cls, mock_force_authenticate):
        self._mock_success(mock_view_cls, employee_count=0)
        request = _fake_request(has_payroll_view=True)

        execute_intent(INTENT_CHECK_PAYROLL_COST_SUMMARY, request)

        django_request = mock_view_cls.as_view.return_value.call_args.args[0]
        self.assertNotIn('month', django_request.GET)
        self.assertNotIn('offset', django_request.GET)


class CheckBranchPayrollBreakdownExecutorTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.BranchPayrollBreakdownView')
    def test_reads_only_top_three_branches_aloud_but_returns_full_data(self, mock_view_cls, mock_force_authenticate):
        rows = [{'branch_name': f'Branch {i}', 'net_pay': str(1000 - i), 'employee_count': 1} for i in range(5)]
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': rows})
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN, request)

        self.assertTrue(result.success)
        for row in rows[:3]:
            self.assertIn(row['branch_name'], result.message)
        for row in rows[3:]:
            self.assertNotIn(row['branch_name'], result.message)
        self.assertEqual(result.data, rows)  # full, un-truncated list for the UI

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.BranchPayrollBreakdownView')
    def test_single_branch_result_uses_singular_phrasing(self, mock_view_cls, mock_force_authenticate):
        rows = [{'branch_name': 'Branch A', 'net_pay': '99000', 'employee_count': 2}]
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': rows})
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN, request)

        self.assertTrue(result.success)
        self.assertIn('Branch A', result.message)
        self.assertIn('99000', result.message)

    @patch('apps.voice_commands.executor_payroll_analytics.force_authenticate')
    @patch('apps.voice_commands.executor_payroll_analytics.BranchPayrollBreakdownView')
    def test_no_data_found_for_period(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': []})
        request = _fake_request(has_payroll_view=True)

        result = execute_intent(INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN, request)

        self.assertTrue(result.success)
        self.assertIn('No branch payroll data', result.message)
