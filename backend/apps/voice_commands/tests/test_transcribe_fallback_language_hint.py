"""
apps.voice_commands.views_transcribe's Hindi-hint-then-English-hint retry —
added after live testing (2026-08-18) showed Sarvam's own unconstrained
language auto-detection guessing gu-IN/ml-IN/te-IN on every genuine Hindi
attempt, never hi-IN. Extended (2026-08-19) after a real repro showed the
hi-IN-hinted call itself can return a fluent but hallucinated transcript
("Yes, yes, yes, yes, yes." for real spoken input) instead of failing
cleanly — _looks_like_hallucination catches the repeated-word signature of
that failure mode and treats it as a miss, same as an empty transcript.
Mocks sarvam_client.transcribe_audio directly (two calls, one per tier)
rather than the HTTP layer — TranscribeAudioTests in test_sarvam_client.py
already covers that the request itself carries language_code correctly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.views_transcribe import VoiceTranscribeFallbackView, _looks_like_hallucination



# Real WebM/EBML magic bytes (\x1a\x45\xdf\xa3) — views_transcribe.py now
# sniffs an upload's actual leading bytes against its declared Content-Type
# (core/file_validation.py) rather than trusting the header alone, so a
# fixture with no real signature at all gets correctly rejected before ever
# reaching the mocked transcription call these tests exist to check.
_REAL_WEBM_HEADER = b'\x1a\x45\xdf\xa3'


def _fake_request(audio_bytes: bytes = _REAL_WEBM_HEADER + b'fake-audio-bytes', content_type: str = 'audio/webm'):
    uploaded = MagicMock()
    uploaded.content_type = content_type
    uploaded.size = len(audio_bytes)
    uploaded.name = 'clip.webm'
    uploaded.read.return_value = audio_bytes
    # Real file objects (and Django's UploadedFile) support seek(); the
    # content-sniffing helper reads the head then seeks back — a bare
    # MagicMock's auto-generated seek() is harmless as a no-op stand-in here.

    request = MagicMock()
    request.FILES = {'audio': uploaded}
    request.POST = {}
    request.user = MagicMock()
    request.user.is_authenticated = True
    return request


class LanguageHintRetryTests(SimpleTestCase):
    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_hint_success_never_calls_auto_detect(self, mock_transcribe):
        mock_transcribe.return_value = {
            'transcript': 'mujhe leave chahiye', 'language_code': 'hi-IN',
            'language_probability': None, 'was_language_hinted': True,
        }

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 1)
        self.assertEqual(mock_transcribe.call_args.kwargs.get('language_code'), 'hi-IN')
        self.assertEqual(mock_transcribe.call_args.kwargs.get('mode'), 'translate')
        self.assertEqual(response.data['data']['was_language_hinted'], True)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_hint_failure_falls_back_to_english_hint(self, mock_transcribe):
        # First call (hi-IN hinted) returns None (empty transcript/failure),
        # second call is an explicit en-IN hint — never unconstrained
        # auto-detect (see _SECONDARY_LANGUAGE_HINT).
        mock_transcribe.side_effect = [
            None,
            {
                'transcript': 'check my leave balance', 'language_code': 'en-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
        ]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        first_call, second_call = mock_transcribe.call_args_list
        self.assertEqual(first_call.kwargs.get('language_code'), 'hi-IN')
        self.assertEqual(first_call.kwargs.get('mode'), 'translate')
        self.assertEqual(second_call.kwargs.get('language_code'), 'en-IN')
        self.assertEqual(second_call.kwargs.get('mode'), 'translate')
        self.assertEqual(response.data['data']['transcript'], 'check my leave balance')
        self.assertEqual(response.data['data']['was_language_hinted'], True)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_hint_hallucination_falls_back_to_english_hint(self, mock_transcribe):
        # hi-IN hint returns a non-empty but repeated-word hallucination —
        # treated exactly like a None/failure, not accepted as a real result.
        mock_transcribe.side_effect = [
            {
                'transcript': 'Yes, yes, yes, yes, yes.', 'language_code': 'hi-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
            {
                'transcript': 'check my leave balance', 'language_code': 'en-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
        ]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        self.assertEqual(response.data['data']['transcript'], 'check my leave balance')

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_both_tiers_failing_is_still_a_plain_failure(self, mock_transcribe):
        mock_transcribe.side_effect = [None, None]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_both_tiers_hallucinating_is_still_a_plain_failure(self, mock_transcribe):
        mock_transcribe.side_effect = [
            {
                'transcript': 'Yes, yes, yes.', 'language_code': 'hi-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
            {
                'transcript': 'Go go go go.', 'language_code': 'en-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
        ]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')


class DetectedLanguageFieldTests(SimpleTestCase):
    """
    Phase 4 — completes Phase 3.1's Gap 2. was_language_hinted alone can't
    distinguish "Hindi tier succeeded" from "Hindi failed, English fallback
    tier succeeded" (both report was_language_hinted=True — see Phase 3.1's
    own DetectLanguageAmbiguityTests, which pinned this down as a real,
    unfixed gap at the time). detected_language is the new signal that DOES
    distinguish them, known for free from which sequential attempt survived
    — these two tests are the positive mirror of that ambiguity test: same
    two scenarios, but now provably told apart.
    """

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_tier_success_reports_detected_language_hi(self, mock_transcribe):
        mock_transcribe.return_value = {
            'transcript': 'mujhe leave chahiye', 'language_code': 'hi-IN',
            'language_probability': None, 'was_language_hinted': True,
        }

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(response.data['data']['detected_language'], 'hi')
        # was_language_hinted is unchanged/still present — additive, not replaced.
        self.assertEqual(response.data['data']['was_language_hinted'], True)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_english_fallback_tier_success_reports_detected_language_en(self, mock_transcribe):
        # The exact scenario the old boolean-only signal could not tell apart
        # from the Hindi-tier-success case above: hi-IN declines, en-IN wins.
        mock_transcribe.side_effect = [
            None,
            {
                'transcript': 'check my leave balance', 'language_code': 'en-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
        ]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(response.data['data']['detected_language'], 'en')
        # was_language_hinted is STILL True here too — the exact ambiguity
        # detected_language exists to resolve.
        self.assertEqual(response.data['data']['was_language_hinted'], True)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_hallucination_falling_back_to_english_still_reports_en(self, mock_transcribe):
        mock_transcribe.side_effect = [
            {
                'transcript': 'Yes, yes, yes, yes, yes.', 'language_code': 'hi-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
            {
                'transcript': 'check my leave balance', 'language_code': 'en-IN',
                'language_probability': None, 'was_language_hinted': True,
            },
        ]

        response = VoiceTranscribeFallbackView()._post_sync(_fake_request())

        self.assertEqual(response.data['data']['detected_language'], 'en')


class LooksLikeHallucinationTests(SimpleTestCase):
    def test_repeated_single_word_is_flagged(self):
        self.assertTrue(_looks_like_hallucination('Yes, yes, yes, yes, yes.'))
        self.assertTrue(_looks_like_hallucination('go go go go'))

    def test_short_repetition_below_three_is_not_flagged(self):
        self.assertFalse(_looks_like_hallucination('Yes, yes.'))

    def test_non_repetitive_garble_is_not_flagged(self):
        # "Huh? Go, go." from a real 2026-08-19 repro — garbled and wrong,
        # but not a repeated-word loop. The STT-confirmation gate in
        # conversation.py is what catches this one, not this heuristic.
        self.assertFalse(_looks_like_hallucination('Huh? Go, go.'))

    def test_real_transcript_is_not_flagged(self):
        self.assertFalse(_looks_like_hallucination('mujhe leave chahiye'))

    def test_repeated_word_is_flagged_in_non_latin_script_too(self):
        # \w is Unicode-aware — translit's Romanized output is the normal
        # case but not a hard guarantee, so this must not silently pass a
        # Devanagari repeat-loop just because it isn't ASCII.
        self.assertTrue(_looks_like_hallucination('हाँ हाँ हाँ'))
