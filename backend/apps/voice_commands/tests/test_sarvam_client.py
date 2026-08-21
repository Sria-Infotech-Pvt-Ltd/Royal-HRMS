"""
apps.voice_commands.sarvam_client is a thin wrapper around the two Sarvam AI
endpoints (chat completions for llm_fallback.py, speech-to-text for
views_transcribe.py). Its entire contract is "return None on ANY failure,
never raise" — both features built on top of it (see llm_fallback.py and
views_transcribe.py) depend on that to fail soft rather than 500ing or
degrading below this app's pre-AI-pivot behavior.
"""
from __future__ import annotations

import base64
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

        self.assertEqual(
            result,
            {
                'transcript': 'I need leave', 'language_code': 'hi-IN', 'language_probability': 0.95,
                'was_language_hinted': False,
            },
        )
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['data']['mode'], 'translate')
        self.assertEqual(call_kwargs['data']['model'], sarvam_client.STT_MODEL)
        self.assertNotIn('language_code', call_kwargs['data'])  # auto-detected, never sent on the request

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_language_code_is_sent_and_hint_flag_is_true_when_requested(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'transcript': 'mujhe leave chahiye', 'language_code': 'hi-IN'},
        )

        result = sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm', language_code='hi-IN')

        self.assertEqual(result['was_language_hinted'], True)
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['data']['language_code'], 'hi-IN')

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_mode_defaults_to_translate_but_is_overridable(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'transcript': 'muje clockin karo', 'language_code': 'hi-IN'},
        )

        sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm')
        self.assertEqual(mock_post.call_args.kwargs['data']['mode'], 'translate')

        sarvam_client.transcribe_audio(b'fake-audio-bytes', 'clip.webm', mode='translit')
        self.assertEqual(mock_post.call_args.kwargs['data']['mode'], 'translit')

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


# A real, RFC 4648-valid base64 string decoding to a tiny (non-audio) byte
# sequence — tests only care that decoding happens correctly, not that the
# bytes are a playable WAV file.
_FAKE_AUDIO_B64 = 'UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA='
_FAKE_AUDIO_BYTES = base64.b64decode(_FAKE_AUDIO_B64)


