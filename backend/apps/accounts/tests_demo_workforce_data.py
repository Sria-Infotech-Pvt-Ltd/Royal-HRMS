"""Checks on the fixed data behind `seed_demo_workforce` (no database needed)."""
from datetime import date

from django.test import SimpleTestCase

from apps.accounts import demo_workforce_data as data
from apps.accounts.demo_workforce_attendance import weekly_off_weekdays


class DemoWorkforceDataTests(SimpleTestCase):
    def test_roster_emails_are_unique_and_on_the_reserved_domain(self):
        emails = [data.email_for(first, last) for first, last, *_rest in data.ROSTER]
        self.assertEqual(len(emails), len(set(emails)))
        self.assertTrue(all(email.endswith(data.EMAIL_SUFFIX) for email in emails))

    def test_every_person_has_a_known_office_and_a_gender(self):
        for _first, _last, gender, city, *_rest in data.ROSTER:
            self.assertIn(city, data.LOCATIONS)
            self.assertIn(gender, ('male', 'female'))

    def test_joining_dates_are_real_history_not_seeder_placeholders(self):
        # seed_demo_employee_details treats joining dates from 2026-09-01 on as placeholders and rewrites them.
        self.assertTrue(all(row[5] < date(2026, 9, 1) for row in data.ROSTER))

    def test_each_remote_office_has_a_team_lead(self):
        self.assertEqual(set(data.team_leads()), {'Bengaluru', 'Pune', 'Chennai'})

    def test_payroll_periods_are_ordered_and_do_not_overlap(self):
        for start, end, pay_date in data.PERIODS:
            self.assertLess(start, end)
            self.assertGreater(pay_date, end)
        for (_s1, end1, _p1), (start2, _e2, _p2) in zip(data.PERIODS, data.PERIODS[1:]):
            self.assertLess(end1, start2)

    def test_weekly_off_weekdays_reads_the_policy(self):
        class Policy:
            monday = tuesday = wednesday = thursday = friday = 'working'
            saturday = sunday = 'off'
        self.assertEqual(weekly_off_weekdays(Policy), {5, 6})
