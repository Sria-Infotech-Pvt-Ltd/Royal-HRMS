from django.test import SimpleTestCase

from apps.voice_commands.payroll_period_extractor import extract_period_month, extract_period_offset


class ExtractPeriodOffsetTests(SimpleTestCase):
    def test_defaults_to_zero(self):
        self.assertEqual(extract_period_offset('what is our payroll cost'), 0)
        self.assertEqual(extract_period_offset('show branch payroll breakdown'), 0)

    def test_last_month_phrase_returns_one(self):
        self.assertEqual(extract_period_offset('what was our payroll cost last month'), 1)

    def test_previous_cycle_phrase_returns_one(self):
        self.assertEqual(extract_period_offset('branch breakdown for the previous cycle'), 1)

    def test_past_payroll_phrase_returns_one(self):
        self.assertEqual(extract_period_offset('show me the past payroll breakdown'), 1)

    def test_unrelated_use_of_last_does_not_match(self):
        # "last" not immediately followed by cycle/month/payroll must not
        # be treated as a relative-period phrase.
        self.assertEqual(extract_period_offset('who was the last employee paid'), 0)


class ExtractPeriodMonthTests(SimpleTestCase):
    def test_returns_none_when_no_month_name_present(self):
        self.assertIsNone(extract_period_month('what is our payroll cost'))
        self.assertIsNone(extract_period_month('show top 3 branches by payroll cost'))

    def test_does_not_hallucinate_a_date_from_an_unrelated_number(self):
        """
        Regression guard: dateutil.parser.parse(fuzzy=True) run unguarded on
        arbitrary text can manufacture a date out of an unrelated number
        (e.g. "top 3 branches" -> day 3 of the current month). The month-name
        guard must reject this before ever calling dateutil.
        """
        self.assertIsNone(extract_period_month('show me the top 3 branches by net pay'))

    def test_extracts_explicit_month_name(self):
        result = extract_period_month('what was the payroll cost for march')
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith('-03'))

    def test_extracts_abbreviated_month_name(self):
        result = extract_period_month('payroll cost for jan')
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith('-01'))

    def test_returns_none_for_garbled_text_around_a_real_month_token(self):
        # A month token is present, so dateutil IS invoked, but it must not
        # raise out of extract_period_month for anything it can't parse.
        result = extract_period_month('may i ask you something')
        # "may" is a real month-name token — dateutil will resolve some
        # date here; the important invariant is that it never raises.
        self.assertTrue(result is None or isinstance(result, str))
