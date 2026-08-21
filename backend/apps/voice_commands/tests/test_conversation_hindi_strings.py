"""
Structural parity + functional selection for every conversation-flow
scaffolding string added in Phase 3.1 (Gap 1) — clarification "did you
mean?" prompts, apply_leave/attendance-correction slot-filling questions,
STT-confirmation prompts, and leave-approval/payroll/clock-in-face
conversational turns. Mirrors test_executor_hindi_strings.py/
test_executor_hindi_selection.py's own two-file split for executor_*.py's
Phase 3 strings exactly, applied to this phase's modules instead:
  - ConversationHindiStringStructuralTests: introspects every module-level
    `{'en': ..., 'hi': ...}` dict (and dicts-of-those) across the modules
    touched this phase, so a string added later without a Hindi pair is
    caught automatically.
  - NonDictLocalHindiLookupTests: the plain code -> Hindi-only lookup tables
    that don't fit the {'en','hi'} pair shape (leave-type/reason/action
    labels pre-selected before .format() ever runs).
  - Functional*Tests: one representative call per module, proving
    apps.voice_commands.language.set_current_language() actually changes
    what the FUNCTION returns, not just that the underlying dicts are
    well-formed.
"""
from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceCorrection
from apps.hrms.models import LEAVE_TYPE_CHOICES
from apps.voice_commands import (
    conversation,
    conversation_clarification,
    conversation_clock_in_face,
    conversation_leave_approval,
    conversation_payroll,
    conversation_stt_confirmation,
    correction_slot_extractor,
    language,
    slot_extractor,
)

_DEVANAGARI_RE = re.compile(r'[ऀ-ॿ]')
_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

_MODULES = [
    conversation,
    conversation_clarification,
    conversation_stt_confirmation,
    conversation_leave_approval,
    conversation_payroll,
    conversation_clock_in_face,
    slot_extractor,
    correction_slot_extractor,
]


def _is_bilingual_pair(value) -> bool:
    return isinstance(value, dict) and isinstance(value.get('en'), str) and isinstance(value.get('hi'), str)


def _bilingual_pairs_in(module) -> list:
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


