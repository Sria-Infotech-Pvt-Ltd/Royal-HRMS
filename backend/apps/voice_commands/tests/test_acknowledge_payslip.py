from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_ACKNOWLEDGE_PAYSLIP, execute_intent
from apps.voice_commands.matcher import get_conversational, get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_payroll_view_own: bool, user_id: int = 7):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_payroll_view_own
    user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions), id=user_id, pk=user_id)

    request = MagicMock()
    request.META = {}
    request.user = user
    return request


def _mock_payslip(pk='payslip-1'):
    payslip = MagicMock()
    payslip.pk = pk
    return payslip


class AcknowledgePayslipRegistryTests(SimpleTestCase):
    def test_requires_payroll_view_own_permission(self):
        """
        Verified directly against AcknowledgePayslipView.post() (payroll/views/
        payslips.py:344-345) — the SAME codename check_my_payslip uses, NOT a
        mutation-flavored codename like payroll.edit, despite this being a
        state-changing action.
        """
        self.assertEqual(get_required_permission(INTENT_ACKNOWLEDGE_PAYSLIP), 'payroll.view_own')

    def test_is_not_conversational(self):
        self.assertFalse(get_conversational(INTENT_ACKNOWLEDGE_PAYSLIP))


class AcknowledgePayslipPermissionDeniedTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll.AcknowledgePayslipView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_user_without_payroll_view_own_is_rejected(self, mock_model, mock_view_cls):
        request = _fake_request(has_payroll_view_own=False)

        result = execute_intent(INTENT_ACKNOWLEDGE_PAYSLIP, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_model.objects.filter.assert_not_called()
        mock_view_cls.as_view.assert_not_called()


class AcknowledgePayslipExecutorTests(SimpleTestCase):
    def _mock_query(self, mock_model, payslip):
        mock_model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = payslip

    @patch('apps.voice_commands.executor_payroll.AcknowledgePayslipView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_no_payslip_on_record(self, mock_model, mock_view_cls):
        self._mock_query(mock_model, None)
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_ACKNOWLEDGE_PAYSLIP, request)

        self.assertFalse(result.success)
        self.assertIn("don't have any payslips", result.message)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.AcknowledgePayslipView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_successful_acknowledgement(self, mock_model, mock_view_cls, mock_force_authenticate):
        self._mock_query(mock_model, _mock_payslip())
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=200, data={'success': True, 'message': 'Payslip acknowledged.', 'data': None},
        )
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_ACKNOWLEDGE_PAYSLIP, request)

        self.assertTrue(result.success)
        self.assertIn('acknowledged', result.message.lower())

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.AcknowledgePayslipView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_view_rejection_surfaces_its_own_business_rule_message(
        self, mock_model, mock_view_cls, mock_force_authenticate,
    ):
        """
        AcknowledgePayslipView.post()'s own status-must-be-SENT rule
        (payslips.py:348-349) runs unchanged; voice only relays its message,
        never re-implements or bypasses it.
        """
        self._mock_query(mock_model, _mock_payslip())
        mock_view_cls.as_view.return_value.return_value = MagicMock(
            status_code=400,
            data={'success': False, 'message': 'Payslip is not in a state that can be acknowledged.'},
        )
        request = _fake_request(has_payroll_view_own=True)

        result = execute_intent(INTENT_ACKNOWLEDGE_PAYSLIP, request)

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'Payslip is not in a state that can be acknowledged.')

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.AcknowledgePayslipView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_authenticates_as_the_calling_user_and_targets_the_right_payslip(
        self, mock_model, mock_view_cls, mock_force_authenticate,
    ):
        self._mock_query(mock_model, _mock_payslip(pk='payslip-42'))
        mock_view_cls.as_view.return_value.return_value = MagicMock(status_code=200, data={'data': None})
        request = _fake_request(has_payroll_view_own=True)

        execute_intent(INTENT_ACKNOWLEDGE_PAYSLIP, request)

        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)
        call_kwargs = mock_view_cls.as_view.return_value.call_args.kwargs
        self.assertEqual(call_kwargs.get('pk'), 'payslip-42')
