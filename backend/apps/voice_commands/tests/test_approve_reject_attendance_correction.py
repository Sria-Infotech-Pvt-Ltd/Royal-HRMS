import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.executor import (
    INTENT_APPROVE_ATTENDANCE_CORRECTION, INTENT_REJECT_ATTENDANCE_CORRECTION, execute_intent,
)
from apps.voice_commands.matcher import get_conversational, get_required_permission

# Mirrors test_approve_reject_leave.py's own shape almost exactly — see that
# file for the leave-approval sibling of every test class here. The one
# structural difference throughout: pending's slot key is 'correction_id',
# not 'request_id' (see executor.py's own execute_intent docstring for why),
# and the underlying REST calls are HRCorrectionListView/HRCorrectionReviewView
# instead of LeaveRequestListCreateView/LeaveApprovalView.

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request(has_attendance_create: bool = True, user_id: int = 42):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_attendance_create
    request = MagicMock()
    request.META = {}
    request.user = SimpleNamespace(role=SimpleNamespace(role_permissions=role_permissions), id=user_id, pk=user_id)
    return request


def _correction_queue_response(rows):
    return MagicMock(
        status_code=200,
        data={'status': 'success', 'message': f'{len(rows)} correction request(s) found.', 'data': {'count': len(rows), 'results': rows}},
    )


def _pending_row(correction_id, name, punch_type='IN', date='2026-07-25', can_action=True):
    return {
        'id': correction_id, 'name': name, 'punch_type': punch_type, 'date': date,
        'status': 'pending', 'can_action': can_action,
    }


class _FakePendingStore:
    """Same in-memory stand-in used throughout this test package for the
    Redis-backed clarification cache — see test_apply_leave_conversation.py."""

    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store):
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch(
            'apps.voice_commands.conversation_attendance_correction_approval.set_pending', side_effect=store.set,
        ),
        patch(
            'apps.voice_commands.conversation_attendance_correction_approval.clear_pending', side_effect=store.clear,
        ),
    )


class ApproveRejectAttendanceCorrectionRegistryTests(SimpleTestCase):
    def test_both_intents_require_attendance_create(self):
        self.assertEqual(get_required_permission(INTENT_APPROVE_ATTENDANCE_CORRECTION), 'attendance.create')
        self.assertEqual(get_required_permission(INTENT_REJECT_ATTENDANCE_CORRECTION), 'attendance.create')

    def test_both_intents_are_conversational(self):
        self.assertTrue(get_conversational(INTENT_APPROVE_ATTENDANCE_CORRECTION))
        self.assertTrue(get_conversational(INTENT_REJECT_ATTENDANCE_CORRECTION))


class PermissionDeniedTests(SimpleTestCase):
    """Mirrors test_approve_reject_leave.py's own PermissionDeniedTests: a
    caller without attendance.create must never reach the correction review
    queue at all, on either intent — proven by asserting the underlying view
    was never called, not just that the message came back wrong."""

    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_approve_denied_without_attendance_create(self, mock_view_cls):
        request = _fake_request(has_attendance_create=False)

        result = execute_intent(
            INTENT_APPROVE_ATTENDANCE_CORRECTION, request, slots={'stage': 'identify', 'name_query': 'ravindra'},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_reject_denied_without_attendance_create(self, mock_view_cls):
        request = _fake_request(has_attendance_create=False)

        result = execute_intent(
            INTENT_REJECT_ATTENDANCE_CORRECTION, request, slots={'stage': 'identify', 'name_query': 'ravindra'},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, _PERMISSION_DENIED_MESSAGE)
        mock_view_cls.as_view.assert_not_called()

    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_conversation_flow_never_reaches_either_view_without_permission(self, mock_list_view, mock_review_view):
        request = _fake_request(has_attendance_create=False)

        result = handle_transcript(request, 'approve attendance correction for ravindra')

        self.assertEqual(result['message'], _PERMISSION_DENIED_MESSAGE)
        self.assertFalse(result['awaiting_input'])
        mock_list_view.as_view.assert_not_called()
        mock_review_view.as_view.assert_not_called()


class NotConfusedWithSelfServiceFilingTests(SimpleTestCase):
    """
    Regression guard for the reported bug (2026-09-24, manager voice
    testing): before approve_attendance_correction/reject_attendance_correction
    existed, "approve attendance correction for ravindra" scored 80.65
    against request_attendance_correction's own "file an attendance
    correction" and silently started the EMPLOYEE self-service filing flow
    under the manager's own account instead. Proven two ways: the matcher
    itself, and the full conversation flow never touching the self-service
    executor.
    """

    def test_matcher_prefers_the_approval_intent(self):
        from apps.voice_commands.matcher import match_intent
        from apps.voice_commands.normalizer import normalize_transcript

        result = match_intent(normalize_transcript('approve attendance correction for ravindra'))

        self.assertEqual(result.intent, INTENT_APPROVE_ATTENDANCE_CORRECTION)
        self.assertNotEqual(result.intent, 'request_attendance_correction')
        self.assertGreaterEqual(result.confidence, 80)

    def test_reject_variant_also_prefers_the_approval_intent(self):
        from apps.voice_commands.matcher import match_intent
        from apps.voice_commands.normalizer import normalize_transcript

        result = match_intent(normalize_transcript('reject attendance correction for ravindra'))

        self.assertEqual(result.intent, INTENT_REJECT_ATTENDANCE_CORRECTION)
        self.assertGreaterEqual(result.confidence, 80)

    def setUp(self):
        # Only test_full_flow_never_starts_the_self_service_filing_flow below
        # actually calls handle_transcript (the two matcher-only tests above
        # never touch pending state) — patched here regardless so real
        # pending state for user 42 never leaks into the real cache and
        # bleeds into a later test class (bit us once during development:
        # PermissionDeniedTests, run after this class alphabetically, found
        # a stale REAL "awaiting_confirmation" pending state for user 42 and
        # treated a fresh command as a yes/no answer instead of hitting the
        # permission gate at all).
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.conversation_attendance_correction.start_request_attendance_correction')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_full_flow_never_starts_the_self_service_filing_flow(
        self, mock_list_view, mock_force_authenticate, mock_start_filing,
    ):
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        request = _fake_request()

        result = handle_transcript(request, 'approve attendance correction for ravindra')

        mock_start_filing.assert_not_called()
        self.assertEqual(result['intent'], INTENT_APPROVE_ATTENDANCE_CORRECTION)
        self.assertTrue(result['awaiting_input'])


