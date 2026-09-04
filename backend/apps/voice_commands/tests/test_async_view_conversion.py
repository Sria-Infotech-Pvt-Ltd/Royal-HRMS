"""
Scale-1 (2026-08-25 scalability-audit fix, Risk 2) — VoiceSpeakView,
VoiceTranscribeFallbackView, and VoiceParseView were converted from plain
synchronous DRF views to async views (adrf.views.APIView) that dispatch
their unchanged, still-fully-synchronous business logic (_post_sync) via
sync_to_async(thread_sensitive=True). See each view's own post() docstring
for the full reasoning and https://docs.djangoproject.com/en/5.1/topics/
async/ for the underlying asgiref mechanics.

Three things this file proves that the renamed-call-site updates in
test_views_speak.py / test_voice_parse_view_geolocation.py /
test_transcribe_fallback_language_hint.py do not:

  1. RealAsyncDispatchTests — the real, unmodified request pipeline
     (APIRequestFactory + View.as_view(), wrapped in async_to_sync the same
     way Django's own WSGI handler does — django/core/handlers/base.py's
     get_response()) still enforces permission_classes and returns the
     same responses as before, for VoiceParseView and
     VoiceTranscribeFallbackView (VoiceSpeakView's own equivalent already
     lives in test_views_speak.py's PermissionEnforcementTests).

  2. PendingStateConcurrencyTests — two concurrent async requests for the
     SAME user, each running on its own dedicated per-request thread (see
     asgiref.sync.ThreadSensitiveContext, opened once per request the same
     way Django's real ASGIHandler.__call__ does at asgi.py:161), don't
     corrupt each other's Redis-backed pending-conversation state or leak
     local state across each other.

  3. ConcurrentRequestsDoNotBlockEachOtherTests — the actual proof Risk 2
     is fixed, not just that the code compiles: a slow (mocked) Sarvam call
     on one request's dedicated thread does not delay an unrelated
     concurrent request running on its own dedicated thread. Uses a
     lightweight synchronous stand-in for the "unrelated request" (e.g. a
     face-verification punch) rather than a real DB-backed view — this
     shared test environment has no provisioned tenant schema for a real
     DB-backed TestCase (see this app's other tests' own "relation does
     not exist" errors), and a real query from a background thread
     wouldn't participate in TestCase's transaction wrapping anyway. The
     stand-in exercises the identical underlying mechanism (a blocking
     call on one dedicated thread must not block any other thread or the
     event loop) without either pitfall.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

from asgiref.sync import ThreadSensitiveContext, async_to_sync, sync_to_async
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.voice_commands import sarvam_client
from apps.voice_commands.clarification import clear_pending, get_pending, set_pending
from apps.voice_commands.views import VoiceParseView
from apps.voice_commands.views_speak import VoiceSpeakView
from apps.voice_commands.views_transcribe import VoiceTranscribeFallbackView

_api_request_factory = APIRequestFactory()


class RealAsyncDispatchTests(SimpleTestCase):
    """VoiceParseView / VoiceTranscribeFallbackView through real dispatch —
    see this module's own docstring, point 1."""

    def test_voice_parse_view_rejects_unauthenticated_requests(self):
        request = _api_request_factory.post('/api/voice/parse/', {'transcript': 'clock in'}, format='json')

        response = async_to_sync(VoiceParseView.as_view())(request)

        self.assertEqual(response.status_code, 401)

    @patch('apps.voice_commands.views.handle_transcript')
    def test_voice_parse_view_authenticated_request_reaches_the_view(self, mock_handle_transcript):
        mock_handle_transcript.return_value = {
            'intent': 'clock_in', 'confidence': 100.0, 'result': None,
            'message': 'You have been clocked in successfully.',
            'speech_message': None, 'conversational': False,
            'awaiting_input': False, 'success': True, 'language': 'en',
        }
        request = _api_request_factory.post('/api/voice/parse/', {'transcript': 'clock in'}, format='json')
        user = MagicMock()
        user.is_authenticated = True
        force_authenticate(request, user=user)

        response = async_to_sync(VoiceParseView.as_view())(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['intent'], 'clock_in')

    def test_voice_transcribe_fallback_view_rejects_unauthenticated_requests(self):
        request = _api_request_factory.post('/api/voice/transcribe-fallback/', {}, format='multipart')

        response = async_to_sync(VoiceTranscribeFallbackView.as_view())(request)

        self.assertEqual(response.status_code, 401)

    @patch('apps.voice_commands.views_transcribe.sarvam_client.transcribe_audio')
    def test_voice_transcribe_fallback_view_authenticated_request_reaches_the_view(self, mock_transcribe):
        mock_transcribe.return_value = {
            'transcript': 'mujhe leave chahiye', 'language_code': 'hi-IN',
            'language_probability': None, 'was_language_hinted': True,
        }
        uploaded = MagicMock()
        uploaded.content_type = 'audio/webm'
        # Real WebM/EBML magic bytes — views_transcribe.py sniffs actual
        # file content against the declared Content-Type now (see
        # core/file_validation.py); a fixture with no real signature gets
        # correctly rejected before reaching this test's mocked transcribe call.
        audio_bytes = b'\x1a\x45\xdf\xa3' + b'fake-audio'
        uploaded.size = len(audio_bytes)
        uploaded.name = 'clip.webm'
        uploaded.read.return_value = audio_bytes
        request = _api_request_factory.post('/api/voice/transcribe-fallback/', {}, format='multipart')
        request.FILES['audio'] = uploaded
        user = MagicMock()
        user.is_authenticated = True
        force_authenticate(request, user=user)

        response = async_to_sync(VoiceTranscribeFallbackView.as_view())(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['transcript'], 'mujhe leave chahiye')


