"""Work-from-home requests cannot start in the past unless HR allows a few days back (no database needed)."""
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.attendance.serializers_settings import PunchRulesWriteSerializer
from apps.hrms.serializers import WorkFromHomeRequestCreateSerializer
from apps.hrms.services_wfh_dates import wfh_backdate_limit_days, wfh_start_refusal

TODAY = date(2026, 11, 17)
YESTERDAY, TWO_BACK, THREE_BACK, TOMORROW = date(2026, 11, 16), date(2026, 11, 15), date(2026, 11, 14), date(2026, 11, 18)


class StartDateRuleTests(SimpleTestCase):
    def test_by_default_only_today_or_later_is_allowed(self):
        self.assertIsNone(wfh_start_refusal(TODAY, TODAY, 0))
        self.assertIsNone(wfh_start_refusal(TOMORROW, TODAY, 0))
        message = wfh_start_refusal(YESTERDAY, TODAY, 0)
        self.assertIn('today or a future date', message)

    def test_a_limit_allows_that_many_days_back_and_no_more(self):
        self.assertIsNone(wfh_start_refusal(YESTERDAY, TODAY, 2))
        self.assertIsNone(wfh_start_refusal(TWO_BACK, TODAY, 2))
        message = wfh_start_refusal(THREE_BACK, TODAY, 2)
        self.assertIn('up to 2 day(s) in the past', message)
        self.assertIn('15-11-2026', message.replace('/', '-'))   # the earliest allowed date is named

    def test_a_future_start_is_always_allowed(self):
        for limit in (0, 1, 7):
            self.assertIsNone(wfh_start_refusal(TOMORROW, TODAY, limit))

    def test_a_negative_limit_means_none(self):
        self.assertIsNotNone(wfh_start_refusal(YESTERDAY, TODAY, -3))


class LimitLookupTests(SimpleTestCase):
    @staticmethod
    def limit_with(settings_row):
        with mock.patch('core.cache_service.AttendanceSettingsCacheService.get', return_value=settings_row):
            return wfh_backdate_limit_days()

    def test_no_saved_settings_means_no_backdating(self):
        self.assertEqual(self.limit_with(None), 0)

    def test_settings_saved_before_the_option_existed_mean_no_backdating(self):
        self.assertEqual(self.limit_with(SimpleNamespace(punch_rules=SimpleNamespace())), 0)

    def test_the_saved_limit_is_used(self):
        self.assertEqual(self.limit_with(SimpleNamespace(punch_rules=SimpleNamespace(wfh_max_backdated_days=3))), 3)

    def test_a_bad_stored_value_is_treated_as_none(self):
        self.assertEqual(self.limit_with(SimpleNamespace(punch_rules=SimpleNamespace(wfh_max_backdated_days=None))), 0)


class RequestSerializerTests(SimpleTestCase):
    @staticmethod
    def payload(start, end=None):
        return {'start_date': start.isoformat(), 'end_date': (end or start).isoformat(), 'reason': 'Internet repair',
                'location_label': 'Home', 'latitude': 17.4, 'longitude': 78.4}

    def validate(self, start, limit=0, end=None):
        with mock.patch('django.utils.timezone.localdate', return_value=TODAY), \
                mock.patch('apps.hrms.services_wfh_dates.wfh_backdate_limit_days', return_value=limit):
            serializer = WorkFromHomeRequestCreateSerializer(data=self.payload(start, end))
            return serializer.is_valid(), serializer.errors

    def test_a_request_for_a_past_day_is_refused_with_a_message_on_the_start_date(self):
        valid, errors = self.validate(YESTERDAY)
        self.assertFalse(valid)
        self.assertIn('start_date', errors)
        self.assertIn('Past dates are not allowed', str(errors['start_date'][0]))

    def test_a_request_starting_today_or_later_is_accepted(self):
        self.assertTrue(self.validate(TODAY)[0])
        self.assertTrue(self.validate(TOMORROW, end=date(2026, 11, 20))[0])

    def test_a_request_that_starts_in_the_past_and_runs_to_today_is_still_refused(self):
        self.assertFalse(self.validate(YESTERDAY, end=TODAY)[0])

    def test_a_saved_limit_lets_a_request_start_that_many_days_back(self):
        self.assertTrue(self.validate(YESTERDAY, limit=1)[0])
        self.assertFalse(self.validate(TWO_BACK, limit=1)[0])

    def test_the_end_date_rule_is_unchanged(self):
        valid, errors = self.validate(TOMORROW, end=TODAY)
        self.assertFalse(valid)
        self.assertIn('end_date', errors)


class SettingsFieldTests(SimpleTestCase):
    base = {'min_hours_full_day': '8.00', 'min_hours_half_day': '4.00', 'early_exit_grace_minutes': 30}

    def test_the_limit_defaults_to_zero_and_accepts_a_small_number(self):
        for extra, expected in (({}, 0), ({'wfh_max_backdated_days': 2}, 2), ({'wfh_max_backdated_days': 31}, 31)):
            serializer = PunchRulesWriteSerializer(data={**self.base, **extra})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data['wfh_max_backdated_days'], expected)

    def test_a_negative_or_huge_limit_is_refused(self):
        for bad in (-1, 32):
            self.assertFalse(PunchRulesWriteSerializer(data={**self.base, 'wfh_max_backdated_days': bad}).is_valid(), bad)
