from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands.views import VoiceParseView


def _fake_request(body: dict):
    request = MagicMock()
    request.data = body
    return request


class VoiceParseViewGeolocationTests(SimpleTestCase):
    """
    Confirms VoiceParseView reads optional latitude/longitude straight off
    the request body and forwards them into handle_transcript() untouched —
    the same values executor.py then carries into PunchWriteSerializer (see
    test_geolocation_forwarding.py for that half of the chain). Calls
    .post() directly rather than going through .as_view()/dispatch — these
    tests only care about request-body parsing, not authentication.
    """

    @patch('apps.voice_commands.views.handle_transcript')
    def test_forwards_latitude_and_longitude_when_present(self, mock_handle_transcript):
        mock_handle_transcript.return_value = {'message': 'ok'}
        request = _fake_request({
            'transcript': 'clock in', 'lang': 'en',
            'latitude': 17.385044, 'longitude': 78.486671,
        })

        VoiceParseView().post(request)

        mock_handle_transcript.assert_called_once_with(
            request, 'clock in', lang='en', latitude=17.385044, longitude=78.486671,
            face_embedding=None, liveness_passed=None, liveness_score=None, capture_session_id='',
            stt_language_probability=None, stt_used_language_hint=False, stt_detected_language=None,
        )

    @patch('apps.voice_commands.views.handle_transcript')
    def test_omitted_latitude_and_longitude_forward_as_none(self, mock_handle_transcript):
        mock_handle_transcript.return_value = {'message': 'ok'}
        request = _fake_request({'transcript': 'clock in', 'lang': 'en'})

        VoiceParseView().post(request)

        mock_handle_transcript.assert_called_once_with(
            request, 'clock in', lang='en', latitude=None, longitude=None,
            face_embedding=None, liveness_passed=None, liveness_score=None, capture_session_id='',
            stt_language_probability=None, stt_used_language_hint=False, stt_detected_language=None,
        )

    @patch('apps.voice_commands.views.handle_transcript')
    def test_forwards_a_recognized_stt_detected_language(self, mock_handle_transcript):
        mock_handle_transcript.return_value = {'message': 'ok'}
        request = _fake_request({'transcript': 'clock in', 'lang': 'en', 'stt_detected_language': 'hi'})

        VoiceParseView().post(request)

        mock_handle_transcript.assert_called_once_with(
            request, 'clock in', lang='en', latitude=None, longitude=None,
            face_embedding=None, liveness_passed=None, liveness_score=None, capture_session_id='',
            stt_language_probability=None, stt_used_language_hint=False, stt_detected_language='hi',
        )

    @patch('apps.voice_commands.views.handle_transcript')
    def test_drops_an_unrecognized_stt_detected_language_rather_than_forwarding_it(self, mock_handle_transcript):
        mock_handle_transcript.return_value = {'message': 'ok'}
        request = _fake_request({'transcript': 'clock in', 'lang': 'en', 'stt_detected_language': 'fr'})

        VoiceParseView().post(request)

        mock_handle_transcript.assert_called_once_with(
            request, 'clock in', lang='en', latitude=None, longitude=None,
            face_embedding=None, liveness_passed=None, liveness_score=None, capture_session_id='',
            stt_language_probability=None, stt_used_language_hint=False, stt_detected_language=None,
        )

    @patch('apps.voice_commands.views.handle_transcript')
    def test_response_data_is_the_handle_transcript_payload(self, mock_handle_transcript):
        payload = {
            'intent': 'clock_in', 'confidence': 100.0, 'result': None,
            'message': 'You have been clocked in successfully.',
            'conversational': False, 'awaiting_input': False, 'success': True,
        }
        mock_handle_transcript.return_value = payload
        request = _fake_request({'transcript': 'clock in', 'lang': 'en'})

        response = VoiceParseView().post(request)

        self.assertEqual(response.data['data'], payload)
        self.assertEqual(response.data['message'], payload['message'])