class OnlyActionableRequestsAreOfferedTests(SimpleTestCase):
    """A request visible in the queue but not actionable by THIS caller right
    now (services_hr_corrections._build_row's can_action=False — e.g. this
    manager was only the L1 approver on a request that already escalated to
    L2/HR) must never be offered as a match, even though the list view still
    returns the row for visibility."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_not_actionable_row_is_excluded_from_matching(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = _correction_queue_response([
            _pending_row('c-1', 'Ravindra Malladi', can_action=False),
        ])
        request = _fake_request()

        result = handle_transcript(request, 'approve attendance correction for ravindra')

        self.assertIn('no attendance correction', result['message'].lower())
        self.assertFalse(result['awaiting_input'])


class ZeroMatchTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_zero_match_ends_the_flow_with_a_clear_message(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        request = _fake_request()

        result = handle_transcript(request, 'approve attendance correction for nobody special')

        self.assertIn('no attendance correction', result['message'].lower())
        self.assertFalse(result['awaiting_input'])
        self.assertIsNone(self.store.get(42))


class NoNameGivenThenDisambiguationTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_no_name_asks_who_then_resolves_on_the_next_turn(self, mock_view_cls, mock_force_authenticate):
        mock_view_cls.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        request = _fake_request()

        result = handle_transcript(request, 'approve attendance correction')
        self.assertTrue(result['awaiting_input'])
        self.assertIn('whose', result['message'].lower())

        result = handle_transcript(request, 'ravindra malladi')
        self.assertTrue(result['awaiting_input'])
        self.assertIn('ravindra malladi', result['message'].lower())
        self.assertIn('yes or no', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['correction_id'], 'c-1')


class MultipleMatchDisambiguationTests(SimpleTestCase):
    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_ambiguous_name_asks_to_be_more_specific_without_storing_a_correction_id(
        self, mock_view_cls, mock_force_authenticate,
    ):
        mock_view_cls.as_view.return_value.return_value = _correction_queue_response([
            _pending_row('c-1', 'Sam Cooper'),
            _pending_row('c-2', 'Sam Anderson'),
        ])
        request = _fake_request()

        result = handle_transcript(request, 'approve attendance correction for sam')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('more specific', result['message'].lower())
        pending = self.store.get(42)
        self.assertIsNotNone(pending)
        self.assertNotIn('correction_id', pending['slots'])


class SingleMatchThenYesFullFlowTests(SimpleTestCase):
    """The complete happy path: identify a unique actionable match, confirm
    with 'yes', and the real review view is called."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_yes_triggers_the_real_review_call_final_approval(
        self, mock_list_view, mock_review_view, mock_force_authenticate,
    ):
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi', punch_type='IN')],
        )
        mock_review_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={
                'status': 'success', 'message': 'Correction approved. Attendance record updated.',
                'data': {'id': 'c-1', 'status': 'approved', 'name': 'Ravindra Malladi'},
            },
        )
        request = _fake_request()

        first = handle_transcript(request, 'approve attendance correction for ravindra malladi')
        self.assertTrue(first['awaiting_input'])

        second = handle_transcript(request, 'yes')

        self.assertFalse(second['awaiting_input'])
        # execute_confirm_attendance_correction_approval deliberately builds
        # its own bilingual message from data['name']/data['status'] rather
        # than reusing HRCorrectionReviewView's raw (English-only) message
        # verbatim — see that function's own docstring.
        self.assertEqual(second['message'], "Ravindra Malladi's attendance correction has been approved.")
        self.assertIsNone(self.store.get(42))

        mock_review_view.as_view.return_value.assert_called_once()
        call_args = mock_review_view.as_view.return_value.call_args
        self.assertEqual(call_args.kwargs.get('pk'), 'c-1')
        sent_body = json.loads(call_args.args[0].body)
        self.assertEqual(sent_body['action'], 'approve')

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_yes_on_l1_approval_that_escalates_says_sent_to_hr(
        self, mock_list_view, mock_review_view, mock_force_authenticate,
    ):
        """A manager's approval that only clears the L1 stage (an L2/HR
        approver is also configured) must say so — not imply the correction
        is fully done when it's only halfway there."""
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        mock_review_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={
                'status': 'success', 'message': 'Correction approved. Awaiting HR review.',
                'data': {'id': 'c-1', 'status': 'l2_pending', 'name': 'Ravindra Malladi'},
            },
        )
        request = _fake_request()

        handle_transcript(request, 'approve attendance correction for ravindra malladi')
        result = handle_transcript(request, 'yes')

        self.assertEqual(
            result['message'],
            "Ravindra Malladi's attendance correction has been approved and sent to HR for final review.",
        )

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_reject_sends_action_reject(self, mock_list_view, mock_review_view, mock_force_authenticate):
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-9', 'Ravindra Malladi')],
        )
        mock_review_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'status': 'success', 'message': 'Correction rejected.', 'data': {'name': 'Ravindra Malladi', 'status': 'rejected'}},
        )
        request = _fake_request()

        handle_transcript(request, 'reject attendance correction for ravindra malladi')
        result = handle_transcript(request, 'yes')

        self.assertFalse(result['awaiting_input'])
        self.assertEqual(result['message'], "Ravindra Malladi's attendance correction has been rejected.")
        call_args = mock_review_view.as_view.return_value.call_args
        sent_body = json.loads(call_args.args[0].body)
        self.assertEqual(sent_body['action'], 'reject')


