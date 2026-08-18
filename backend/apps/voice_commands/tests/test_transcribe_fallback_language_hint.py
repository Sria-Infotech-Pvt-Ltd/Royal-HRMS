"""
apps.voice_commands.views_transcribe's Hindi-hint-then-auto-detect retry —
added after live testing (2026-08-18) showed Sarvam's own language
auto-detection guessing gu-IN/ml-IN/te-IN on every genuine Hindi attempt,
never hi-IN. Mocks sarvam_client.transcribe_audio directly (two calls, one
per tier) rather than the HTTP layer — TranscribeAudioTests in
test_sarvam_client.py already covers that the request itself carries
language_code correctly.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.views_transcribe import VoiceTranscribeFallbackView


def _fake_request(audio_bytes: bytes = b'fake-audio-bytes', content_type: str = 'audio/webm'):
    uploaded = MagicMock()
    uploaded.content_type = content_type
    uploaded.size = len(audio_bytes)
    uploaded.name = 'clip.webm'
    uploaded.read.return_value = audio_bytes

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

        response = VoiceTranscribeFallbackView().post(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 1)
        self.assertEqual(mock_transcribe.call_args.kwargs.get('language_code'), 'hi-IN')
        self.assertEqual(response.data['data']['was_language_hinted'], True)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_hindi_hint_failure_falls_back_to_auto_detect(self, mock_transcribe):
        # First call (hinted) returns None (empty transcript/failure), second
        # call (no language_code — auto-detect) succeeds.
        mock_transcribe.side_effect = [
            None,
            {
                'transcript': 'check my leave balance', 'language_code': 'en-IN',
                'language_probability': 0.77, 'was_language_hinted': False,
            },
        ]

        response = VoiceTranscribeFallbackView().post(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        first_call, second_call = mock_transcribe.call_args_list
        self.assertEqual(first_call.kwargs.get('language_code'), 'hi-IN')
        self.assertNotIn('language_code', second_call.kwargs)
        self.assertEqual(response.data['data']['transcript'], 'check my leave balance')
        self.assertEqual(response.data['data']['was_language_hinted'], False)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_both_tiers_failing_is_still_a_plain_failure(self, mock_transcribe):
        mock_transcribe.side_effect = [None, None]

        response = VoiceTranscribeFallbackView().post(_fake_request())

        self.assertEqual(mock_transcribe.call_count, 2)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'error')