@override_settings(SARVAM_API_KEY='sk_test_key')
class TextToSpeechTests(SimpleTestCase):
    """
    Unlike ChatCompletionTests/TranscribeAudioTests above, text_to_speech()
    does not fail soft to None — it raises typed SarvamTTSError subclasses
    (see sarvam_client.SarvamTTSError's docstring for why). Every failure
    case here asserts the specific exception type raised, not just that
    *something* went wrong.

    time.sleep is patched away for every test in this class (not just the
    retry-specific ones below) so a 429/500/503 response — which now
    triggers real backoff — never actually slows the test suite down,
    whether or not a given test cares about retries.
    """

    def setUp(self):
        sleep_patcher = patch('apps.voice_commands.sarvam_client.time.sleep')
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_returns_decoded_audio_bytes_on_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'request_id': 'req_123', 'audios': [_FAKE_AUDIO_B64]},
        )

        result = sarvam_client.text_to_speech('Welcome to Royal HRMS', 'en-IN')

        self.assertEqual(result, _FAKE_AUDIO_BYTES)
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs['headers']['api-subscription-key'], 'sk_test_key')
        self.assertEqual(call_kwargs['json']['text'], 'Welcome to Royal HRMS')
        self.assertEqual(call_kwargs['json']['language_code'], 'en-IN')
        self.assertEqual(call_kwargs['json']['speaker'], 'shubh')
        self.assertEqual(call_kwargs['json']['model'], sarvam_client.TTS_MODEL)
        self.assertEqual(call_kwargs['json']['model'], 'bulbul:v3')

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_speaker_is_overridable(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {'audios': [_FAKE_AUDIO_B64]},
        )

        sarvam_client.text_to_speech('Hello', 'en-IN', speaker='aditya')

        self.assertEqual(mock_post.call_args.kwargs['json']['speaker'], 'aditya')

    def test_empty_text_raises_input_error_without_calling_sarvam(self):
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            with self.assertRaises(sarvam_client.SarvamTTSInputError):
                sarvam_client.text_to_speech('   ', 'en-IN')
            mock_post.assert_not_called()

    def test_text_over_the_character_limit_raises_input_error_without_calling_sarvam(self):
        too_long = 'a' * (sarvam_client.TTS_MAX_TEXT_LENGTH + 1)
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            with self.assertRaises(sarvam_client.SarvamTTSInputError):
                sarvam_client.text_to_speech(too_long, 'en-IN')
            mock_post.assert_not_called()

    def test_text_exactly_at_the_character_limit_is_allowed(self):
        exactly_max = 'a' * sarvam_client.TTS_MAX_TEXT_LENGTH
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200, json=lambda: {'audios': [_FAKE_AUDIO_B64]},
            )
            sarvam_client.text_to_speech(exactly_max, 'en-IN')
            mock_post.assert_called_once()

    @override_settings(SARVAM_API_KEY='')
    def test_not_configured_raises_config_error_without_calling_sarvam(self):
        with patch('apps.voice_commands.sarvam_client.requests.post') as mock_post:
            with self.assertRaises(sarvam_client.SarvamTTSConfigError):
                sarvam_client.text_to_speech('Hello', 'en-IN')
            mock_post.assert_not_called()

    def test_config_error_is_also_an_auth_error(self):
        """SarvamTTSConfigError subclasses SarvamTTSAuthError — a caller that
        only wants to distinguish "auth-shaped" failures can catch the
        parent and still see this one (see views_speak.py's status mapping)."""
        with override_settings(SARVAM_API_KEY=''):
            with self.assertRaises(sarvam_client.SarvamTTSAuthError):
                sarvam_client.text_to_speech('Hello', 'en-IN')

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_403_raises_auth_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=403, text='invalid_api_key_error')

        with self.assertRaises(sarvam_client.SarvamTTSAuthError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)  # not retryable — never worth a second try
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_429_raises_rate_limit_error_after_exhausting_retries(self, mock_post):
        mock_post.return_value = MagicMock(status_code=429, text='rate_limit_exceeded_error')

        with self.assertRaises(sarvam_client.SarvamTTSRateLimitError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, sarvam_client._TTS_MAX_ATTEMPTS)
        self.assertEqual(self.mock_sleep.call_count, sarvam_client._TTS_MAX_ATTEMPTS - 1)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_503_also_raises_rate_limit_error_after_exhausting_retries(self, mock_post):
        """Documented (docs.sarvam.ai/api/getting-started/ratelimits) as
        "handled identically" to 429 for this endpoint — see
        SarvamTTSRateLimitError's docstring."""
        mock_post.return_value = MagicMock(status_code=503, text='backend overloaded')

        with self.assertRaises(sarvam_client.SarvamTTSRateLimitError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, sarvam_client._TTS_MAX_ATTEMPTS)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_429_then_success_returns_audio_without_exhausting_the_budget(self, mock_post):
        """A transient rate-limit that clears on retry must not surface as a
        failure at all — the whole point of retrying."""
        mock_post.side_effect = [
            MagicMock(status_code=429, text='rate_limit_exceeded_error'),
            MagicMock(status_code=200, json=lambda: {'audios': [_FAKE_AUDIO_B64]}),
        ]

        result = sarvam_client.text_to_speech('Hello', 'en-IN')

        self.assertEqual(result, _FAKE_AUDIO_BYTES)
        self.assertEqual(mock_post.call_count, 2)
        self.mock_sleep.assert_called_once_with(sarvam_client._TTS_RETRY_BACKOFF_SECONDS[0])

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_backoff_grows_between_successive_retries(self, mock_post):
        mock_post.side_effect = [
            MagicMock(status_code=503, text='backend overloaded'),
            MagicMock(status_code=503, text='backend overloaded'),
            MagicMock(status_code=200, json=lambda: {'audios': [_FAKE_AUDIO_B64]}),
        ]

        sarvam_client.text_to_speech('Hello', 'en-IN')

        self.assertEqual(
            [call.args[0] for call in self.mock_sleep.call_args_list],
            list(sarvam_client._TTS_RETRY_BACKOFF_SECONDS),
        )

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_400_raises_input_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=400, text='invalid language_code')

        with self.assertRaises(sarvam_client.SarvamTTSInputError):
            sarvam_client.text_to_speech('Hello', 'xx-XX')
        self.assertEqual(mock_post.call_count, 1)
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_422_raises_input_error_without_retrying(self, mock_post):
        mock_post.return_value = MagicMock(status_code=422, text='unprocessable_entity_error')

        with self.assertRaises(sarvam_client.SarvamTTSInputError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)  # a client input error — retrying can't fix it
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_timeout_raises_timeout_error_without_retrying(self, mock_post):
        mock_post.side_effect = requests.Timeout('boom')

        with self.assertRaises(sarvam_client.SarvamTTSTimeoutError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_network_error_raises_service_error_without_retrying(self, mock_post):
        mock_post.side_effect = requests.ConnectionError('boom')

        with self.assertRaises(sarvam_client.SarvamTTSServiceError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_bare_500_raises_service_error_after_exhausting_retries(self, mock_post):
        response = MagicMock(status_code=500, text='internal_server_error')
        response.raise_for_status.side_effect = requests.HTTPError('server error', response=response)
        mock_post.return_value = response

        with self.assertRaises(sarvam_client.SarvamTTSServiceError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, sarvam_client._TTS_MAX_ATTEMPTS)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_500_then_success_returns_audio(self, mock_post):
        response_500 = MagicMock(status_code=500, text='internal_server_error')
        response_500.raise_for_status.side_effect = requests.HTTPError('server error', response=response_500)
        mock_post.side_effect = [response_500, MagicMock(status_code=200, json=lambda: {'audios': [_FAKE_AUDIO_B64]})]

        result = sarvam_client.text_to_speech('Hello', 'en-IN')

        self.assertEqual(result, _FAKE_AUDIO_BYTES)
        self.assertEqual(mock_post.call_count, 2)

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_501_raises_service_error_without_retrying(self, mock_post):
        """501 is a non-2xx failure but not one of the three documented
        retryable statuses (429/500/503) — still falls through to the
        existing generic raise_for_status() branch, unretried, exactly like
        Phase 2."""
        response = MagicMock(status_code=501, text='not_implemented')
        response.raise_for_status.side_effect = requests.HTTPError('not implemented', response=response)
        mock_post.return_value = response

        with self.assertRaises(sarvam_client.SarvamTTSServiceError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)
        self.mock_sleep.assert_not_called()

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_unrecognized_response_shape_raises_service_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'unexpected': 'shape'})

        with self.assertRaises(sarvam_client.SarvamTTSServiceError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
        self.assertEqual(mock_post.call_count, 1)  # a malformed 2xx isn't a retryable status

    @patch('apps.voice_commands.sarvam_client.requests.post')
    def test_empty_audios_array_raises_service_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'audios': []})

        with self.assertRaises(sarvam_client.SarvamTTSServiceError):
            sarvam_client.text_to_speech('Hello', 'en-IN')
