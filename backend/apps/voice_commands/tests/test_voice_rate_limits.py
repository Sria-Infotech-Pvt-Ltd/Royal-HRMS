"""
Phase 7.3: per-user rate limits on the paid voice paths (speak, transcribe, AI intent fallback).

Uses the project's existing DRF throttle mechanism (scope -> rate in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], rates
configurable by env). Rates are patched per test (the throttle classes read them at class level), and every test starts
from an empty cache so counters never leak between tests. No database is touched.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

from apps.voice_commands import llm_fallback
from apps.voice_commands.conversation import _NO_MATCH_MESSAGE, handle_transcript
from apps.voice_commands.language import text
from apps.voice_commands.throttles import VoiceLLMRateThrottle, llm_fallback_allowed
from apps.voice_commands.views_speak import VoiceSpeakView
from apps.voice_commands.views_transcribe import VoiceTranscribeFallbackView

_factory = APIRequestFactory()
_WEBM = b'\x1a\x45\xdf\xa3' + b'fake-audio-bytes'


def _user(tag: str):
    user = MagicMock()
    user.is_authenticated = True
    user.pk = f'rate-limit-user-{tag}'
    user.id = user.pk
    return user


def _speak(user, view=None):
    request = _factory.post('/api/voice/speak/', {'text': 'Hello', 'language_code': 'en-IN'}, format='json')
    force_authenticate(request, user=user)
    return async_to_sync((view or VoiceSpeakView).as_view())(request)


def _transcribe(user):
    request = _factory.post(
        '/api/voice/transcribe-fallback/',
        {'audio': SimpleUploadedFile('clip.webm', _WEBM, content_type='audio/webm')}, format='multipart',
    )
    force_authenticate(request, user=user)
    return async_to_sync(VoiceTranscribeFallbackView.as_view())(request)


def _rates(**overrides):
    return patch.dict(SimpleRateThrottle.THROTTLE_RATES, overrides)


class _Base(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)


class ConfigurationTests(SimpleTestCase):
    def test_the_three_paid_scopes_have_configurable_hourly_rates_in_settings(self):
        rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
        for scope in ('voice_speak', 'voice_transcribe', 'voice_llm'):
            with self.subTest(scope):
                self.assertRegex(rates[scope], r'^\d+/(second|minute|hour|day)$')

    def test_settings_read_the_documented_env_variable_names(self):
        source = open(settings.BASE_DIR / 'config' / 'settings.py', encoding='utf8').read()
        for name in ('VOICE_SPEAK_RATE', 'VOICE_TRANSCRIBE_RATE', 'VOICE_LLM_RATE'):
            self.assertIn(f"env('{name}'", source)

    def test_paid_views_keep_the_project_default_throttles_and_add_their_own(self):
        for view in (VoiceSpeakView, VoiceTranscribeFallbackView):
            with self.subTest(view.__name__):
                classes = view.throttle_classes
                self.assertIn(UserRateThrottle, classes)
                self.assertIn(AnonRateThrottle, classes)
                self.assertTrue(any(c.scope in ('voice_speak', 'voice_transcribe') for c in classes if hasattr(c, 'scope')
                                    and c not in (UserRateThrottle, AnonRateThrottle)))

    def test_distinct_scopes_so_the_limits_are_independent(self):
        scopes = {VoiceLLMRateThrottle.scope}
        scopes.update(c.scope for c in VoiceSpeakView.throttle_classes if c.scope.startswith('voice_'))
        scopes.update(c.scope for c in VoiceTranscribeFallbackView.throttle_classes if c.scope.startswith('voice_'))
        self.assertEqual(scopes, {'voice_speak', 'voice_transcribe', 'voice_llm'})


class SpeakRateLimitTests(_Base):
    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech', return_value=b'RIFF....WAVEfmt ')
    def test_requests_under_the_limit_are_allowed_and_the_next_is_blocked_with_429(self, _tts):
        user = _user('speak')
        with _rates(voice_speak='2/hour'):
            self.assertEqual(_speak(user).status_code, 200)
            self.assertEqual(_speak(user).status_code, 200)
            blocked = _speak(user)
        self.assertEqual(blocked.status_code, 429)
        body = blocked.data
        self.assertEqual(body['status'], 'error')  # the project's standard error envelope the client already handles
        self.assertIn('throttled', body['message'].lower())
        self.assertIn('seconds', body['message'])  # DRF's own "available in N seconds" text is kept

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech', return_value=b'RIFF....WAVEfmt ')
    def test_the_limit_is_per_user(self, _tts):
        with _rates(voice_speak='1/hour'):
            self.assertEqual(_speak(_user('a')).status_code, 200)
            self.assertEqual(_speak(_user('a')).status_code, 429)
            self.assertEqual(_speak(_user('b')).status_code, 200)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_a_blocked_request_never_reaches_the_paid_provider(self, mock_tts):
        mock_tts.return_value = b'audio'
        user = _user('provider')
        with _rates(voice_speak='1/hour'):
            _speak(user)
            _speak(user)
        self.assertEqual(mock_tts.call_count, 1)


class TranscribeRateLimitTests(_Base):
    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_allowed_then_blocked_and_the_provider_is_not_called_when_blocked(self, mock_transcribe):
        mock_transcribe.return_value = {
            'transcript': 'check my leave balance', 'language_code': 'hi-IN',
            'language_probability': None, 'was_language_hinted': True,
        }
        user = _user('transcribe')
        with _rates(voice_transcribe='1/hour'):
            first = _transcribe(user)
            blocked = _transcribe(user)
        self.assertEqual(first.status_code, 200, getattr(first, 'data', None))
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(mock_transcribe.call_count, 1)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio', return_value=None)
    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech', return_value=b'audio')
    def test_each_paid_path_has_its_own_counter(self, _tts, _stt):
        user = _user('independent')
        with _rates(voice_speak='1/hour', voice_transcribe='1/hour'):
            self.assertEqual(_speak(user).status_code, 200)
            self.assertEqual(_speak(user).status_code, 429)
            self.assertNotEqual(_transcribe(user).status_code, 429)  # speak being exhausted does not touch transcribe


class LLMFallbackRateLimitTests(_Base):
    def _request(self, tag='llm'):
        request = MagicMock()
        request.user = _user(tag)
        request.META = {}
        return request

    def _call(self, request):
        return llm_fallback.try_llm_fallback(request, 'something unmatched', 'something unmatched', None, 'en', MagicMock())

    @patch('apps.voice_commands.llm_fallback.sarvam_client')
    def test_calls_under_the_limit_reach_the_provider_and_the_next_is_skipped(self, mock_client):
        mock_client.is_configured.return_value = True
        mock_client.chat_completion.return_value = json.dumps({'intent': 'no_match'})
        request = self._request()
        with _rates(voice_llm='2/hour'):
            for _ in range(3):
                self.assertIsNone(self._call(request))
        self.assertEqual(mock_client.chat_completion.call_count, 2)

    @patch('apps.voice_commands.llm_fallback.sarvam_client')
    def test_the_limit_is_per_user(self, mock_client):
        mock_client.is_configured.return_value = True
        mock_client.chat_completion.return_value = json.dumps({'intent': 'no_match'})
        with _rates(voice_llm='1/hour'):
            self._call(self._request('one'))
            self._call(self._request('one'))
            self._call(self._request('two'))
        self.assertEqual(mock_client.chat_completion.call_count, 2)  # one for 'one', one for 'two'

    @patch('apps.voice_commands.llm_fallback.sarvam_client')
    def test_a_limited_user_gets_the_ordinary_no_match_answer_not_an_error(self, mock_client):
        """The frontend flow is not broken: skipping the AI step looks exactly like the AI declining."""
        mock_client.is_configured.return_value = True
        request = self._request('flow')
        request.is_secure.return_value = True
        with _rates(voice_llm='0/hour'):
            payload = handle_transcript(request, 'what is the weather in paris')
        mock_client.chat_completion.assert_not_called()
        self.assertEqual(payload['message'], text(_NO_MATCH_MESSAGE))
        self.assertFalse(payload['success'])
        self.assertFalse(payload['awaiting_input'])
        self.assertIn('is_clarification', payload)

    def test_the_rule_engine_path_is_not_limited_at_all(self):
        request = self._request('free')
        request.is_secure.return_value = True
        with _rates(voice_llm='0/hour'), patch('apps.voice_commands.conversation.execute_intent') as mock_execute:
            mock_execute.return_value = SimpleNamespace(success=True, message='hi', data=None, speech_message=None)
            payload = handle_transcript(request, 'hello')
        self.assertTrue(payload['success'])

    @patch('apps.voice_commands.llm_fallback.sarvam_client')
    def test_it_fails_open_when_the_rate_check_itself_errors(self, mock_client):
        mock_client.is_configured.return_value = True
        mock_client.chat_completion.return_value = json.dumps({'intent': 'no_match'})
        with patch.object(VoiceLLMRateThrottle, 'allow_request', side_effect=RuntimeError('cache down')):
            self.assertTrue(llm_fallback_allowed(self._request('open')))
            self._call(self._request('open'))
        mock_client.chat_completion.assert_called_once()
