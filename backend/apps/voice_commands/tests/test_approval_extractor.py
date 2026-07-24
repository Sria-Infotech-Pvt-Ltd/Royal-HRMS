from django.test import SimpleTestCase

from apps.voice_commands.approval_extractor import (
    extract_employee_name_query,
    match_employee_name,
    parse_yes_no,
    strip_employee_name_phrases,
)


class ExtractEmployeeNameQueryTests(SimpleTestCase):
    def test_for_pattern_captures_the_name(self):
        self.assertEqual(extract_employee_name_query('approve leave for sarah khan'), 'sarah khan')

    def test_possessive_pattern_captures_the_name(self):
        self.assertEqual(extract_employee_name_query("approve sarah's leave request"), 'sarah')

    def test_reject_and_deny_verbs_are_both_recognized(self):
        self.assertEqual(extract_employee_name_query('reject leave for sam'), 'sam')
        self.assertEqual(extract_employee_name_query("deny sam's leave request"), 'sam')

    def test_no_name_present_returns_none(self):
        self.assertIsNone(extract_employee_name_query('approve leave'))
        self.assertIsNone(extract_employee_name_query('approve this leave request'))

    def test_no_approval_verb_never_extracts_a_name(self):
        # "team's leave requests" contains a possessive-before-leave pattern,
        # but with no approve/reject/deny verb this must not fire — it's
        # check_team_leave_queue's own phrase, not an approval target.
        self.assertIsNone(extract_employee_name_query("show my team's leave requests"))


class StripEmployeeNamePhrasesTests(SimpleTestCase):
    def test_strips_for_name_but_keeps_the_action_phrase(self):
        self.assertEqual(strip_employee_name_phrases('approve leave for sarah khan'), 'approve leave for')

    def test_strips_possessive_name_but_keeps_leave_request(self):
        self.assertEqual(strip_employee_name_phrases("approve sarah's leave request"), 'approve leave request')

    def test_unrelated_text_is_left_untouched(self):
        self.assertEqual(strip_employee_name_phrases("show my team's leave requests"), "show my team's leave requests")

    def test_apply_leave_for_leave_is_not_mistaken_for_a_name(self):
        # No approve/reject/deny verb present -> guard blocks the strip
        # entirely, regardless of the "for leave" tail.
        self.assertEqual(strip_employee_name_phrases('apply for leave'), 'apply for leave')


class ParseYesNoTests(SimpleTestCase):
    def test_recognizes_common_yes_words(self):
        for answer in ('yes', 'yeah', 'yep', 'sure', 'correct', 'confirmed', 'go ahead'):
            with self.subTest(answer=answer):
                self.assertTrue(parse_yes_no(answer))

    def test_recognizes_common_no_words(self):
        for answer in ('no', 'nope', 'nah', "don't", 'cancel', 'negative'):
            with self.subTest(answer=answer):
                self.assertFalse(parse_yes_no(answer))

    def test_ambiguous_answer_returns_none(self):
        for answer in ('maybe', 'i am not sure', 'what', ''):
            with self.subTest(answer=answer):
                self.assertIsNone(parse_yes_no(answer))

    def test_answer_containing_both_yes_and_no_words_is_ambiguous(self):
        self.assertIsNone(parse_yes_no('no wait yes'))


class MatchEmployeeNameTests(SimpleTestCase):
    def _candidates(self):
        return [
            {'request_id': 'req-1', 'employee_name': 'Sarah Khan'},
            {'request_id': 'req-2', 'employee_name': 'Sam Cooper'},
        ]

    def test_no_query_returns_no_matches(self):
        self.assertEqual(match_employee_name(None, self._candidates()), [])
        self.assertEqual(match_employee_name('', self._candidates()), [])

    def test_no_candidates_returns_no_matches(self):
        self.assertEqual(match_employee_name('sarah', []), [])

    def test_exact_first_name_matches_only_that_candidate(self):
        matches = match_employee_name('sarah', self._candidates())
        self.assertEqual([m['request_id'] for m in matches], ['req-1'])

    def test_unrelated_name_matches_nothing(self):
        matches = match_employee_name('zzzzqqqq', self._candidates())
        self.assertEqual(matches, [])

    def test_full_name_match_is_unambiguous(self):
        matches = match_employee_name('sam cooper', self._candidates())
        self.assertEqual([m['request_id'] for m in matches], ['req-2'])
