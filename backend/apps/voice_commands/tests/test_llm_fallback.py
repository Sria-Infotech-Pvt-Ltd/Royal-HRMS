"""
apps.voice_commands.llm_fallback is classification-only: it must dispatch
through the SAME _dispatch_matched_intent callback a rule match uses, never
trust an intent name outside the fixed allow-list, and fail soft (return
None) on absolutely anything else so conversation.py's handle_transcript
falls back to the exact pre-AI-pivot no-match message. Most tests here mock
dispatch_matched_intent directly to isolate llm_fallback's own classification
logic; PermissionGateStillAppliesTests instead drives the real
conversation.handle_transcript + execute_intent path (only sarvam_client.
chat_completion is mocked) to prove permission gating is genuinely untouched
for an LLM-resolved intent — mirrors test_check_team_attendance.py's
_fake_request(has_permission) pattern.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_CHECK_TEAM_ATTENDANCE, INTENT_CLOCK_IN
from apps.voice_commands.llm_fallback import try_llm_fallback

_PERMISSION_DENIED_MESSAGE = "You don't have permission to do that."


def _fake_request():
    request = MagicMock()
    request.META = {}
    return request


def _fake_dispatch(return_value):
    return MagicMock(return_value=return_value)


class NotConfiguredTests(SimpleTestCase):
    @patch('apps.voice_commands.llm_fallback.sarvam_client.is_configured', return_value=False)
    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_returns_none_without_calling_sarvam_at_all(self, mock_chat, mock_is_configured):
        dispatch = _fake_dispatch({'intent': INTENT_CLOCK_IN})

        result = try_llm_fallback(_fake_request(), 'clock me in somehow', 'clock me in somehow', None, 'en', dispatch)

        self.assertIsNone(result)
        mock_chat.assert_not_called()
        dispatch.assert_not_called()


@patch('apps.voice_commands.llm_fallback.sarvam_client.is_configured', return_value=True)
class ValidClassificationTests(SimpleTestCase):
    @patch('apps.voice_commands.llm_fallback.log_llm_fallback_used')
    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_valid_intent_is_dispatched_via_the_injected_callback(self, mock_chat, mock_log, _mock_configured):
        mock_chat.return_value = '{"intent": "clock_in", "confidence": 0.91}'
        sentinel = {'intent': INTENT_CLOCK_IN, 'message': 'Clocked in.'}
        dispatch = _fake_dispatch(sentinel)
        request = _fake_request()

        result = try_llm_fallback(request, 'yo punch the clock for me', 'yo punch the clock for me', 'office', 'en', dispatch)

        self.assertIs(result, sentinel)
        dispatch.assert_called_once_with(
            request, INTENT_CLOCK_IN, 'yo punch the clock for me', None,
            attendance_mode='office', lang='en', latitude=None, longitude=None,
        )
        mock_log.assert_called_once_with(request, 'yo punch the clock for me', INTENT_CLOCK_IN, 0.91)

    @patch('apps.voice_commands.llm_fallback.log_llm_fallback_used')
    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_forwards_latitude_and_longitude_through_to_dispatch(self, mock_chat, mock_log, _mock_configured):
        # confidence must be >= _LLM_CLARIFICATION_THRESHOLD here — this test
        # is specifically about a DIRECT dispatch's kwargs, not the
        # low-confidence clarification path (see LowConfidenceTests below).
        mock_chat.return_value = '{"intent": "clock_in", "confidence": 0.95}'
        dispatch = _fake_dispatch({'ok': True})
        request = _fake_request()

        try_llm_fallback(
            request, 'clock in', 'clock in', None, 'en', dispatch,
            latitude=17.38, longitude=78.48,
        )

        self.assertEqual(dispatch.call_args.kwargs['latitude'], 17.38)
        self.assertEqual(dispatch.call_args.kwargs['longitude'], 78.48)


@patch('apps.voice_commands.llm_fallback.sarvam_client.is_configured', return_value=True)
@patch('apps.voice_commands.llm_fallback.log_llm_fallback_used')
class RejectedClassificationTests(SimpleTestCase):
    """Every case here must fall through to None, exactly like a Sarvam
    outage — dispatch_matched_intent must never be called."""

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_hallucinated_intent_name_outside_the_allow_list_is_rejected(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = '{"intent": "delete_all_employee_records", "confidence": 0.99}'
        dispatch = _fake_dispatch({'should': 'never see this'})

        result = try_llm_fallback(_fake_request(), 'do something drastic', 'do something drastic', None, 'en', dispatch)

        self.assertIsNone(result)
        dispatch.assert_not_called()

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_model_explicit_no_match_is_rejected(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = '{"intent": "no_match", "confidence": 0.4}'
        dispatch = _fake_dispatch({'should': 'never see this'})

        result = try_llm_fallback(_fake_request(), 'what is the weather', 'what is the weather', None, 'en', dispatch)

        self.assertIsNone(result)
        dispatch.assert_not_called()

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_malformed_json_response_is_rejected(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = 'not json at all'
        dispatch = _fake_dispatch({'should': 'never see this'})

        result = try_llm_fallback(_fake_request(), 'garbled input', 'garbled input', None, 'en', dispatch)

        self.assertIsNone(result)
        dispatch.assert_not_called()

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_json_missing_the_intent_key_is_rejected(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = '{"confidence": 0.9}'
        dispatch = _fake_dispatch({'should': 'never see this'})

        result = try_llm_fallback(_fake_request(), 'garbled input', 'garbled input', None, 'en', dispatch)

        self.assertIsNone(result)
        dispatch.assert_not_called()

    def test_sarvam_call_failure_is_rejected_without_raising(self, _mock_log, _mock_configured):
        # sarvam_client.chat_completion itself already returns None on any
        # network/timeout/HTTP failure (see test_sarvam_client.py) — this
        # confirms try_llm_fallback propagates that as a clean None, not an
        # exception.
        with patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion', return_value=None):
            dispatch = _fake_dispatch({'should': 'never see this'})

            result = try_llm_fallback(_fake_request(), 'clock in', 'clock in', None, 'en', dispatch)

        self.assertIsNone(result)
        dispatch.assert_not_called()


@patch('apps.voice_commands.llm_fallback.sarvam_client.is_configured', return_value=True)
@patch('apps.voice_commands.llm_fallback.log_llm_fallback_used')
class LowConfidenceTests(SimpleTestCase):
    """
    A valid, allow-listed intent below _LLM_CLARIFICATION_THRESHOLD must
    ask before acting (via the same start_clarification 'did you mean X?'
    mechanism the rule engine's middle confidence band uses), never
    dispatch directly — this is the fix for a real, confirmed gap: this
    tier used to dispatch ANY valid intent regardless of the confidence it
    asked the model for and then discarded.
    """

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_low_confidence_valid_intent_asks_instead_of_dispatching(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = '{"intent": "clock_in", "confidence": 0.5}'
        dispatch = _fake_dispatch({'should': 'never see this'})
        request = _fake_request()

        result = try_llm_fallback(request, 'maybe clock in i guess', 'maybe clock in i guess', None, 'en', dispatch)

        dispatch.assert_not_called()
        self.assertIsNotNone(result)
        self.assertTrue(result['awaiting_input'])
        self.assertEqual(result['intent'], INTENT_CLOCK_IN)

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_missing_confidence_field_is_treated_as_low_confidence(self, mock_chat, _mock_log, _mock_configured):
        # No benefit of the doubt for a response that doesn't comply with
        # the requested shape — omission is not "no opinion, dispatch anyway."
        mock_chat.return_value = '{"intent": "clock_in"}'
        dispatch = _fake_dispatch({'should': 'never see this'})
        request = _fake_request()

        result = try_llm_fallback(request, 'clock in', 'clock in', None, 'en', dispatch)

        dispatch.assert_not_called()
        self.assertTrue(result['awaiting_input'])

    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_high_confidence_still_dispatches_directly(self, mock_chat, _mock_log, _mock_configured):
        mock_chat.return_value = '{"intent": "clock_in", "confidence": 0.95}'
        sentinel = {'intent': INTENT_CLOCK_IN}
        dispatch = _fake_dispatch(sentinel)
        request = _fake_request()

        result = try_llm_fallback(request, 'clock me in', 'clock me in', None, 'en', dispatch)

        dispatch.assert_called_once()
        self.assertIs(result, sentinel)


class PermissionGateStillAppliesTests(SimpleTestCase):
    """
    End-to-end through the REAL conversation.handle_transcript + execute_intent
    path (only sarvam_client.chat_completion is mocked) — proves an
    LLM-resolved intent is gated by the exact same registry-declared
    required_permission check a rule match goes through. Mirrors
    test_check_team_attendance.py's _fake_request(has_permission) pattern.
    """

    def _fake_request(self, has_attendance_view: bool):
        role_permissions = MagicMock()
        role_permissions.filter.return_value.exists.return_value = has_attendance_view
        # id AND pk both set — handle_transcript's clarification.get_pending
        # reads user.id, audit.py's log_no_match/_record read user.pk.
        user = SimpleNamespace(id=1, pk=1, role=SimpleNamespace(role_permissions=role_permissions))
        request = MagicMock()
        request.META = {}
        request.user = user
        return request

    @patch('apps.voice_commands.llm_fallback.sarvam_client.is_configured', return_value=True)
    @patch('apps.voice_commands.llm_fallback.sarvam_client.chat_completion')
    def test_llm_resolved_intent_without_permission_is_still_rejected(self, mock_chat, _mock_configured):
        mock_chat.return_value = f'{{"intent": "{INTENT_CHECK_TEAM_ATTENDANCE}", "confidence": 0.88}}'
        request = self._fake_request(has_attendance_view=False)

        from apps.voice_commands.conversation import handle_transcript
        # Deliberately odd phrasing the rule engine's fuzzy matcher won't
        # confidently resolve on its own, so this genuinely reaches the LLM
        # fallback tier rather than a direct rule match.
        result = handle_transcript(request, "give me the lowdown on everyone's clock-ins today")

        self.assertFalse(result['success'])
        self.assertEqual(result['message'], _PERMISSION_DENIED_MESSAGE)