class SingleMatchThenNoTests(SimpleTestCase):
    """Declining the confirmation cancels gracefully — the real review view
    must never be called."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_no_cancels_without_calling_the_review_view(self, mock_list_view, mock_force_authenticate, mock_review_view):
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        request = _fake_request()

        handle_transcript(request, 'approve attendance correction for ravindra malladi')
        result = handle_transcript(request, 'no')

        self.assertFalse(result['awaiting_input'])
        self.assertIn('not', result['message'].lower())
        self.assertIsNone(self.store.get(42))
        mock_review_view.as_view.assert_not_called()


class AmbiguousConfirmationAnswerTests(SimpleTestCase):
    """An unclear answer to the yes/no question re-asks rather than guessing."""

    def setUp(self):
        self.store = _FakePendingStore()
        patchers = _patch_pending_store(self.store)
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionListView')
    def test_unclear_answer_reasks_and_keeps_the_pending_correction_id(
        self, mock_list_view, mock_force_authenticate, mock_review_view,
    ):
        mock_list_view.as_view.return_value.return_value = _correction_queue_response(
            [_pending_row('c-1', 'Ravindra Malladi')],
        )
        request = _fake_request()

        handle_transcript(request, 'approve attendance correction for ravindra malladi')
        result = handle_transcript(request, 'maybe later')

        self.assertTrue(result['awaiting_input'])
        self.assertIn('yes or a no', result['message'].lower())
        self.assertEqual(self.store.get(42)['slots']['correction_id'], 'c-1')
        mock_review_view.as_view.assert_not_called()

        mock_review_view.as_view.return_value.return_value = MagicMock(
            status_code=200,
            data={'status': 'success', 'message': 'Correction approved. Attendance record updated.', 'data': {'name': 'Ravindra Malladi', 'status': 'approved'}},
        )
        result = handle_transcript(request, 'yes')
        self.assertFalse(result['awaiting_input'])
        mock_review_view.as_view.return_value.assert_called_once()


class StageIneligibilityStillBlockedTests(SimpleTestCase):
    """
    Not reachable through the normal identify step (the queue query's
    can_action filter already excludes requests this caller can't currently
    act on), but if a correction_id ever reached the confirm stage after the
    caller's eligibility changed in the meantime (e.g. someone else already
    actioned it), HRCorrectionReviewView.patch()'s own
    _can_approve_at_stage/PermissionError check must still apply unchanged —
    voice only relays that response, it never re-implements or bypasses it.
    """

    @patch('apps.voice_commands.executor_approval.force_authenticate')
    @patch('apps.voice_commands.executor_approval.HRCorrectionReviewView')
    def test_confirm_stage_surfaces_the_views_own_rejection(self, mock_review_view, mock_force_authenticate):
        mock_review_view.as_view.return_value.return_value = MagicMock(
            status_code=403,
            data={'status': 'error', 'message': 'You are not authorised to act on this request at the L2 stage.'},
        )
        request = _fake_request()

        result = execute_intent(
            INTENT_APPROVE_ATTENDANCE_CORRECTION, request, slots={'stage': 'confirm', 'correction_id': 'c-stale'},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, 'You are not authorised to act on this request at the L2 stage.')
