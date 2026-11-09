"""
Phase 4B contract tests: the registry (23 intents, existing ones and their "clock in" phrases preserved), the matcher's
meaningful-word guard, Punch In/Out wording (English + Hindi), the Aira out-of-scope message, the `is_clarification`
field on every response builder, Hindi/Hinglish yes/no, and the TTS retry budget.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.voice_commands import (
    conversation, conversation_attendance_correction, conversation_attendance_correction_approval,
    conversation_clarification, conversation_clock_in_face, conversation_leave_approval, conversation_payroll,
    conversation_stt_confirmation, executor_attendance, matcher, sarvam_client,
)
from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.matcher import NO_MATCH_INTENT, _shares_meaningful_word, get_required_permission, match_intent
from apps.voice_commands.normalizer import normalize_transcript

ORIGINAL_INTENTS = {
    'clock_in', 'clock_out', 'check_leave_balance', 'check_leave_status', 'cancel_leave', 'check_attendance_stats',
    'check_attendance_summary', 'apply_leave', 'check_team_leave_queue', 'check_team_attendance', 'approve_leave',
    'reject_leave', 'check_my_payslip', 'acknowledge_payslip', 'raise_payslip_query', 'check_employee_payslip',
    'request_attendance_correction', 'greeting',
}
NEW_INTENTS = {
    'approve_attendance_correction', 'reject_attendance_correction', 'check_pending_payroll_cycles',
    'check_payroll_cost_summary', 'check_branch_payroll_breakdown',
}


class RegistryTests(SimpleTestCase):
    @staticmethod
    def _registry():
        return matcher._get_intent_registry(matcher._registry_path_for(matcher.DEFAULT_LANG))

    def test_registry_has_exactly_the_23_expected_intents(self):
        intents = set(self._registry())
        self.assertEqual(len(intents), 23)
        self.assertEqual(intents, ORIGINAL_INTENTS | NEW_INTENTS)

    def test_new_intents_have_the_expected_permissions(self):
        self.assertEqual(get_required_permission('approve_attendance_correction'), 'attendance.create')
        self.assertEqual(get_required_permission('reject_attendance_correction'), 'attendance.create')
        for intent in ('check_pending_payroll_cycles', 'check_payroll_cost_summary', 'check_branch_payroll_breakdown'):
            self.assertEqual(get_required_permission(intent), 'payroll.view', intent)

    def test_clock_in_and_out_keep_both_clock_and_punch_phrases(self):
        config = self._registry()
        for phrase in ('clock in', 'clock me in', 'punch in'):
            self.assertIn(phrase, config['clock_in']['phrases'])
        for phrase in ('clock out', 'punch out'):
            self.assertIn(phrase, config['clock_out']['phrases'])

    def test_clock_phrases_still_match_their_intents(self):
        for phrase, intent in (('clock in', 'clock_in'), ('clock me in', 'clock_in'), ('punch in', 'clock_in'),
                               ('clock out', 'clock_out'), ('punch out', 'clock_out')):
            with self.subTest(phrase):
                self.assertEqual(match_intent(normalize_transcript(phrase)).intent, intent)

    def test_new_intents_match_their_own_phrases(self):
        for phrase, intent in (
            ('approve attendance correction for ravindra', 'approve_attendance_correction'),
            ('reject this correction request', 'reject_attendance_correction'),
            ('what payroll cycles are pending', 'check_pending_payroll_cycles'),
            ('what is our payroll cost', 'check_payroll_cost_summary'),
            ('show branch payroll breakdown', 'check_branch_payroll_breakdown'),
        ):
            with self.subTest(phrase):
                result = match_intent(normalize_transcript(phrase))
                self.assertEqual(result.intent, intent)


class MatcherGuardTests(SimpleTestCase):
    def test_filler_words_alone_do_not_count_as_shared_meaning(self):
        self.assertFalse(_shares_meaningful_word('what is the weather today', 'what is my net pay'))

    def test_a_shared_real_word_counts(self):
        self.assertTrue(_shares_meaningful_word('show me my payslip please', 'check my payslip'))

    def test_a_typo_of_a_real_word_counts(self):
        self.assertTrue(_shares_meaningful_word('show my payslp', 'check my payslip'))

    def test_concatenated_registry_phrases_count(self):
        self.assertTrue(_shares_meaningful_word('leave balance', 'leavebalance'))

    def test_empty_inputs_never_match(self):
        self.assertFalse(_shares_meaningful_word('', 'check my payslip'))
        self.assertFalse(_shares_meaningful_word('the is a', 'check my payslip'))

    def test_out_of_scope_question_gets_no_did_you_mean_candidate(self):
        result = match_intent(normalize_transcript('what is the weather today?'))
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertIsNone(result.candidate_intent)


class WordingTests(SimpleTestCase):
    def test_punch_success_messages_say_punched_in_and_out_in_english(self):
        self.assertEqual(executor_attendance._CLOCK_IN_SUCCESS_MESSAGE['en'], 'Punched in successfully.')
        self.assertEqual(executor_attendance._CLOCK_OUT_SUCCESS_MESSAGE['en'], 'Punched out successfully.')

    def test_hindi_equivalents_exist_and_use_punch_wording(self):
        self.assertIn('पंच-इन', executor_attendance._CLOCK_IN_SUCCESS_MESSAGE['hi'])
        self.assertIn('पंच-आउट', executor_attendance._CLOCK_OUT_SUCCESS_MESSAGE['hi'])

    def test_no_match_message_is_for_aira_not_royal_hrms(self):
        for language_code in ('en', 'hi'):
            message = conversation._NO_MATCH_MESSAGE[language_code]
            self.assertNotIn('Royal', message)
            self.assertIn('Aira', message)

    def test_no_royal_hrms_wording_in_the_voice_backend_strings(self):
        import pathlib
        root = pathlib.Path(conversation.__file__).parent
        offenders = [
            path.name for path in root.glob('*.py')
            if 'Royal' in path.read_text(encoding='utf8') and path.name != 'test_sarvam_client.py'
        ]
        self.assertEqual(offenders, [])


class ResponseContractTests(SimpleTestCase):
    def test_every_response_builder_carries_is_clarification(self):
        builders = (
            conversation._payload, conversation_attendance_correction._payload,
            conversation_attendance_correction_approval._payload, conversation_clarification._payload,
            conversation_clock_in_face._payload, conversation_leave_approval._payload, conversation_payroll._payload,
            conversation_stt_confirmation._payload,
        )
        for builder in builders:
            with self.subTest(builder.__module__):
                payload = builder('check_leave_balance', None, None, 'm')
                self.assertIn('is_clarification', payload)
                self.assertFalse(payload['is_clarification'])

    def test_only_the_did_you_mean_question_sets_it(self):
        payload = conversation_clarification._payload('check_leave_balance', 80.0, None, 'q?', is_clarification=True)
        self.assertTrue(payload['is_clarification'])


class HindiYesNoTests(SimpleTestCase):
    def test_hindi_and_hinglish_answers(self):
        for answer in ('haan', 'haan ji', 'हाँ', 'हां', 'ठीक है', 'bilkul', 'yes', 'हाँ।'):
            with self.subTest(answer):
                self.assertIs(parse_yes_no(answer), True)
        for answer in ('nahi', 'nahin', 'नहीं', 'नहीं।', 'no', 'cancel'):
            with self.subTest(answer):
                self.assertIs(parse_yes_no(answer), False)
        self.assertIsNone(parse_yes_no('maybe later'))


class TtsRetryBudgetTests(SimpleTestCase):
    def test_timeout_and_attempts_are_the_approved_values(self):
        self.assertEqual(sarvam_client._TTS_TIMEOUT_SECONDS, 8)
        self.assertEqual(sarvam_client._TTS_MAX_ATTEMPTS, 2)
        self.assertEqual(len(sarvam_client._TTS_RETRY_BACKOFF_SECONDS), sarvam_client._TTS_MAX_ATTEMPTS - 1)

    def test_aira_file_content_validation_is_still_wired_into_transcription(self):
        import apps.voice_commands.views_transcribe as views_transcribe
        self.assertTrue(callable(views_transcribe._validate_file_content))
