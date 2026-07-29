from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_CHECK_MY_PAYSLIP, execute_intent
from apps.voice_commands.matcher import get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_payroll_view_own: bool):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_payroll_view_own
    user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions), id=1, pk=1)

    request = MagicMock()
    request.META = {}
    request.user = user
    return request


def _mock_data(**overrides):
    data = {
        'cycle_end': '2026-07-31',
        'gross_earnings': '55000.00',
        'total_deductions': '5000.00',
        'net_pay': '50000.00',
        'status': 'sent',
    }
    data.update(overrides)
    return data


class CheckMyPayslipRegistryTests(SimpleTestCase):
    def test_requires_payroll_view_own_permission(self):
        """
        Verified directly against MyPayslipsView.get() (payroll/views/payslips.py
        :323-324) — this is NOT the same "no domain codename required" shape
        as check_leave_balance/check_attendance_stats's own-data intents.
        """
        self.assertEqual(get_required_permission(INTENT_CHECK_MY_PAYSLIP), 'payroll.view_own')


class CheckMyPayslipPermissionDeniedTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_user_without_payroll_view_own_is_rejected(self, mock_model):
        request = _fake_request(has_payroll_view_own=False)

        result = execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_model.objects.filter.assert_not_called()


class CheckMyPayslipExecutorTests(SimpleTestCase):
    def _mock_query(self, mock_model, payslip):
        mock_model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = payslip

    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_no_payslip_on_record(self, mock_model, mock_serializer_cls):
        self._mock_query(mock_model, None)
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        self.assertTrue(result.success)
        self.assertIn("don't have any payslips", result.message)
        mock_serializer_cls.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_summary_includes_gross_deductions_net_and_status(self, mock_model, mock_serializer_cls):
        self._mock_query(mock_model, MagicMock())
        mock_serializer_cls.return_value.data = _mock_data()
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        self.assertTrue(result.success)
        self.assertIn('55000.00', result.message)
        self.assertIn('5000.00', result.message)
        self.assertIn('50000.00', result.message)
        # 'sent' -> EmployeePayslip.STATUS_CHOICES' real display label, not the raw code.
        self.assertIn('Sent to Employee', result.message)

    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_message_does_not_dump_every_raw_field(self, mock_model, mock_serializer_cls):
        """Only gross/deductions/net/status get spoken — not pf_employee,
        esi_employee, lop_days, etc. (the full serializer payload is still
        returned as .data for anything that wants the raw fields)."""
        self._mock_query(mock_model, MagicMock())
        mock_serializer_cls.return_value.data = _mock_data(pf_employee='1800.00', esi_employee='412.50')
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        self.assertNotIn('1800.00', result.message)
        self.assertNotIn('412.50', result.message)

    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_queries_by_the_calling_users_own_id(self, mock_model, mock_serializer_cls):
        self._mock_query(mock_model, MagicMock())
        mock_serializer_cls.return_value.data = _mock_data()
        request = _fake_request(has_payroll_view_own=True)

        execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        mock_model.objects.filter.assert_called_once_with(employee_id=request.user.id)

    @patch('apps.voice_commands.executor_payroll.EmployeePayslipSerializer')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_orders_most_recent_cycle_first(self, mock_model, mock_serializer_cls):
        """Same ordering MyPayslipsView.get() uses — no 'current month' filter
        exists on the real endpoint either; this mirrors taking results[0]."""
        self._mock_query(mock_model, MagicMock())
        mock_serializer_cls.return_value.data = _mock_data()
        request = _fake_request(has_payroll_view_own=True)

        execute_intent(INTENT_CHECK_MY_PAYSLIP, request)

        mock_model.objects.filter.return_value.select_related.return_value.order_by.assert_called_once_with(
            '-cycle__cycle_start',
        )
