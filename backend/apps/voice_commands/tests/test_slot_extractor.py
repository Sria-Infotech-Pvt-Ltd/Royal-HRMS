from datetime import date, timedelta

from django.test import SimpleTestCase

from apps.voice_commands.slot_extractor import (
    extract_apply_leave_slots,
    extract_date_range,
    extract_leave_type,
    extract_reason,
    next_missing_slot,
    parse_slot_answer,
    question_for_slot,
    strip_leave_slot_phrases,
)

_TODAY = date(2026, 1, 1)


class ExtractLeaveTypeTests(SimpleTestCase):
    def test_matches_sick(self):
        self.assertEqual(extract_leave_type('apply for sick leave'), 'sick')

    def test_matches_casual(self):
        self.assertEqual(extract_leave_type('i want casual leave'), 'casual')

    def test_matches_earned_synonym_annual(self):
        self.assertEqual(extract_leave_type('i need annual leave'), 'earned')

    def test_matches_sick_synonym_medical(self):
        self.assertEqual(extract_leave_type('i need medical leave'), 'sick')

    def test_matches_lwp_synonym_loss_of_pay(self):
        self.assertEqual(extract_leave_type('apply for loss of pay leave'), 'lwp')

    def test_matches_lwp_synonym_unpaid(self):
        self.assertEqual(extract_leave_type('unpaid leave please'), 'lwp')

    def test_matches_maternity(self):
        self.assertEqual(extract_leave_type('maternity leave'), 'maternity')

    def test_matches_paternity(self):
        self.assertEqual(extract_leave_type('paternity leave'), 'paternity')

    def test_no_leave_type_mentioned_returns_none(self):
        self.assertIsNone(extract_leave_type('apply for leave from july 22 to july 24'))


class ExtractDateRangeTests(SimpleTestCase):
    def test_from_to_range(self):
        start, end = extract_date_range('from july 22 to july 24', today=_TODAY)
        self.assertEqual(start, date(2026, 7, 22))
        self.assertEqual(end, date(2026, 7, 24))

    def test_full_utterance_with_from_to_range(self):
        start, end = extract_date_range('apply for sick leave from july 22 to july 24', today=_TODAY)
        self.assertEqual(start, date(2026, 7, 22))
        self.assertEqual(end, date(2026, 7, 24))

    def test_single_bare_date_sets_both_start_and_end(self):
        start, end = extract_date_range('july 22', today=_TODAY)
        self.assertEqual(start, date(2026, 7, 22))
        self.assertEqual(end, date(2026, 7, 22))

    def test_relative_day_word_inside_range_phrase_still_resolves(self):
        # "from X to Y" captures a targeted date fragment even when X/Y are
        # relative words, so these are still honored.
        start, end = extract_date_range('from tomorrow to day after tomorrow', today=_TODAY)
        self.assertEqual(start, date(2026, 1, 2))
        self.assertEqual(end, date(2026, 1, 3))

    def test_bare_relative_day_word_no_longer_resolves_in_fallback_branch(self):
        # Regression: the no-range fallback treats `text` as a potentially
        # arbitrary sentence (see extract_apply_leave_slots), so a bare
        # "today"/"tomorrow" is no longer silently resolved here — only in
        # parse_slot_answer(), where the whole answer IS the date fragment.
        self.assertEqual(extract_date_range('today', today=_TODAY), (None, None))
        self.assertEqual(extract_date_range('tomorrow', today=_TODAY), (None, None))

    def test_no_date_found_returns_none_none(self):
        start, end = extract_date_range('apply for leave', today=_TODAY)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_relative_day_word_anywhere_in_a_full_sentence_is_not_a_date(self):
        # This is the exact bug: "apply for sick leave tomorrow" used to
        # silently resolve BOTH start and end to tomorrow's date, from a
        # substring match against the whole sentence.
        start, end = extract_date_range('apply for sick leave tomorrow', today=_TODAY)
        self.assertIsNone(start)
        self.assertIsNone(end)


class ExtractReasonTests(SimpleTestCase):
    def test_because_marker(self):
        self.assertEqual(extract_reason('apply for leave because i am feeling unwell'), 'i am feeling unwell')

    def test_due_to_marker(self):
        self.assertEqual(extract_reason('apply for leave due to a family function'), 'a family function')

    def test_reason_is_marker(self):
        self.assertEqual(extract_reason('apply for leave, reason is a family emergency'), 'a family emergency')

    def test_no_marker_returns_none(self):
        self.assertIsNone(extract_reason('apply for sick leave from july 22 to july 24'))


