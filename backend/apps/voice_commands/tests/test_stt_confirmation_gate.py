"""
apps.voice_commands.conversation.handle_transcript's STT-confirmation gate —
covers both the pre-existing language_probability threshold check and the
stt_used_language_hint addition (2026-08-18): a transcript from the Sarvam
retry's explicit-Hindi-hint attempt never gets a language_probability back
from Sarvam at all (confirmed against real docs.sarvam.ai docs), so the gate
must confirm regardless rather than read "no signal" as "trustworthy."
Critically, a transcript with NEITHER signal (typed input, or browser
SpeechRecognition output) must still skip confirmation entirely — that's the
overwhelming majority of traffic and must not regress.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript


def _fake_request(user_id=77):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


@patch('apps.voice_commands.conversation.get_pending', return_value=None)
@patch('apps.voice_commands.conversation.start_stt_confirmation')
class SttConfirmationGateTests(SimpleTestCase):
    # Deliberate gibberish — must not match any real intent, so a "skips
    # confirmation" case falls through to the lightweight flat no-match
    # branch instead of reaching match_intent/execute_intent for real (which
    # would need an actual User model instance, not this fake request's
    # MagicMock user, to run a real DB-backed intent). The gate decision
    # itself is independent of what happens to the transcript afterward.
    _UNMATCHABLE_TRANSCRIPT = 'asdkjhasd'

    def test_no_signal_at_all_skips_confirmation(self, mock_start_confirmation, _mock_get_pending):
        """Typed input or browser SpeechRecognition output — neither
        stt_language_probability nor stt_used_language_hint set. The
        overwhelming majority of traffic; must never be gated."""
        handle_transcript(_fake_request(), self._UNMATCHABLE_TRANSCRIPT)

        mock_start_confirmation.assert_not_called()

    def test_high_probability_skips_confirmation(self, mock_start_confirmation, _mock_get_pending):
        handle_transcript(_fake_request(), self._UNMATCHABLE_TRANSCRIPT, stt_language_probability=0.9)

        mock_start_confirmation.assert_not_called()

    def test_low_probability_triggers_confirmation(self, mock_start_confirmation, _mock_get_pending):
        handle_transcript(_fake_request(), self._UNMATCHABLE_TRANSCRIPT, stt_language_probability=0.3)

        mock_start_confirmation.assert_called_once()

    def test_language_hint_with_no_probability_triggers_confirmation(self, mock_start_confirmation, _mock_get_pending):
        """The new case: hinted STT gets no language_probability from Sarvam
        at all (None), but stt_used_language_hint=True must still gate it —
        "no signal" must not read as "trustworthy" here."""
        handle_transcript(
            _fake_request(), self._UNMATCHABLE_TRANSCRIPT,
            stt_language_probability=None, stt_used_language_hint=True,
        )

        mock_start_confirmation.assert_called_once()
