"""
apps.voice_commands.sarvam_client is a thin wrapper around the two Sarvam AI
endpoints (chat completions for llm_fallback.py, speech-to-text for
views_transcribe.py). Its entire contract is "return None on ANY failure,
never raise" — both features built on top of it (see llm_fallback.py and
views_transcribe.py) depend on that to fail soft rather than 500ing or
degrading below this app's pre-AI-pivot behavior.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.voice_commands import sarvam_client


class IsConfiguredTests(SimpleTestCase):
    @override_settings(SARVAM_API_KEY='')
    def test_false_when_key_is_blank(self):
        self.assertFalse(sarvam_client.is_configured())

    @override_settings(SARVAM_API_KEY='sk_test_key')
    def test_true_when_key_is_set(self):
        self.assertTrue(sarvam_client.is_configured())


@override_settings(SARVAM_API_KEY='sk_test_key')
class ChatCompletionTests(SimpleTestCase):
    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_message_content_on_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'choices': [{'message': {'content': '{"intent": "clock_in"}'}}]},
        )

        result = sarvam_client.chat_completion(messages=[{'role': 'user', 'content': 'clock me in'}])

        self.assertEqual(result, '{"intent": "clock_in"}')
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['headers']['api-subscription-key'], 'sk_test_key')
        self.assertEqual(call_kwargs['json']['model'], sarvam_client.CHAT_MODEL)
        self.assertEqual(call_kwargs['json']['model'], 'sarvam-105b')  # never the deprecated sarvam-30b

    @override_settings(SARVAM_API_KEY='')
    def test_returns_none_when_key_is_not_configured(self):
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            result = sarvam_client.chat_completion(messages=[])
            mock_post.assert_not_called()
        self.assertIsNone(result)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError('boom')

        result = sarvam_client.chat_completion(messages=[])

        self.assertIsNone(result)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout('boom')

        result = sarvam_client.chat_completion(messages=[])

        self.assertIsNone(result)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_non_2xx_response(self, mock_post):
        response = MagicMock(status_code=500)
        response.raise_for_status.side_effect = requests.HTTPError('server error')
        mock_post.return_value = response

        result = sarvam_client.chat_completion(messages=[])

        self.assertIsNone(result)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_unrecognized_response_shape(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'unexpected': 'shape'})

        result = sarvam_client.chat_completion(messages=[])

        self.assertIsNone(result)


@override_settings(SARVAM_API_KEY='sk_test_key')
class TranscribeAudioTests(SimpleTestCase):
    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_transcript_and_language_code_on_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'transcript': 'I need leave', 'language_code': 'hi-IN', 'language_probability': 0.95},
        )

        result = sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm')

        self.assertEqual(result, {'transcript': 'I need leave', 'language_code': 'hi-IN'})
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['data']['mode'], 'translate')
        self.assertEqual(call_kwargs['data']['model'], sarvam_client.STT_MODEL)
        self.assertNotIn('language_code', call_kwargs['data'])  # auto-detected, never sent on the request

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_empty_transcript(self, mock_post):
        """Silence, or audio Saaras couldn't make out at all — the caller
        (views_transcribe.py) treats this identically to a hard failure."""
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {'transcript': '', 'language_code': None},
        )

        result = sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm')

        self.assertIsNone(result)

    @override_settings(SARVAM_API_KEY='')
    def test_returns_none_when_key_is_not_configured(self):
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            result = sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm')
            mock_post.assert_not_called()
        self.assertIsNone(result)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_none_on_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError('boom')

        result = sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm')

        self.assertIsNone(result)