class ExtractApplyLeaveSlotsTests(SimpleTestCase):
    def test_single_utterance_captures_leave_type_and_dates(self):
        slots = extract_apply_leave_slots('apply for sick leave from july 22 to july 24')
        self.assertEqual(slots.get('leave_type'), 'sick')
        # today defaults to real date.today() here, only month/day are asserted.
        self.assertEqual(slots['start_date'].month, 7)
        self.assertEqual(slots['start_date'].day, 22)
        self.assertEqual(slots['end_date'].month, 7)
        self.assertEqual(slots['end_date'].day, 24)
        self.assertNotIn('reason', slots)

    def test_single_utterance_captures_all_four_slots(self):
        slots = extract_apply_leave_slots(
            'apply for sick leave from july 22 to july 24 because i am unwell'
        )
        self.assertEqual(slots.get('leave_type'), 'sick')
        self.assertEqual(slots.get('reason'), 'i am unwell')
        self.assertIn('start_date', slots)
        self.assertIn('end_date', slots)

    def test_bare_apply_for_leave_captures_nothing(self):
        slots = extract_apply_leave_slots('apply for leave')
        self.assertEqual(slots, {})

    def test_relative_day_word_in_first_utterance_does_not_fill_dates(self):
        # Regression for the bug where "apply for sick leave tomorrow"
        # silently set both start_date and end_date from the word "tomorrow"
        # appearing anywhere in the sentence, skipping the date questions
        # entirely.
        slots = extract_apply_leave_slots('apply for sick leave tomorrow')
        self.assertEqual(slots, {'leave_type': 'sick'})
        self.assertNotIn('start_date', slots)
        self.assertNotIn('end_date', slots)


class NextMissingSlotTests(SimpleTestCase):
    def test_returns_leave_type_first(self):
        self.assertEqual(next_missing_slot({}), 'leave_type')

    def test_returns_start_date_when_leave_type_present(self):
        self.assertEqual(next_missing_slot({'leave_type': 'sick'}), 'start_date')

    def test_returns_end_date_when_leave_type_and_start_present(self):
        self.assertEqual(
            next_missing_slot({'leave_type': 'sick', 'start_date': _TODAY}), 'end_date',
        )

    def test_returns_reason_when_only_reason_missing(self):
        self.assertEqual(
            next_missing_slot({'leave_type': 'sick', 'start_date': _TODAY, 'end_date': _TODAY}),
            'reason',
        )

    def test_returns_none_when_all_present(self):
        self.assertIsNone(next_missing_slot({
            'leave_type': 'sick', 'start_date': _TODAY, 'end_date': _TODAY, 'reason': 'not feeling well today',
        }))


class QuestionForSlotTests(SimpleTestCase):
    def test_leave_type_question_lists_choices(self):
        question = question_for_slot('leave_type')
        for label in ('Casual', 'Earned', 'Sick', 'Maternity', 'Paternity'):
            self.assertIn(label, question)

    def test_start_date_question(self):
        self.assertIn('start', question_for_slot('start_date').lower())

    def test_end_date_question(self):
        self.assertIn('end', question_for_slot('end_date').lower())

    def test_reason_question(self):
        self.assertIn('reason', question_for_slot('reason').lower())


class ParseSlotAnswerTests(SimpleTestCase):
    def test_valid_leave_type_answer(self):
        value, error_message = parse_slot_answer('leave_type', 'sick')
        self.assertEqual(value, 'sick')
        self.assertIsNone(error_message)

    def test_invalid_leave_type_answer_asks_again_and_lists_choices(self):
        value, error_message = parse_slot_answer('leave_type', 'banana')
        self.assertIsNone(value)
        self.assertIsNotNone(error_message)
        self.assertIn('Sick', error_message)

    def test_valid_start_date_answer(self):
        value, error_message = parse_slot_answer('start_date', 'july 22 2026')
        self.assertEqual(value, date(2026, 7, 22))
        self.assertIsNone(error_message)

    def test_relative_day_word_answer_still_resolves(self):
        # parse_slot_answer is only ever called for the slot the system just
        # asked about — the whole answer IS the date fragment here, so
        # relative-day words remain valid (unlike extract_date_range's
        # whole-sentence fallback, which no longer honors them).
        value, error_message = parse_slot_answer('start_date', 'tomorrow')
        self.assertEqual(value, date.today() + timedelta(days=1))
        self.assertIsNone(error_message)

    def test_invalid_date_answer_asks_again(self):
        value, error_message = parse_slot_answer('start_date', 'asdkjhasd')
        self.assertIsNone(value)
        self.assertIsNotNone(error_message)

    def test_valid_reason_answer(self):
        value, error_message = parse_slot_answer('reason', 'family function out of town')
        self.assertEqual(value, 'family function out of town')
        self.assertIsNone(error_message)

    def test_too_short_reason_answer_asks_again(self):
        value, error_message = parse_slot_answer('reason', 'sick')
        self.assertIsNone(value)
        self.assertIsNotNone(error_message)


class StripLeaveSlotPhrasesTests(SimpleTestCase):
    def test_strips_date_range_and_leave_type_and_reason(self):
        stripped = strip_leave_slot_phrases(
            'apply for sick leave from july 22 to july 24 because i am unwell'
        )
        self.assertEqual(stripped, 'apply for leave')

    def test_bare_phrase_unchanged(self):
        self.assertEqual(strip_leave_slot_phrases('apply for leave'), 'apply for leave')
