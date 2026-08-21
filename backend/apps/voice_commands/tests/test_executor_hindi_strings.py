"""
Structural parity between every executor_*.py English string (Phase 3) and
its Hindi counterpart — introspects each module's own `{'en': ..., 'hi': ...}`
dicts (and dicts-of-those, e.g. a status-code -> {'en','hi'} label map)
rather than hand-listing every constant name here, so a string added later
without a Hindi pair is caught automatically instead of only by remembering
to update this file too.

Three checks per pair, matching the Phase 3 task's own testing requirement:
  1. Hindi is non-empty and contains real Devanagari script (not empty text,
     not a stray reuse of the English string).
  2. Hindi carries every {placeholder} the English version does — no missing
     interpolation.
  3. Neither side has a placeholder the other doesn't — no extra/renamed one
     that would raise a KeyError/leave a stray literal "{...}" at .format()
     time.
"""
from __future__ import annotations

import re

from django.test import SimpleTestCase

from apps.voice_commands import (
    executor,
    executor_approval,
    executor_attendance,
    executor_greeting,
    executor_leave,
    executor_payroll,
)

_DEVANAGARI_RE = re.compile(r'[ऀ-ॿ]')
_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

_MODULES = [executor, executor_leave, executor_payroll, executor_approval, executor_attendance, executor_greeting]


def _is_bilingual_pair(value) -> bool:
    return isinstance(value, dict) and isinstance(value.get('en'), str) and isinstance(value.get('hi'), str)


def _bilingual_pairs_in(module) -> list:
    """
    Every module-level `{'en': ..., 'hi': ...}` dict, plus every value of a
    module-level dict-of-those (e.g. executor_leave._STATUS_LABELS, keyed by
    leave-status code) — collected as (qualified_name, en, hi) tuples.
    """
    pairs = []
    for name, value in vars(module).items():
        if name.startswith('__'):
            continue
        if _is_bilingual_pair(value):
            pairs.append((f'{module.__name__}.{name}', value['en'], value['hi']))
        elif isinstance(value, dict):
            for key, sub in value.items():
                if _is_bilingual_pair(sub):
                    pairs.append((f'{module.__name__}.{name}[{key!r}]', sub['en'], sub['hi']))
    return pairs


class ExecutorHindiStringStructuralTests(SimpleTestCase):
    def test_every_bilingual_pair_across_all_executors_is_structurally_sound(self):
        all_pairs = []
        for module in _MODULES:
            all_pairs.extend(_bilingual_pairs_in(module))

        # Sanity floor — fails loudly if the introspection above ever stops
        # finding anything (e.g. a refactor that renames the dict shape),
        # rather than this test silently passing on zero real assertions.
        self.assertGreaterEqual(
            len(all_pairs), 30,
            'Expected at least 30 bilingual message pairs across executor_*.py '
            f'— found {len(all_pairs)}. Did a refactor change the {{"en", "hi"}} dict shape?',
        )

        for qualified_name, en, hi in all_pairs:
            with self.subTest(qualified_name):
                self.assertTrue(hi.strip(), f'{qualified_name}: Hindi text is empty/blank.')
                self.assertTrue(
                    _DEVANAGARI_RE.search(hi),
                    f'{qualified_name}: Hindi text has no Devanagari characters: {hi!r}',
                )
                # Not literally the English string re-used as a placeholder —
                # would silently defeat this whole feature.
                self.assertNotEqual(en, hi, f'{qualified_name}: Hindi text is identical to English.')

                en_placeholders = set(_PLACEHOLDER_RE.findall(en))
                hi_placeholders = set(_PLACEHOLDER_RE.findall(hi))
                self.assertEqual(
                    en_placeholders, hi_placeholders,
                    f'{qualified_name}: placeholder mismatch — '
                    f'English has {en_placeholders}, Hindi has {hi_placeholders}.',
                )


class NonDictLocalHindiLookupTests(SimpleTestCase):
    """
    Two small Hindi-only lookup tables don't fit the {'en','hi'} pair shape
    above (they're a single language's word keyed by an internal code that
    is itself never displayed) — checked directly instead:
      - executor_approval._ACTION_LABELS_HI: 'approve'/'reject' -> Hindi verb.
      - executor_greeting._TIME_OF_DAY_HI: 'morning'/'afternoon'/'evening' ->
        Hindi time-of-day word.
    """

    def test_action_labels_hi_covers_both_actions_with_real_devanagari(self):
        labels = executor_approval._ACTION_LABELS_HI
        self.assertEqual(set(labels.keys()), {'approve', 'reject'})
        for action, hi in labels.items():
            with self.subTest(action):
                self.assertTrue(hi.strip())
                self.assertTrue(_DEVANAGARI_RE.search(hi))

    def test_time_of_day_hi_covers_all_three_buckets_with_real_devanagari(self):
        labels = executor_greeting._TIME_OF_DAY_HI
        self.assertEqual(set(labels.keys()), {'morning', 'afternoon', 'evening'})
        for bucket, hi in labels.items():
            with self.subTest(bucket):
                self.assertTrue(hi.strip())
                self.assertTrue(_DEVANAGARI_RE.search(hi))
