from datetime import date, time, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.attendance.models import AttendanceCorrection
from apps.voice_commands.correction_datetime_extractor import extract_correction_date, extract_time
from apps.voice_commands.correction_slot_extractor import (
    extract_correction_reason,
    extract_correction_slots,
    extract_punch_type,
    looks_like_correction_reason,
    next_missing_slot,
    parse_slot_answer,
    question_for_slot,
    strip_correction_slot_phrases,
)


class ExtractTimeTests(SimpleTestCase):
    def test_meridiem_time_with_minutes(self):
        self.assertEqual(extract_time('9:30 pm'), time(21, 30))

    def test_meridiem_time_without_minutes(self):
        self.assertEqual(extract_time('9 am'), time(9, 0))

    def test_24_hour_time(self):
        self.assertEqual(extract_time('17:30'), time(17, 30))

    def test_noon_and_midnight(self):
        self.assertEqual(extract_time('12 pm'), time(12, 0))
        self.assertEqual(extract_time('12 am'), time(0, 0))

    def test_idiomatic_phrasing_is_not_supported(self):
        """Documented limitation — only literal digit-based times parse."""
        self.assertIsNone(extract_time('quarter past nine'))
        self.assertIsNone(extract_time('half past nine'))

    def test_bare_number_without_a_time_marker_is_not_a_time(self):
        """Regression guard for the exact dateutil foot-gun this regex-based
        approach was written to avoid — a bare number should never be
        misread as an hour just because it's followed by unrelated words."""
        self.assertIsNone(extract_time('5 in the evening'))
        self.assertIsNone(extract_time('i forgot to punch'))


class ExtractPunchTypeTests(SimpleTestCase):
    def test_compound_phrases_in_free_text(self):
        self.assertEqual(extract_punch_type('my clock in time was wrong'), 'IN')
        self.assertEqual(extract_punch_type('i punched out early'), 'OUT')
        self.assertEqual(extract_punch_type('both my in and out were wrong'), 'BOTH')

    def test_bare_word_is_ignored_in_free_text_by_default(self):
        """Without targeted_answer, a bare 'in'/'out' must NOT match — it
        would false-positive on countless unrelated sentences."""
        self.assertIsNone(extract_punch_type('what is the weather in paris'))
        self.assertIsNone(extract_punch_type('my attendance is wrong'))

    def test_bare_word_is_accepted_as_a_targeted_answer(self):
        self.assertEqual(extract_punch_type('in', targeted_answer=True), 'IN')
        self.assertEqual(extract_punch_type('out', targeted_answer=True), 'OUT')
        self.assertEqual(extract_punch_type('both', targeted_answer=True), 'BOTH')


class ExtractCorrectionReasonTests(SimpleTestCase):
    def test_keyword_synonyms(self):
        self.assertEqual(extract_correction_reason('i forgot to punch'), AttendanceCorrection.REASON_FORGOT)
        self.assertEqual(extract_correction_reason('the biometric scanner failed'), AttendanceCorrection.REASON_BIOMETRIC)
        self.assertEqual(extract_correction_reason('i was at a client site'), AttendanceCorrection.REASON_FIELD_WORK)
        self.assertEqual(extract_correction_reason('it was some other reason'), AttendanceCorrection.REASON_OTHER)

    def test_system_down_regex_tolerates_a_verb_in_between(self):
        """A bare 'system down'/'server down' substring check misses the
        common 'the system WAS down' phrasing — this is the regex fix for
        that gap."""
        self.assertEqual(extract_correction_reason('the system was down'), AttendanceCorrection.REASON_SYSTEM)
        self.assertEqual(extract_correction_reason('the server is down'), AttendanceCorrection.REASON_SYSTEM)
        self.assertEqual(extract_correction_reason('system down'), AttendanceCorrection.REASON_SYSTEM)

    def test_unrecognized_text_returns_none(self):
        self.assertIsNone(extract_correction_reason('my favorite color is blue'))

    def test_looks_like_correction_reason_excludes_bare_other(self):
        """The timeout-detection heuristic must not fire on the word 'other'
        alone — too common in ordinary unrelated sentences."""
        self.assertFalse(looks_like_correction_reason('any other options available'))
        self.assertTrue(looks_like_correction_reason('i forgot to punch'))


