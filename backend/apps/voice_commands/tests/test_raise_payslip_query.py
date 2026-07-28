import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import INTENT_RAISE_PAYSLIP_QUERY, execute_intent
from apps.voice_commands.matcher import get_conversational, get_required_permission

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_payroll_view_own: bool = True, user_id: int = 55):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_payroll_view_own
    request = MagicMock()
    request.META = {}
    request.user = SimpleNamespace(
        role=SimpleNamespace(role_permissions=role_permissions), id=user_id, pk=user_id,
    )
    return request


class _FakePendingStore:
    """Same in-memory stand-in used by test_apply_leave_conversation.py/
    test_approve_reject_leave.py for the Redis-backed clarification cache."""

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


def _mock_payslip(pk='payslip-9'):
    payslip = MagicMock()
    payslip.pk = pk
    return payslip


def _mock_query(mock_model, payslip):
    mock_model.objects.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = payslip


def _query_view_response(status_code=201, message='Query raised.', data=None):
    return MagicMock(status_code=status_code, data={'success': status_code < 400, 'message': message, 'data': data or {}})


class RaisePayslipQueryRegistryTests(SimpleTestCase):
    def test_requires_payroll_view_own_permission(self):
        """Verified directly against PayslipQueryListView.post() (payroll/views/
        payslips.py:375-376) — the SAME codename check_my_payslip/
        acknowledge_payslip use, not a separate query/dispute codename."""
        self.assertEqual(get_required_permission(INTENT_RAISE_PAYSLIP_QUERY), 'payroll.view_own')

    def test_is_conversational(self):
        self.assertTrue(get_conversational(INTENT_RAISE_PAYSLIP_QUERY))


class PermissionDeniedTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_execute_intent_denied_without_payroll_view_own(self, mock_model, mock_view_cls):
        request = _fake_request(has_payroll_view_own=False)

        result = execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': 'my hra looks wrong'})

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_model.objects.filter.assert_not_called()
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_conversation_flow_never_reaches_the_view_without_permission(self, mock_model, mock_view_cls):
        request = _fake_request(has_payroll_view_own=False)

        result = handle_transcript(request, 'raise a query about my payslip because the hra looks wrong')

        self.assertEqual(result['message'], _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()


class ExecutorTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_no_payslip_on_record(self, mock_model):
        _mock_query(mock_model, None)
        request = _fake_request()

        result = execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': 'the hra looks wrong'})

        self.assertFalse(result.success)
        self.assertIn("don't have any payslips", result.message)

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_successful_submission(self, mock_model, mock_view_cls, mock_force_authenticate):
        _mock_query(mock_model, _mock_payslip())
        mock_view_cls.as_view.return_value.return_value = _query_view_response()
        request = _fake_request()

        result = execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': 'the hra looks wrong'})

        self.assertTrue(result.success)
        self.assertIn('raised', result.message.lower())

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_view_rejection_surfaces_its_own_business_rule_message(
        self, mock_model, mock_view_cls, mock_force_authenticate,
    ):
        """PayslipQueryListView.post()'s own status/query-window rules
        (payslips.py:386-390) run unchanged; voice only relays the message."""
        _mock_query(mock_model, _mock_payslip())
        mock_view_cls.as_view.return_value.return_value = _query_view_response(
            status_code=400, message='The query window for this payslip has closed.',
        )
        request = _fake_request()

        result = execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': 'the hra looks wrong'})

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'The query window for this payslip has closed.')

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_forwards_the_payslip_id_and_description(self, mock_model, mock_view_cls, mock_force_authenticate):
        _mock_query(mock_model, _mock_payslip(pk='payslip-77'))
        mock_view_cls.as_view.return_value.return_value = _query_view_response()
        request = _fake_request()

        execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': 'the hra looks wrong'})

        call_args = mock_view_cls.as_view.return_value.call_args
        sent_body = json.loads(call_args.args[0].body)
        self.assertEqual(sent_body['payslip'], 'payslip-77')
        self.assertEqual(sent_body['description'], 'the hra looks wrong')


