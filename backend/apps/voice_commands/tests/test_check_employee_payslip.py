from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import INTENT_CHECK_EMPLOYEE_PAYSLIP, execute_intent
from apps.voice_commands.matcher import get_conversational, get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_payroll_view: bool = True, user_id: int = 90, branch=None):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_payroll_view
    request = MagicMock()
    request.META = {}
    request.user = SimpleNamespace(
        role=SimpleNamespace(role_permissions=role_permissions, name='hr_admin'),
        id=user_id, pk=user_id, branch=branch,
    )
    return request


class _FakePendingStore:
    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store):
    # conversation_payroll.py imports set_pending/clear_pending directly from
    # clarification.py (not through conversation.py) to avoid a circular
    # import — both bindings point at the same real functions/cache key in
    # production, but a fake in-memory store has to be patched onto BOTH
    # module namespaces to see every write, since patching only
    # apps.voice_commands.conversation would miss the ones conversation_payroll
    # makes directly.
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_payroll.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_payroll.clear_pending', side_effect=store.clear),
    )


def _fake_employee(user_id, full_name):
    return SimpleNamespace(id=user_id, full_name=full_name)


def _mock_employee_queryset(mock_user_model, employees):
    mock_user_model.objects.filter.return_value.exclude.return_value = employees


def _mock_payslip_lookup(mock_payslip_model, payslip):
    mock_payslip_model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = payslip


def _detail_view_response(status_code=200, data=None, message='Payslip retrieved.'):
    return MagicMock(status_code=status_code, data={'success': status_code < 400, 'message': message, 'data': data})


def _payslip_data(**overrides):
    data = {
        'cycle_end': '2026-07-31', 'gross_earnings': '80000.00',
        'total_deductions': '9000.00', 'net_pay': '71000.00', 'status': 'paid',
    }
    data.update(overrides)
    return data


class CheckEmployeePayslipRegistryTests(SimpleTestCase):
    def test_requires_payroll_view_permission(self):
        """
        Verified directly against PayslipDetailView.get() (payroll/views/
        payslips.py:61) — the codename that gate checks for viewing anyone
        OTHER than yourself. This is deliberately a DIFFERENT codename from
        check_my_payslip/acknowledge_payslip/raise_payslip_query's
        payroll.view_own.
        """
        self.assertEqual(get_required_permission(INTENT_CHECK_EMPLOYEE_PAYSLIP), 'payroll.view')

    def test_is_conversational(self):
        self.assertTrue(get_conversational(INTENT_CHECK_EMPLOYEE_PAYSLIP))


class PermissionDeniedTests(SimpleTestCase):
    """Mirrors test_check_team_leave_queue.py's pattern: a caller without
    payroll.view must never reach the employee lookup or PayslipDetailView at
    all — not even payroll.view_own is enough here."""

    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_execute_intent_denied_without_payroll_view(self, mock_user_model, mock_detail_view):
        request = _fake_request(has_payroll_view=False)

        result = execute_intent(INTENT_CHECK_EMPLOYEE_PAYSLIP, request, slots={'name_query': 'sarah'})

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_user_model.objects.filter.assert_not_called()
        mock_detail_view.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_conversation_flow_never_reaches_the_lookup_without_permission(
        self, mock_user_model, mock_detail_view,
    ):
        request = _fake_request(has_payroll_view=False)

        result = handle_transcript(request, "check sarah khan's payslip")

        self.assertEqual(result['message'], _PERMISSION_DENIED_MESSAGE)
        mock_user_model.objects.filter.assert_not_called()
        mock_detail_view.as_view.assert_not_called()


class NeedNameTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_no_name_in_utterance_asks_which_employee(self):
        request = _fake_request()

        result = handle_transcript(request, "check her payslip")

        self.assertTrue(result['awaiting_input'])
        self.assertIn("which employee", result['message'].lower())


class ZeroMatchTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_zero_match_ends_the_flow_with_a_clear_message(self, mock_user_model, mock_detail_view):
        _mock_employee_queryset(mock_user_model, [_fake_employee(1, 'Sarah Khan')])
        request = _fake_request()

        result = handle_transcript(request, "check nobody special's payslip")

        self.assertIn('no employee found', result['message'].lower())
        self.assertFalse(result['awaiting_input'])
        self.assertIsNone(self.store.get(90))
        mock_detail_view.as_view.assert_not_called()


class MultipleMatchDisambiguationTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_ambiguous_name_asks_to_be_more_specific(self, mock_user_model, mock_detail_view):
        _mock_employee_queryset(mock_user_model, [
            _fake_employee(1, 'Sam Cooper'), _fake_employee(2, 'Sam Anderson'),
        ])
        request = _fake_request()

        result = handle_transcript(request, "check sam's payslip")

        self.assertTrue(result['awaiting_input'])
        self.assertIn('more specific', result['message'].lower())
        mock_detail_view.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_being_more_specific_resolves_to_a_single_match_and_responds_directly(
        self, mock_user_model, mock_payslip_model, mock_detail_view, mock_force_authenticate,
    ):
        _mock_employee_queryset(mock_user_model, [
            _fake_employee(1, 'Sam Cooper'), _fake_employee(2, 'Sam Anderson'),
        ])
        _mock_payslip_lookup(mock_payslip_model, MagicMock(pk='payslip-1'))
        mock_detail_view.as_view.return_value.return_value = _detail_view_response(data=_payslip_data())
        request = _fake_request()

        handle_transcript(request, "check sam's payslip")
        result = handle_transcript(request, 'sam cooper')

        # No yes/no confirmation stage — the follow-up answer resolves
        # directly to the terminal payslip summary.
        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        self.assertIn('80000.00', result['message'])
        self.assertIn('71000.00', result['message'])


class SingleMatchImmediateResponseTests(SimpleTestCase):
    """The complete happy path in one turn: a name in the first utterance
    resolves to exactly one employee, and their payslip summary is read back
    directly — no yes/no confirmation, unlike approve_leave/reject_leave."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_single_match_responds_immediately_with_no_confirmation_stage(
        self, mock_user_model, mock_payslip_model, mock_detail_view, mock_force_authenticate,
    ):
        _mock_employee_queryset(mock_user_model, [_fake_employee(1, 'Sarah Khan')])
        _mock_payslip_lookup(mock_payslip_model, MagicMock(pk='payslip-1'))
        mock_detail_view.as_view.return_value.return_value = _detail_view_response(data=_payslip_data())
        request = _fake_request()

        result = handle_transcript(request, "check sarah khan's payslip")

        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        self.assertIsNone(self.store.get(90))

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_response_states_whose_payslip_it_is(
        self, mock_user_model, mock_payslip_model, mock_detail_view, mock_force_authenticate,
    ):
        _mock_employee_queryset(mock_user_model, [_fake_employee(1, 'Sarah Khan')])
        _mock_payslip_lookup(mock_payslip_model, MagicMock(pk='payslip-1'))
        mock_detail_view.as_view.return_value.return_value = _detail_view_response(data=_payslip_data())
        request = _fake_request()

        result = handle_transcript(request, "check sarah khan's payslip")

        self.assertIn('sarah khan', result['message'].lower())

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_matched_employee_with_no_payslips_reports_that_clearly(
        self, mock_user_model, mock_payslip_model, mock_detail_view, mock_force_authenticate,
    ):
        _mock_employee_queryset(mock_user_model, [_fake_employee(1, 'Sarah Khan')])
        _mock_payslip_lookup(mock_payslip_model, None)
        request = _fake_request()

        result = handle_transcript(request, "check sarah khan's payslip")

        self.assertFalse(result['awaiting_input'])
        self.assertIn("doesn't have any payslips", result['message'].lower())
        mock_detail_view.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipDetailView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    @patch('apps.voice_commands.executor_payroll.User')
    def test_dispatches_through_the_real_payslip_detail_view(
        self, mock_user_model, mock_payslip_model, mock_detail_view, mock_force_authenticate,
    ):
        """Fetches via PayslipDetailView (re-validating self-vs-other access
        inside the real view too), not a locally reimplemented lookup."""
        _mock_employee_queryset(mock_user_model, [_fake_employee(1, 'Sarah Khan')])
        _mock_payslip_lookup(mock_payslip_model, MagicMock(pk='payslip-55'))
        mock_detail_view.as_view.return_value.return_value = _detail_view_response(data=_payslip_data())
        request = _fake_request()

        handle_transcript(request, "check sarah khan's payslip")

        call_kwargs = mock_detail_view.as_view.return_value.call_args.kwargs
        self.assertEqual(call_kwargs.get('pk'), 'payslip-55')
        mock_force_authenticate.assert_called_once()
        self.assertEqual(mock_force_authenticate.call_args.kwargs['user'], request.user)