class ExtractCorrectionDateTests(SimpleTestCase):
    def test_explicit_date(self):
        self.assertEqual(extract_correction_date('july 20 2026'), date(2026, 7, 20))

    def test_relative_words_not_honored_in_free_text_by_default(self):
        """Mirrors slot_extractor's own reasoning: text here can be an
        arbitrary sentence, so a bare 'today'/'yesterday' substring check
        would misfire on any sentence merely mentioning the word."""
        result = extract_correction_date('i wonder what happened yesterday at the mall')
        self.assertIsNone(result)


class NextMissingSlotTests(SimpleTestCase):
    def test_asks_date_first(self):
        self.assertEqual(next_missing_slot({}), 'date')

    def test_asks_punch_type_after_date(self):
        self.assertEqual(next_missing_slot({'date': date(2026, 7, 20)}), 'punch_type')

    def test_in_only_asks_for_correct_in_time_never_out_time(self):
        slots = {'date': date(2026, 7, 20), 'punch_type': 'IN'}
        self.assertEqual(next_missing_slot(slots), 'correct_in_time')
        slots['correct_in_time'] = time(9, 0)
        self.assertEqual(next_missing_slot(slots), 'reason')

    def test_out_only_asks_for_correct_out_time_never_in_time(self):
        slots = {'date': date(2026, 7, 20), 'punch_type': 'OUT'}
        self.assertEqual(next_missing_slot(slots), 'correct_out_time')
        slots['correct_out_time'] = time(18, 0)
        self.assertEqual(next_missing_slot(slots), 'reason')

    def test_both_asks_in_time_then_out_time_then_reason(self):
        slots = {'date': date(2026, 7, 20), 'punch_type': 'BOTH'}
        self.assertEqual(next_missing_slot(slots), 'correct_in_time')
        slots['correct_in_time'] = time(9, 0)
        self.assertEqual(next_missing_slot(slots), 'correct_out_time')
        slots['correct_out_time'] = time(18, 0)
        self.assertEqual(next_missing_slot(slots), 'reason')

    def test_all_slots_present_returns_none(self):
        slots = {
            'date': date(2026, 7, 20), 'punch_type': 'BOTH',
            'correct_in_time': time(9, 0), 'correct_out_time': time(18, 0),
            'reason': AttendanceCorrection.REASON_FORGOT,
        }
        self.assertIsNone(next_missing_slot(slots))


class ParseSlotAnswerTests(SimpleTestCase):
    def test_valid_date_answer(self):
        value, error = parse_slot_answer('date', 'july 20 2026')
        self.assertEqual(value, date(2026, 7, 20))
        self.assertIsNone(error)

    def test_yesterday_is_honored_as_a_targeted_date_answer(self):
        value, error = parse_slot_answer('date', 'yesterday')
        self.assertEqual(value, date.today() - timedelta(days=1))
        self.assertIsNone(error)

    def test_future_date_answer_is_rejected(self):
        value, error = parse_slot_answer('date', 'december 31 2099')
        self.assertIsNone(value)
        self.assertIn('future', error.lower())

    def test_unparseable_date_answer_is_rejected(self):
        value, error = parse_slot_answer('date', 'blah blah')
        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_valid_punch_type_answer(self):
        value, error = parse_slot_answer('punch_type', 'out')
        self.assertEqual(value, 'OUT')
        self.assertIsNone(error)

    def test_invalid_punch_type_answer_is_rejected(self):
        value, error = parse_slot_answer('punch_type', 'sideways')
        self.assertIsNone(value)
        self.assertIn('clock-in, clock-out, or both', error.lower())

    def test_valid_time_answer(self):
        value, error = parse_slot_answer('correct_in_time', '9:15 am')
        self.assertEqual(value, time(9, 15))
        self.assertIsNone(error)

    def test_invalid_time_answer_is_rejected(self):
        value, error = parse_slot_answer('correct_out_time', 'later today')
        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_valid_reason_answer(self):
        value, error = parse_slot_answer('reason', 'i forgot to punch')
        self.assertEqual(value, AttendanceCorrection.REASON_FORGOT)
        self.assertIsNone(error)

    def test_invalid_reason_answer_is_rejected(self):
        value, error = parse_slot_answer('reason', 'no comment')
        self.assertIsNone(value)
        self.assertIn('not a reason', error.lower())


