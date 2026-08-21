"""
Phase 3.1 — Gap 2: the language-detection signal fix.

Two things are covered here, matching the task's own two possible outcomes
for Gap 2 ("fix the signal, or explain why no more accurate one exists"):

1. DetectLanguageAmbiguityTests documents the actual limitation found while
   investigating Gap 2: stt_used_language_hint (as set by views_transcribe.py
   and threaded through by useVoiceCommand.ts — see language.detect_language's
   own docstring) is True whenever EITHER of views_transcribe.py's two hint
   tiers succeeds (hi-IN tried first, falling back to an explicit en-IN hint
   — see that module's docstring), so detect_language cannot and does not
   distinguish "Hindi STT succeeded" from "Hindi failed, English fallback
   succeeded, but the flag is still true." No additional field crosses the
   wire to /voice/parse/ that WOULD let it — views_transcribe.py itself knows
   which tier won, but that fact is discarded before reaching this app's
   /voice/parse/ request body (useVoiceCommand.ts is what would need to
   thread it through, and that file is out of scope for this phase — see the
   Phase 3.1 task report for the proposed minimal fix). This test pins that
   documented limitation down as an explicit, intentional assertion (both
   "succeeded via Hindi" and "succeeded via English fallback" resolve to the
   SAME detect_language() output) so a future fix has a red test to turn
   green, rather than the ambiguity silently drifting further from being
   noticed.

2. SttConfirmationLanguageReplayTests covers the real, fixable bug this
   investigation surfaced along the way: a leaked-contextvar bug of the same
   class Phase 3 already had to catch once (see test_response_language_field.py's
   own docstring on that). continue_stt_confirmation's "yes" branch re-enters
   handle_transcript on the now-confirmed original transcript — a SECOND call
   to handle_transcript within the same HTTP request/response cycle, and
   handle_transcript unconditionally re-runs set_current_language() as its
   first line on every call. Without replaying the language the ORIGINAL turn
   resolved to (see conversation.py's response_language parameter and
   conversation_stt_confirmation.py's own docstrings), that re-entrant call
   would silently reset to English regardless of what language the confirmed
   transcript was actually in. Covers both directions (Hindi-resolved,
   English-resolved) and confirms the replay does not re-trigger the
   STT-confirmation gate itself (pending is already cleared; stt_used_language_hint
   is deliberately NOT what's replayed — see handle_transcript's own
   response_language docstring for why re-using that parameter for this would
   loop the confirmation question on itself forever).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import language
from apps.voice_commands.conversation import handle_transcript
from apps.voice_commands.language import LANG_EN, LANG_HI, detect_language


class DetectLanguageAmbiguityTests(SimpleTestCase):
    """Pins down the documented Gap 2 finding: the boolean signal cannot
    distinguish which Sarvam-STT hint tier actually succeeded."""

    def test_hindi_hint_tier_success_resolves_to_hindi(self):
        # views_transcribe.py's PRIMARY (hi-IN) tier succeeding sets
        # was_language_hinted=True, threaded through as stt_used_language_hint=True.
        self.assertEqual(detect_language(stt_used_language_hint=True), LANG_HI)

    def test_english_fallback_tier_success_ALSO_resolves_to_hindi(self):
        """
        The actual gap: views_transcribe.py's SECONDARY (en-IN) fallback tier
        succeeding ALSO sets was_language_hinted=True (both tiers pass an
        explicit language hint — see that module's own docstring), which
        useVoiceCommand.ts threads through as the exact same
        stt_used_language_hint=True. There is currently no way for the
        backend to tell these two cases apart from what crosses the wire —
        this test documents that both inputs are indistinguishable to
        detect_language, not that this is desired behavior.
        """
        self.assertEqual(
            detect_language(stt_used_language_hint=True),
            detect_language(stt_used_language_hint=True),
        )
        # Spelled out explicitly rather than just the tautology above — the
        # SAME boolean value is genuinely all that reaches this function for
        # both the "Hindi succeeded" and "English fallback succeeded" cases.
        hindi_tier_succeeded = True
        english_fallback_tier_succeeded = True  # also reported as True — the gap
        self.assertEqual(
            detect_language(hindi_tier_succeeded), detect_language(english_fallback_tier_succeeded),
        )
        self.assertEqual(detect_language(english_fallback_tier_succeeded), LANG_HI)


def _fake_request(user_id=555):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


class _FakePendingStore:
    """Same in-memory stand-in for the Redis-backed clarification cache used
    throughout this test package — see test_apply_leave_conversation.py."""

    def __init__(self):
        self._store = {}

    def get(self, user_id):
        return self._store.get(user_id)

    def set(self, user_id, intent, slots):
        self._store[user_id] = {'intent': intent, 'slots': dict(slots)}

    def clear(self, user_id):
        self._store.pop(user_id, None)


def _patch_pending_store(store: _FakePendingStore):
    # conversation.py and conversation_stt_confirmation.py each bind their
    # own set_pending/get_pending/clear_pending import (to avoid a circular
    # import back into conversation.py — see conversation_stt_confirmation.py's
    # own docstring), so both bindings need patching.
    return (
        patch('apps.voice_commands.conversation.get_pending', side_effect=store.get),
        patch('apps.voice_commands.conversation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation.clear_pending', side_effect=store.clear),
        patch('apps.voice_commands.conversation_stt_confirmation.set_pending', side_effect=store.set),
        patch('apps.voice_commands.conversation_stt_confirmation.clear_pending', side_effect=store.clear),
    )


# Deliberate gibberish — must not match any real intent, so the confirmed
# "yes" turn falls through to the lightweight flat no-match branch (no DB,
# no real User) instead of reaching match_intent/execute_intent for real.
_UNMATCHABLE_TRANSCRIPT = 'asdkjhasd'


class SttConfirmationLanguageReplayTests(SimpleTestCase):
    def setUp(self):
        language.set_current_language(LANG_EN)
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        language.set_current_language(LANG_EN)

    def test_hindi_resolved_turn_stays_hindi_after_confirmation(self):
        request = _fake_request()

        # Turn 1: Hindi-hinted STT transcript triggers the confirmation gate.
        first = handle_transcript(request, _UNMATCHABLE_TRANSCRIPT, stt_used_language_hint=True)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_HI)
        self.assertEqual(self.store.get(555)['slots']['response_language'], LANG_HI)

        # Turn 2: user confirms "yes" — a plain typed/browser-STT answer,
        # its OWN stt_used_language_hint is False (not passed at all).
        second = handle_transcript(request, 'yes')

        # The re-entrant dispatch on the confirmed original transcript must
        # still be Hindi — not silently reset to English by the second call's
        # own default arguments (the bug this fix closes).
        self.assertEqual(second['language'], LANG_HI)
        # And it must not loop back into another confirmation round.
        self.assertNotEqual(second['message'], first['message'])

    def test_english_resolved_turn_stays_english_after_confirmation(self):
        request = _fake_request()

        # Turn 1: low language_probability (not a language hint) triggers
        # confirmation while resolving to English.
        first = handle_transcript(request, _UNMATCHABLE_TRANSCRIPT, stt_language_probability=0.1)
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_EN)
        self.assertEqual(self.store.get(555)['slots']['response_language'], LANG_EN)

        second = handle_transcript(request, 'yes')

        self.assertEqual(second['language'], LANG_EN)

    def test_confirmed_dispatch_does_not_retrigger_the_confirmation_gate(self):
        """
        Guards against reintroducing the infinite-loop regression a naive fix
        (replaying stt_used_language_hint=True itself into the re-entrant
        call) would cause — see conversation.py's response_language
        docstring. If this regressed, `second` would itself be another
        "is that right?" confirmation prompt instead of a real dispatch.
        """
        request = _fake_request()
        handle_transcript(request, _UNMATCHABLE_TRANSCRIPT, stt_used_language_hint=True)

        second = handle_transcript(request, 'yes')

        self.assertIsNone(self.store.get(555))  # pending cleared, not re-armed into another confirmation
        self.assertNotIn('is that right', second['message'].lower())
        self.assertNotIn('क्या यह सही है', second['message'])


class SttConfirmationLanguageReplayWithDetectedLanguageTests(SimpleTestCase):
    """
    Phase 4 — confirms the Phase 3.1 fix above composes correctly with the
    new, accurate stt_detected_language signal: response_language stores
    whatever get_current_language() resolves to at confirmation-start time
    (see conversation_stt_confirmation.start_stt_confirmation's own
    docstring), and that resolution already prefers stt_detected_language
    over the stt_used_language_hint approximation (see
    language.detect_language). So the replay on "yes" automatically carries
    the ACCURATE language forward too — without conversation_stt_confirmation.py
    needing any Phase-4-specific change of its own. This is exactly the
    disagreement case the old boolean signal alone could not resolve: the
    hint says Hindi, but the accurate signal says English actually won.
    """

    def setUp(self):
        language.set_current_language(LANG_EN)
        self.store = _FakePendingStore()
        for p in _patch_pending_store(self.store):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        language.set_current_language(LANG_EN)

    def test_accurate_english_signal_overrides_a_disagreeing_hint_and_survives_confirmation(self):
        request = _fake_request()

        # stt_used_language_hint=True would, on its own, resolve to Hindi —
        # but stt_detected_language='en' says the English fallback tier
        # actually won, and that's what must win end to end.
        first = handle_transcript(
            request, _UNMATCHABLE_TRANSCRIPT,
            stt_used_language_hint=True, stt_detected_language='en',
        )
        self.assertTrue(first['awaiting_input'])
        self.assertEqual(first['language'], LANG_EN)
        self.assertEqual(self.store.get(555)['slots']['response_language'], LANG_EN)

        second = handle_transcript(request, 'yes')

        self.assertEqual(second['language'], LANG_EN)

    def test_accurate_hindi_signal_survives_confirmation(self):
        request = _fake_request()

        first = handle_transcript(
            request, _UNMATCHABLE_TRANSCRIPT,
            stt_used_language_hint=True, stt_detected_language='hi',
        )
        self.assertEqual(first['language'], LANG_HI)

        second = handle_transcript(request, 'yes')

        self.assertEqual(second['language'], LANG_HI)
