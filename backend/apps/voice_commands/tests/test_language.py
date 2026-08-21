"""
apps.voice_commands.language — the Phase 3 ambient response-language signal
(detect_language/set_current_language/get_current_language/text). See that
module's own docstring for why this is a contextvar rather than a parameter
threaded through every executor/conversation function.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.voice_commands import language


class DetectLanguageTests(SimpleTestCase):
    def test_hint_used_resolves_to_hindi(self):
        self.assertEqual(language.detect_language(True), language.LANG_HI)

    def test_no_hint_resolves_to_english(self):
        self.assertEqual(language.detect_language(False), language.LANG_EN)


class DetectLanguageWithDetectedLanguageTests(SimpleTestCase):
    """
    Phase 4 — completes Phase 3.1's Gap 2. stt_detected_language, when a
    recognized value, is preferred outright over the stt_used_language_hint
    approximation — including when the two would disagree, which is exactly
    the case that approximation couldn't resolve on its own before this.
    """

    def test_detected_language_hi_wins_even_when_hint_is_false(self):
        self.assertEqual(language.detect_language(False, 'hi'), language.LANG_HI)

    def test_detected_language_en_wins_even_when_hint_is_true(self):
        # The exact disagreement case: hint says "treat as Hindi" (both
        # Sarvam tiers set was_language_hinted=True), but the accurate
        # signal says the English fallback tier actually won.
        self.assertEqual(language.detect_language(True, 'en'), language.LANG_EN)

    def test_falls_back_to_hint_derived_approximation_when_absent(self):
        self.assertEqual(language.detect_language(True, None), language.LANG_HI)
        self.assertEqual(language.detect_language(False, None), language.LANG_EN)

    def test_unrecognized_detected_language_value_falls_back_to_hint(self):
        self.assertEqual(language.detect_language(True, 'fr'), language.LANG_HI)
        self.assertEqual(language.detect_language(False, 'fr'), language.LANG_EN)


class CurrentLanguageTests(SimpleTestCase):
    def setUp(self):
        # Every test starts from the documented default — a contextvar value
        # set by an earlier test must never leak into this one.
        language.set_current_language(language.LANG_EN)

    def tearDown(self):
        # Symmetric with setUp — this contextvar is process/thread-ambient,
        # not per-TestCase, so a test that sets it to Hindi and returns
        # without resetting would leak into whichever UNRELATED test
        # (anywhere else in the suite, including pre-existing executor tests
        # that call execute_*() directly and never go through
        # handle_transcript's own reset) happens to run next on this thread.
        language.set_current_language(language.LANG_EN)

    def test_default_is_english(self):
        # A fresh module-level ContextVar with no set() call in this test at
        # all — confirms the "never went through handle_transcript" case
        # (e.g. existing tests calling execute_intent()/execute_check_leave_
        # balance() etc. directly) resolves to English, not an error or None.
        self.assertEqual(language.get_current_language(), language.LANG_EN)

    def test_set_hindi_is_read_back(self):
        language.set_current_language(language.LANG_HI)
        self.assertEqual(language.get_current_language(), language.LANG_HI)

    def test_unrecognized_value_fails_safe_to_english(self):
        language.set_current_language('te')  # not a language this app supports
        self.assertEqual(language.get_current_language(), language.LANG_EN)

    def test_set_english_after_hindi_switches_back(self):
        language.set_current_language(language.LANG_HI)
        language.set_current_language(language.LANG_EN)
        self.assertEqual(language.get_current_language(), language.LANG_EN)


class TextTests(SimpleTestCase):
    def setUp(self):
        language.set_current_language(language.LANG_EN)

    def tearDown(self):
        # See CurrentLanguageTests.tearDown's own comment.
        language.set_current_language(language.LANG_EN)

    def test_returns_english_entry_by_default(self):
        pair = {'en': 'Hello', 'hi': 'नमस्ते'}
        self.assertEqual(language.text(pair), 'Hello')

    def test_returns_hindi_entry_when_current_language_is_hindi(self):
        pair = {'en': 'Hello', 'hi': 'नमस्ते'}
        language.set_current_language(language.LANG_HI)
        self.assertEqual(language.text(pair), 'नमस्ते')

    def test_falls_back_to_english_for_an_unrecognized_current_language(self):
        """Defensive only — set_current_language() itself never allows this,
        but text() doesn't assume that's the only caller."""
        token = language._current_language.set('fr')
        try:
            pair = {'en': 'Hello', 'hi': 'नमस्ते'}
            self.assertEqual(language.text(pair), 'Hello')
        finally:
            language._current_language.reset(token)