class DirectQueryConversationTests(SimpleTestCase):
    """The direct 'raise a query' phrasing — not the download-flavored route."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_full_utterance_with_because_clause_submits_in_one_turn(
        self, mock_model, mock_view_cls, mock_force_authenticate,
    ):
        _mock_query(mock_model, _mock_payslip(pk='payslip-1'))
        mock_view_cls.as_view.return_value.return_value = _query_view_response()
        request = _fake_request()

        result = handle_transcript(
            request, 'raise a query about my payslip because the hra calculation looks wrong',
        )

        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        self.assertIsNone(self.store.get(55))

    def test_bare_utterance_asks_for_the_query_content(self):
        request = _fake_request()

        result = handle_transcript(request, 'raise a payslip query')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('what would you like to ask', result['message'].lower())
        self.assertNotIn('download', result['message'].lower())

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_follow_up_answer_submits_the_query(self, mock_model, mock_view_cls, mock_force_authenticate):
        _mock_query(mock_model, _mock_payslip(pk='payslip-1'))
        mock_view_cls.as_view.return_value.return_value = _query_view_response()
        request = _fake_request()

        handle_transcript(request, 'raise a payslip query')
        result = handle_transcript(request, 'the hra calculation on my payslip looks wrong to me')

        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        self.assertIsNone(self.store.get(55))

    def test_too_short_follow_up_answer_reasks_without_submitting(self):
        request = _fake_request()

        handle_transcript(request, 'raise a payslip query')
        result = handle_transcript(request, 'no')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('a bit more', result['message'].lower())
        self.assertIsNotNone(self.store.get(55))


class DownloadPhraseRoutingTests(SimpleTestCase):
    """'download my payslip'-style phrases route into this same intent with a
    redirect preamble, instead of a dead-end rejection — payslip PDFs are
    never generated anywhere in the payroll app (see the investigation this
    build was based on)."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_download_my_payslip_routes_to_raise_payslip_query(self):
        request = _fake_request()

        result = handle_transcript(request, 'download my payslip')

        self.assertEqual(result['intent'], INTENT_RAISE_PAYSLIP_QUERY)
        self.assertTrue(result['awaiting_input'])

    def test_download_my_payslip_message_explains_the_gap_and_offers_a_query(self):
        request = _fake_request()

        result = handle_transcript(request, 'download my payslip')

        self.assertIn("aren't available", result['message'].lower())
        self.assertIn('query', result['message'].lower())

    def test_send_me_my_payslip_also_routes_here_with_the_redirect(self):
        request = _fake_request()

        result = handle_transcript(request, 'send me my payslip')

        self.assertEqual(result['intent'], INTENT_RAISE_PAYSLIP_QUERY)
        self.assertIn("aren't available", result['message'].lower())

    def test_get_my_payslip_pdf_also_routes_here_with_the_redirect(self):
        request = _fake_request()

        result = handle_transcript(request, 'get my payslip pdf')

        self.assertEqual(result['intent'], INTENT_RAISE_PAYSLIP_QUERY)
        self.assertIn("aren't available", result['message'].lower())

    def test_direct_query_phrasing_does_not_get_the_download_preamble(self):
        """Sanity check the preamble is conditional, not always shown for this intent."""
        request = _fake_request()

        result = handle_transcript(request, 'i have an issue with my payslip')

        self.assertNotIn("aren't available", result['message'].lower())

    @patch('apps.voice_commands.executor_payroll.force_authenticate')
    @patch('apps.voice_commands.executor_payroll.PayslipQueryListView')
    @patch('apps.voice_commands.executor_payroll.EmployeePayslip')
    def test_answering_the_redirect_still_submits_a_real_query(
        self, mock_model, mock_view_cls, mock_force_authenticate,
    ):
        _mock_query(mock_model, _mock_payslip(pk='payslip-1'))
        mock_view_cls.as_view.return_value.return_value = _query_view_response()
        request = _fake_request()

        handle_transcript(request, 'download my payslip')
        result = handle_transcript(request, 'i just want to check my hra deduction is correct')

        self.assertFalse(result['awaiting_input'])
        self.assertTrue(result['success'])
        call_args = mock_view_cls.as_view.return_value.call_args
        sent_body = json.loads(call_args.args[0].body)
        self.assertIn('hra deduction', sent_body['description'])