class ConversationHindiStringStructuralTests(SimpleTestCase):
    def test_every_bilingual_pair_across_all_conversation_modules_is_structurally_sound(self):
        all_pairs = []
        for module in _MODULES:
            all_pairs.extend(_bilingual_pairs_in(module))

        # Sanity floor — fails loudly if the introspection above ever stops
        # finding anything (e.g. a refactor that renames the dict shape),
        # rather than this test silently passing on zero real assertions.
        self.assertGreaterEqual(
            len(all_pairs), 25,
            'Expected at least 25 bilingual message pairs across the Phase 3.1 conversation '
            f'modules — found {len(all_pairs)}. Did a refactor change the {{"en", "hi"}} dict shape?',
        )

        for qualified_name, en, hi in all_pairs:
            with self.subTest(qualified_name):
                self.assertTrue(hi.strip(), f'{qualified_name}: Hindi text is empty/blank.')
                self.assertTrue(
                    _DEVANAGARI_RE.search(hi),
                    f'{qualified_name}: Hindi text has no Devanagari characters: {hi!r}',
                )
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
    Plain code -> Hindi-only lookup tables (pre-selected through text() at
    the call site, alongside the matching English word, before .format()
    ever runs — see each dict's own comment) — checked directly, same
    reasoning test_executor_hindi_strings.py's own NonDictLocalHindiLookupTests
    documents for executor_approval._ACTION_LABELS_HI.
    """

    def test_leave_approval_action_labels_hi_covers_both_actions_with_real_devanagari(self):
        labels = conversation_leave_approval._ACTION_LABELS_HI
        self.assertEqual(set(labels.keys()), {'approve', 'reject'})
        for action, hi in labels.items():
            with self.subTest(action):
                self.assertTrue(hi.strip())
                self.assertTrue(_DEVANAGARI_RE.search(hi))

    def test_leave_type_labels_hi_covers_every_registered_leave_type_with_real_devanagari(self):
        labels = slot_extractor._LEAVE_TYPE_LABELS_HI
        self.assertEqual(set(labels.keys()), {key for key, _ in LEAVE_TYPE_CHOICES})
        for code, hi in labels.items():
            with self.subTest(code):
                self.assertTrue(hi.strip())
                self.assertTrue(_DEVANAGARI_RE.search(hi))

    def test_correction_reason_labels_hi_covers_every_registered_reason_with_real_devanagari(self):
        labels = correction_slot_extractor._REASON_LABELS_HI
        self.assertEqual(set(labels.keys()), {key for key, _ in AttendanceCorrection.REASON_CHOICES})
        for code, hi in labels.items():
            with self.subTest(code):
                self.assertTrue(hi.strip())
                self.assertTrue(_DEVANAGARI_RE.search(hi))


class _LanguageIsolatedTestCase(SimpleTestCase):
    """Every test in this file starts from English — a Hindi value left set
    by one test (or by an earlier file in the same process) must never leak
    into the next. Mirrors test_executor_hindi_selection.py's own
    _LanguageIsolatedTestCase."""

    def setUp(self):
        super().setUp()
        language.set_current_language(language.LANG_EN)

    def tearDown(self):
        language.set_current_language(language.LANG_EN)
        super().tearDown()


def _fake_request(user_id=901):
    request = MagicMock()
    request.META = {}
    request.user.id = user_id
    request.user.pk = user_id
    return request


class ClarificationFunctionalTests(_LanguageIsolatedTestCase):
    @patch('apps.voice_commands.conversation_clarification.set_pending')
    def test_did_you_mean_question_is_hindi_when_set(self, _mock_set_pending):
        language.set_current_language(language.LANG_HI)
        result = conversation_clarification.start_clarification(
            _fake_request(), 'clock_in', 'clock me in', 70.0, 'clock me in', None, 'en',
        )
        self.assertIn('क्या आपका मतलब था', result['message'])

    @patch('apps.voice_commands.conversation_clarification.clear_pending')
    def test_declined_message_is_hindi_when_set(self, _mock_clear_pending):
        language.set_current_language(language.LANG_HI)
        pending = {'intent': 'clock_in', 'slots': {'matched_phrase': 'clock me in', 'source': 'rule_engine'}}
        result = conversation_clarification.continue_clarification(_fake_request(), pending, 'no', MagicMock())
        self.assertIn('ठीक है', result['message'])


class SttConfirmationFunctionalTests(_LanguageIsolatedTestCase):
    @patch('apps.voice_commands.conversation_stt_confirmation.set_pending')
    @patch('apps.voice_commands.conversation_stt_confirmation.log_stt_confirmation_started')
    def test_confirm_transcript_question_is_hindi_when_set(self, _mock_log, _mock_set_pending):
        language.set_current_language(language.LANG_HI)
        result = conversation_stt_confirmation.start_stt_confirmation(_fake_request(), 'clock me in', 'en')
        self.assertIn('मुझे लगा आपने कहा', result['message'])

    @patch('apps.voice_commands.conversation_stt_confirmation.clear_pending')
    @patch('apps.voice_commands.conversation_stt_confirmation.log_clarification_outcome')
    def test_try_again_message_is_hindi_when_set(self, _mock_log, _mock_clear_pending):
        language.set_current_language(language.LANG_HI)
        pending = {'intent': 'no_match', 'slots': {'original_transcript': 'clock me in', 'lang': 'en'}}
        result = conversation_stt_confirmation.continue_stt_confirmation(_fake_request(), pending, 'no', MagicMock())
        self.assertIn('ठीक है', result['message'])


class LeaveApprovalFunctionalTests(_LanguageIsolatedTestCase):
    @patch('apps.voice_commands.conversation_leave_approval.set_pending')
    def test_confirm_action_question_is_hindi_when_set(self, _mock_set_pending):
        language.set_current_language(language.LANG_HI)
        pending = {'intent': 'approve_leave', 'slots': {'request_id': 'r1'}}
        result = conversation_leave_approval._continue_leave_approval_confirmation(
            _fake_request(), 'approve_leave', pending, 'maybe',
        )
        self.assertIn('स्वीकृत', result['message'])

    @patch('apps.voice_commands.conversation_leave_approval.clear_pending')
    def test_not_actioned_message_is_hindi_when_set(self, _mock_clear_pending):
        language.set_current_language(language.LANG_HI)
        pending = {'intent': 'reject_leave', 'slots': {'request_id': 'r1'}}
        result = conversation_leave_approval._continue_leave_approval_confirmation(
            _fake_request(), 'reject_leave', pending, 'no',
        )
        self.assertIn('अस्वीकृत', result['message'])
        self.assertIn('नहीं किया गया है', result['message'])


class PayrollFunctionalTests(_LanguageIsolatedTestCase):
    @patch('apps.voice_commands.conversation_payroll.set_pending')
    def test_query_question_is_hindi_when_set(self, _mock_set_pending):
        language.set_current_language(language.LANG_HI)
        result = conversation_payroll.start_raise_payslip_query(_fake_request(), 'raise a query', 70.0)
        self.assertIn('पेस्लिप', result['message'])

    @patch('apps.voice_commands.conversation_payroll.set_pending')
    def test_short_answer_reask_is_hindi_when_set(self, _mock_set_pending):
        language.set_current_language(language.LANG_HI)
        pending = {'intent': 'raise_payslip_query', 'slots': {}}
        result = conversation_payroll.continue_raise_payslip_query(_fake_request(), pending, 'no')
        self.assertIn('क्या आप', result['message'])


class ClockInFaceFunctionalTests(_LanguageIsolatedTestCase):
    @patch('apps.voice_commands.conversation_clock_in_face.FaceRegistrationRequest')
    @patch('apps.voice_commands.conversation_clock_in_face.is_face_verification_mandatory', return_value=True)
    def test_no_registration_message_is_hindi_when_set(self, _mock_mandatory, mock_model):
        mock_model.objects.filter.return_value.exists.return_value = False
        language.set_current_language(language.LANG_HI)

        result = conversation_clock_in_face.start_voice_clock_punch(
            _fake_request(), 'clock_in', 'office', 90.0, None, None,
        )

        self.assertIn('फेस आईडी', result['message'])


class SlotExtractorFunctionalTests(_LanguageIsolatedTestCase):
    def test_leave_type_question_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        question = slot_extractor.question_for_slot('leave_type')
        self.assertIn('आकस्मिक छुट्टी', question)

    def test_invalid_leave_type_answer_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        _, error_message = slot_extractor.parse_slot_answer('leave_type', 'banana')
        self.assertIn('बीमारी की छुट्टी', error_message)

    def test_generic_slot_fallback_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        self.assertIn('बता सकते हैं', slot_extractor.question_for_slot('__unknown_slot__'))
        _, error_message = slot_extractor.parse_slot_answer('__unknown_slot__', 'anything')
        self.assertIn('बताएं', error_message)


class CorrectionSlotExtractorFunctionalTests(_LanguageIsolatedTestCase):
    def test_reason_question_is_hindi_when_set(self):
        language.set_current_language(language.LANG_HI)
        question = correction_slot_extractor.question_for_slot('reason')
        self.assertIn('डिवाइस खराबी', question)

    def test_future_date_answer_is_hindi_when_set(self):
        from datetime import date, timedelta

        language.set_current_language(language.LANG_HI)
        _, error_message = correction_slot_extractor.parse_slot_answer(
            'date', (date.today() + timedelta(days=5)).isoformat(),
        )
        self.assertIn('भविष्य', error_message)
