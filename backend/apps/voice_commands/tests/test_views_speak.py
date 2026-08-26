"""
apps.voice_commands.views_speak — Phase 2's VoiceSpeakView (POST
/api/voice/speak/). Two test styles, same split as the rest of this test
package:
  - ViewLogicTests calls ._post_sync() directly with a MagicMock request
    (like test_voice_parse_view_geolocation.py) — fast, no DB, mocks
    sarvam_client.text_to_speech directly rather than the HTTP layer
    (TextToSpeechTests in test_sarvam_client.py already covers that the
    request itself is built correctly). Targets _post_sync — the real,
    unchanged view logic — rather than the now-async post(), which just
    dispatches to it via sync_to_async (see views_speak.py's own docstring,
    Scale-1 2026-08-25); calling post() directly here would return an
    un-awaited coroutine, not a Response.
  - PermissionEnforcementTests dispatches through APIRequestFactory +
    VoiceSpeakView.as_view() (like test_audit.py) so permission_classes is
    actually exercised — a direct ._post_sync() call bypasses DRF's
    dispatch()/check_permissions() entirely, which is exactly what's under
    test here. Uses a bare MagicMock user (is_authenticated set explicitly)
    rather than a real DB-backed User, since IsAuthenticated only reads that
    one attribute — no need for apps.accounts.factories.make_user here.
    Wrapped in async_to_sync since VoiceSpeakView is now async — the same
    bridge Django's own WSGI handler applies in production (see
    django/core/handlers/base.py's get_response()), so this is a faithful
    simulation of a real request, not a workaround.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.voice_commands import sarvam_client
from apps.voice_commands.views_speak import VoiceSpeakView

_api_request_factory = APIRequestFactory()


def _fake_request(body: dict):
    request = MagicMock()
    request.data = body
    return request


class ViewLogicTests(SimpleTestCase):
    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_successful_request_returns_wav_audio_bytes(self, mock_tts):
        mock_tts.return_value = b'RIFF....WAVEfmt '

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'RIFF....WAVEfmt ')
        self.assertEqual(response['Content-Type'], 'audio/wav')
        mock_tts.assert_called_once_with('Hello', 'en-IN', speaker=sarvam_client.TTS_DEFAULT_SPEAKER)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_always_uses_the_shubh_speaker_regardless_of_language(self, mock_tts):
        mock_tts.return_value = b'audio'

        VoiceSpeakView()._post_sync(_fake_request({'text': 'Namaste', 'language_code': 'hi-IN'}))

        self.assertEqual(mock_tts.call_args.kwargs['speaker'], 'shubh')

    def test_missing_text_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView()._post_sync(_fake_request({'language_code': 'en-IN'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['status'], 'error')

    def test_blank_text_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView()._post_sync(_fake_request({'text': '   ', 'language_code': 'en-IN'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)

    def test_missing_language_code_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['status'], 'error')

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_input_error_maps_to_422(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSInputError('text is too long.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['message'], 'text is too long.')

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_auth_error_maps_to_503(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSAuthError('Sarvam rejected the configured API key.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 503)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_config_error_also_maps_to_503(self, mock_tts):
        """SarvamTTSConfigError is a SarvamTTSAuthError subclass — confirms
        the view's isinstance walk (not an exact-type dict lookup) catches
        it via the parent's mapping."""
        mock_tts.side_effect = sarvam_client.SarvamTTSConfigError('SARVAM_API_KEY is not configured.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 503)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_rate_limit_error_maps_to_429(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSRateLimitError('Sarvam rate limit exceeded.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 429)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_timeout_error_maps_to_504(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSTimeoutError('Sarvam did not respond in time.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 504)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_service_error_maps_to_502(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSServiceError('Sarvam returned HTTP 500.')

        response = VoiceSpeakView()._post_sync(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 502)


class PermissionEnforcementTests(SimpleTestCase):
    def test_unauthenticated_request_is_rejected(self):
        request = _api_request_factory.post(
            '/api/voice/speak/', {'text': 'Hello', 'language_code': 'en-IN'}, format='json',
        )

        response = async_to_sync(VoiceSpeakView.as_view())(request)

        # 401, not 403 — CookieJWTAuthentication (config/settings.py's
        # DEFAULT_AUTHENTICATION_CLASSES) extends simplejwt's
        # JWTAuthentication, which implements authenticate_header(), so DRF
        # reports "no credentials at all" as 401 Unauthorized rather than
        # 403 Forbidden. Confirmed by actually dispatching the view here
        # rather than assumed.
        self.assertEqual(response.status_code, 401)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_authenticated_request_reaches_the_view(self, mock_tts):
        mock_tts.return_value = b'audio-bytes'
        user = MagicMock()
        user.is_authenticated = True
        request = _api_request_factory.post(
            '/api/voice/speak/', {'text': 'Hello', 'language_code': 'en-IN'}, format='json',
        )
        force_authenticate(request, user=user)

        response = async_to_sync(VoiceSpeakView.as_view())(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'audio-bytes')