class ExtractCorrectionSlotsTests(SimpleTestCase):
    def test_extracts_all_slots_from_one_rich_utterance(self):
        slots = extract_correction_slots(
            'correct my clock in on july 20 2026 to 9:15 am i forgot to punch',
        )
        self.assertEqual(slots, {
            'date': date(2026, 7, 20),
            'punch_type': 'IN',
            'correct_in_time': time(9, 15),
            'reason': AttendanceCorrection.REASON_FORGOT,
        })

    def test_bare_utterance_extracts_nothing(self):
        self.assertEqual(extract_correction_slots('my attendance is wrong'), {})

    def test_both_punch_type_does_not_guess_which_time_a_single_match_belongs_to(self):
        """Documented limitation — a BOTH utterance with only one time
        mentioned isn't captured at all here; the multi-turn flow asks for
        it explicitly instead of guessing in vs out."""
        slots = extract_correction_slots('both my in and out were wrong on july 20 2026, it was 9 am')
        self.assertEqual(slots.get('punch_type'), 'BOTH')
        self.assertNotIn('correct_in_time', slots)
        self.assertNotIn('correct_out_time', slots)

    @patch('apps.voice_commands.correction_slot_extractor.date')
    @patch('apps.voice_commands.correction_datetime_extractor.date')
    def test_future_date_is_not_captured_from_free_text(self, mock_datetime_date, mock_slot_date):
        # Two patch targets since the split: correction_datetime_extractor.date
        # backs extract_correction_date's own dateutil default, while
        # correction_slot_extractor.date backs extract_correction_slots' own
        # "is this date in the future" comparison — both need today() mocked
        # for this test to exercise the intended scenario rather than
        # incidentally passing off the real current date.
        for mock_date in (mock_datetime_date, mock_slot_date):
            mock_date.today.return_value = date(2026, 1, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        slots = extract_correction_slots('my clock in on december 31 2026 was wrong')
        self.assertNotIn('date', slots)


class StripCorrectionSlotPhrasesTests(SimpleTestCase):
    def test_bare_clock_in_survives_untouched(self):
        """The collision guard: 'clock in'/'clock out' are ALSO the literal
        registered phrases for the separate clock_in/clock_out intents —
        stripping the whole utterance down to nothing here would break
        those commands entirely."""
        self.assertEqual(strip_correction_slot_phrases('clock in'), 'clock in')
        self.assertEqual(strip_correction_slot_phrases('clock out'), 'clock out')
        self.assertEqual(strip_correction_slot_phrases('punch in'), 'punch in')
        self.assertEqual(strip_correction_slot_phrases('punch out'), 'punch out')

    def test_punch_type_mention_inside_a_longer_sentence_is_stripped(self):
        result = strip_correction_slot_phrases('my clock in time was wrong yesterday')
        self.assertNotIn('clock in', result)

    def test_date_and_time_spans_are_stripped(self):
        result = strip_correction_slot_phrases('correct my attendance on july 20 2026 to 9:15 am')
        self.assertNotIn('july', result)
        self.assertNotIn('2026', result)
        self.assertNotIn('9:15', result)

    def test_reason_keywords_are_stripped(self):
        result = strip_correction_slot_phrases('my attendance is wrong, i forgot to punch')
        self.assertNotIn('forgot', result)