class PendingStateConcurrencyTests(SimpleTestCase):
    """Two concurrent async requests for the same user must not corrupt
    each other's Redis-backed pending-conversation state — see this
    module's own docstring, point 2.

    Plain `def` test methods driving their own asyncio.run(), NOT `async
    def` — see ConcurrentRequestsDoNotBlockEachOtherTests' own docstring
    for why: Django's test runner invokes an async test method via
    asgiref's async_to_sync, which collapses every ThreadSensitiveContext()
    below onto one shared thread, running "concurrent" work fully
    serialized instead. These two tests would still pass either way (they
    assert eventual-state correctness, not timing), but asyncio.run() here
    makes them genuinely exercise concurrent access, not just sequential
    access that happens to look the same from the outside."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_concurrent_set_and_get_for_the_same_user_do_not_corrupt_state(self):
        user_id = 999001
        clear_pending(user_id)

        async def writer():
            # Own dedicated thread, mirroring what Django's ASGIHandler
            # opens per real incoming request (asgi.py:161) — without this,
            # both coroutines below would share asgiref's single shared
            # executor and run fully serialized, proving nothing about
            # concurrent-request isolation.
            async with ThreadSensitiveContext():
                await sync_to_async(set_pending, thread_sensitive=True)(
                    user_id, 'apply_leave', {'leave_type': 'sick'},
                )
                return await sync_to_async(get_pending, thread_sensitive=True)(user_id)

        async def reader():
            async with ThreadSensitiveContext():
                # A concurrent read from a second request's own dedicated
                # thread must never crash or see a torn/partial write —
                # either None (writer hasn't committed yet) or the writer's
                # complete, correct dict, never anything in between.
                return await sync_to_async(get_pending, thread_sensitive=True)(user_id)

        async def run_both():
            return await asyncio.gather(writer(), reader())

        write_result, read_result = asyncio.run(run_both())

        self.assertEqual(write_result, {'intent': 'apply_leave', 'slots': {'leave_type': 'sick'}})
        self.assertIn(read_result, (None, {'intent': 'apply_leave', 'slots': {'leave_type': 'sick'}}))
        # Final state is exactly what the writer wrote — not merged/corrupted
        # by having run concurrently with an unrelated read.
        self.assertEqual(
            get_pending(user_id), {'intent': 'apply_leave', 'slots': {'leave_type': 'sick'}},
        )

    def test_two_concurrent_writers_for_the_same_user_leave_a_coherent_final_state(self):
        """Whichever write lands last wins — the same behaviour two
        concurrent WSGI workers already had before this conversion (this
        cache key was never request-locked). Confirms the conversion didn't
        make that pre-existing property any worse: no exception, no
        interleaved/corrupted dict, no lost key structure."""
        user_id = 999002
        clear_pending(user_id)

        async def write_leave():
            async with ThreadSensitiveContext():
                await sync_to_async(set_pending, thread_sensitive=True)(
                    user_id, 'apply_leave', {'leave_type': 'sick'},
                )

        async def write_correction():
            async with ThreadSensitiveContext():
                await sync_to_async(set_pending, thread_sensitive=True)(
                    user_id, 'request_attendance_correction', {'date': '2026-08-25'},
                )

        async def run_both():
            await asyncio.gather(write_leave(), write_correction())

        asyncio.run(run_both())

        final = get_pending(user_id)
        self.assertIn(
            final,
            (
                {'intent': 'apply_leave', 'slots': {'leave_type': 'sick'}},
                {'intent': 'request_attendance_correction', 'slots': {'date': '2026-08-25'}},
            ),
        )


class ConcurrentRequestsDoNotBlockEachOtherTests(SimpleTestCase):
    """The actual proof Risk 2 is fixed — see this module's own docstring,
    point 3."""

    @patch('apps.voice_commands.views_speak.sarvam_client.text_to_speech')
    def test_slow_speak_request_does_not_delay_a_concurrent_fast_request(self, mock_tts):
        """Plain `def`, driving its own asyncio.run() — deliberately NOT an
        `async def` test method. Django's own test runner invokes an async
        test method via asgiref's async_to_sync (django/test/testcases.py),
        and async_to_sync has a real, documented, DELIBERATE behaviour: all
        thread_sensitive work anywhere inside it is routed back to run on
        THAT SAME calling thread (so sync code that calls into async code
        that calls back into sync code stays thread-consistent — e.g. for
        Django ORM connection thread-locals). That's correct and desired for
        the app's normal request handling, but it defeats THIS test's whole
        premise: every ThreadSensitiveContext() below would collapse onto
        the one thread async_to_sync reserves, fully serializing "slow" and
        "fast" instead of overlapping them — reproduced directly against a
        minimal asgiref-only repro before writing this comment, confirming
        it's async_to_sync's own behaviour, not a bug in the view
        conversion. A real ASGI server (daphne/uvicorn) never launches
        request handling via async_to_sync in the first place — it runs an
        already-live event loop and dispatches each connection as a plain
        task — so asyncio.run() here (a fresh loop, no ancestor
        async_to_sync launch) is the faithful simulation, and the
        async_to_sync path above is purely a Django-test-runner artifact
        this test must route around, not something the fix needs to handle
        in production."""
        slow_delay_seconds = 1.0
        # Generous relative to the fast work's own true cost (a 10ms sleep)
        # — only needs to prove "not delayed by ~1s", not pin an exact bound.
        fast_budget_seconds = 0.5
        fast_duration = {}

        def slow_text_to_speech(*args, **kwargs):
            time.sleep(slow_delay_seconds)
            return b'audio-bytes'

        mock_tts.side_effect = slow_text_to_speech

        async def run_slow_speak_request():
            async with ThreadSensitiveContext():
                request = _api_request_factory.post(
                    '/api/voice/speak/', {'text': 'Hello', 'language_code': 'en-IN'}, format='json',
                )
                user = MagicMock()
                user.is_authenticated = True
                force_authenticate(request, user=user)
                return await VoiceSpeakView.as_view()(request)

        async def run_fast_unrelated_request():
            # Stands in for e.g. a face-verification punch — a real,
            # unrelated view sharing nothing with VoiceSpeakView except the
            # same ASGI process. What matters is that it runs on its own
            # dedicated thread and is timed independently.
            async with ThreadSensitiveContext():
                start = time.monotonic()
                await sync_to_async(time.sleep, thread_sensitive=True)(0.01)
                fast_duration['seconds'] = time.monotonic() - start

        async def run_both():
            slow_task = asyncio.create_task(run_slow_speak_request())
            await asyncio.sleep(0.05)  # let the slow request actually start first
            await run_fast_unrelated_request()
            return await slow_task

        slow_response = asyncio.run(run_both())

        self.assertEqual(slow_response.status_code, 200)
        self.assertEqual(slow_response.content, b'audio-bytes')
        self.assertLess(
            fast_duration['seconds'], fast_budget_seconds,
            'the fast request was delayed by the slow request — a dedicated-thread '
            'boundary was not actually isolating the two requests.',
        )
