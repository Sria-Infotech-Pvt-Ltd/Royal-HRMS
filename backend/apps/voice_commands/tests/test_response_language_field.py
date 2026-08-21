"""
Phase 3's `language` field on the voice-command pipeline's response payload —
present on every response (not just ones with translated text — see
conversation.py's own _payload docstring) and set to "hi" exactly when
stt_used_language_hint was True on THIS request, "en" otherwise. Same
request-construction pattern (a MagicMock request, an unmatchable transcript
that falls through to the flat no-match branch without ever touching a real
database) as test_stt_confirmation_gate.py, which already covers the
STT-confirmation gate this reuses the exact same signal from.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.language import LANG_EN, LANG_HI, set_current_language


def _fake_request(user_id=77):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


# Deliberate gibberish — must not match any real intent, so this reaches the
# lightweight flat no-match branch (no DB, no real User) rather than
# execute_intent(), same reasoning test_stt_confirmation_gate.py documents.
# stt_language_probability=0.9 (or omitted) keeps every case here above the
# STT-confirmation gate's threshold so it never intercepts before the
# language field is even set on the final response.
_UNMATCHABLE_TRANSCRIPT = 'asdkjhasd'


@patch('apps.voice_commands.conversation.get_pending', return_value=None)
class ResponseLanguageFieldTests(SimpleTestCase):
    # handle_transcript sets apps.voice_commands.language's ambient contextvar
    # as a side effect (that's the very thing under test here) — this
    # contextvar is process/thread-ambient, not per-TestCase, so a Hindi-
    # hinted call left unreset would leak into whichever UNRELATED test
    # happens to run next on this thread, including pre-existing executor
    # tests elsewhere in the suite that never touch handle_transcript (and so
    # never get their own reset). setUp AND tearDown both reset, matching
    # test_language.py's own symmetric pattern.
    def setUp(self):
        set_current_language(LANG_EN)

    def tearDown(self):
        set_current_language(LANG_EN)

    def test_language_field_is_present_on_every_response(self, _mock_get_pending):
        result = handle_transcript(_fake_request(), _UNMATCHABLE_TRANSCRIPT)
        self.assertIn('language', result)

    def test_no_hint_at_all_resolves_to_english(self, _mock_get_pending):
        result = handle_transcript(_fake_request(), _UNMATCHABLE_TRANSCRIPT)
        self.assertEqual(result['language'], LANG_EN)

    def test_high_probability_no_hint_resolves_to_english(self, _mock_get_pending):
        """A confidence score alone (auto-detect path) carries no language
        code — see language.detect_language's own docstring — so this stays
        English even with a real Sarvam signal present."""
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT, stt_language_probability=0.9,
        )
        self.assertEqual(result['language'], LANG_EN)

    def test_language_hint_used_resolves_to_hindi(self, _mock_get_pending):
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT,
            stt_language_probability=0.9, stt_used_language_hint=True,
        )
        self.assertEqual(result['language'], LANG_HI)

    def test_hindi_response_carries_the_hindi_no_match_message(self, _mock_get_pending):
        """Confirms the language field isn't just a label sitting next to an
        unaffected English message — handle_transcript's own no-match
        fallback text actually switches too."""
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT,
            stt_language_probability=0.9, stt_used_language_hint=True,
        )
        self.assertEqual(result['language'], LANG_HI)
        self.assertNotEqual(result['message'], "Sorry, I didn't catch that — could you say it differently?")

    def test_consecutive_requests_do_not_leak_language_between_each_other(self, _mock_get_pending):
        """Guards the contextvar design itself (apps.voice_commands.language's
        own docstring) — a Hindi-hinted request must not leave the ambient
        value set for the very next, unrelated request on the same thread."""
        hindi_result = handle_transcript(
            _fake_request(user_id=1), _UNMATCHABLE_TRANSCRIPT,
            stt_language_probability=0.9, stt_used_language_hint=True,
        )
        english_result = handle_transcript(_fake_request(user_id=2), _UNMATCHABLE_TRANSCRIPT)

        self.assertEqual(hindi_result['language'], LANG_HI)
        self.assertEqual(english_result['language'], LANG_EN)


@patch('apps.voice_commands.conversation.get_pending', return_value=None)
class SttDetectedLanguageFieldTests(SimpleTestCase):
    """
    Phase 4 — completes Phase 3.1's Gap 2: stt_detected_language is the
    accurate signal threaded all the way from views_transcribe.py through
    views.py to handle_transcript, preferred over the stt_used_language_hint
    approximation for deciding this field (and which text/voice gets spoken)
    — see language.detect_language's own docstring.
    """

    def setUp(self):
        set_current_language(LANG_EN)

    def tearDown(self):
        set_current_language(LANG_EN)

    def test_detected_language_en_wins_even_when_hint_says_hindi(self, _mock_get_pending):
        # The exact case the OLD signal alone could not resolve: both of
        # views_transcribe.py's hint tiers set was_language_hinted=True, so
        # stt_used_language_hint=True here regardless of which tier actually
        # won — only stt_detected_language can say it was really English.
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT,
            stt_used_language_hint=True, stt_detected_language='en',
        )
        self.assertEqual(result['language'], LANG_EN)

    def test_detected_language_hi_is_honored(self, _mock_get_pending):
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT,
            stt_used_language_hint=True, stt_detected_language='hi',
        )
        self.assertEqual(result['language'], LANG_HI)

    def test_absent_detected_language_falls_back_to_hint_derived_approximation(self, _mock_get_pending):
        result = handle_transcript(
            _fake_request(), _UNMATCHABLE_TRANSCRIPT, stt_used_language_hint=True,
        )
        self.assertEqual(result['language'], LANG_HI)
