"""
apps.voice_commands.views_speak — Phase 2's VoiceSpeakView (POST
/api/voice/speak/). Two test styles, same split as the rest of this test
package:
  - ViewLogicTests calls .post() directly with a MagicMock request (like
    test_voice_parse_view_geolocation.py) — fast, no DB, mocks
    sarvam_client.text_to_speech directly rather than the HTTP layer
    (TextToSpeechTests in test_sarvam_client.py already covers that the
    request itself is built correctly).
  - PermissionEnforcementTests dispatches through APIRequestFactory +
    VoiceSpeakView.as_view() (like test_audit.py) so permission_classes is
    actually exercised — a direct .post() call bypasses DRF's
    dispatch()/check_permissions() entirely, which is exactly what's under
    test here. Uses a bare MagicMock user (is_authenticated set explicitly)
    rather than a real DB-backed User, since IsAuthenticated only reads that
    one attribute — no need for apps.accounts.factories.make_user here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'RIFF....WAVEfmt ')
        self.assertEqual(response['Content-Type'], 'audio/wav')
        mock_tts.assert_called_once_with('Hello', 'en-IN', speaker=sarvam_client.TTS_DEFAULT_SPEAKER)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_always_uses_the_shubh_speaker_regardless_of_language(self, mock_tts):
        mock_tts.return_value = b'audio'

        VoiceSpeakView().post(_fake_request({'text': 'Namaste', 'language_code': 'hi-IN'}))

        self.assertEqual(mock_tts.call_args.kwargs['speaker'], 'shubh')

    def test_missing_text_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView().post(_fake_request({'language_code': 'en-IN'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['status'], 'error')

    def test_blank_text_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView().post(_fake_request({'text': '   ', 'language_code': 'en-IN'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)

    def test_missing_language_code_is_rejected_without_calling_sarvam(self):
        with patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech') as mock_tts:
            response = VoiceSpeakView().post(_fake_request({'text': 'Hello'}))
            mock_tts.assert_not_called()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['status'], 'error')

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_input_error_maps_to_422(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSInputError('text is too long.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['message'], 'text is too long.')

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_auth_error_maps_to_503(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSAuthError('Sarvam rejected the configured API key.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 503)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_config_error_also_maps_to_503(self, mock_tts):
        """SarvamTTSConfigError is a SarvamTTSAuthError subclass — confirms
        the view's isinstance walk (not an exact-type dict lookup) catches
        it via the parent's mapping."""
        mock_tts.side_effect = sarvam_client.SarvamTTSConfigError('SARVAM_API_KEY is not configured.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 503)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_rate_limit_error_maps_to_429(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSRateLimitError('Sarvam rate limit exceeded.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 429)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_timeout_error_maps_to_504(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSTimeoutError('Sarvam did not respond in time.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 504)

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_service_error_maps_to_502(self, mock_tts):
        mock_tts.side_effect = sarvam_client.SarvamTTSServiceError('Sarvam returned HTTP 500.')

        response = VoiceSpeakView().post(_fake_request({'text': 'Hello', 'language_code': 'en-IN'}))

        self.assertEqual(response.status_code, 502)


class PermissionEnforcementTests(SimpleTestCase):
    def test_unauthenticated_request_is_rejected(self):
        request = _api_request_factory.post(
            '/api/voice/speak/', {'text': 'Hello', 'language_code': 'en-IN'}, format='json',
        )

        response = VoiceSpeakView.as_view()(request)

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

        response = VoiceSpeakView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'audio-bytes')
