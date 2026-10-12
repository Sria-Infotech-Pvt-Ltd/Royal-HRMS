"""Tests for the demo-data helpers behind the `seed_demo_employee_details` command (pure functions, no DB)."""
from datetime import date

from django.test import SimpleTestCase

from apps.accounts import demo_profile_data as demo
from apps.accounts.demo_avatar import generate_avatar_png


class DemoProfileDataTests(SimpleTestCase):
    def test_employee_number_comes_from_the_digits_of_the_id(self):
        self.assertEqual(demo.employee_number('EMP00011'), 11)
        self.assertEqual(demo.employee_number('QA0003'), 3)
        self.assertEqual(demo.employee_number(''), 1)

    def test_details_are_deterministic(self):
        self.assertEqual(demo.personal_details(11, 'Meera Iyer'), demo.personal_details(11, 'Meera Iyer'))

    def test_gender_follows_the_first_name(self):
        self.assertEqual(demo.personal_details(1, 'Sneha Sharma')['gender'], 'female')
        self.assertEqual(demo.personal_details(2, 'Rohan Reddy')['gender'], 'male')

    def test_personal_email_and_emergency_contact_shape(self):
        details = demo.personal_details(61, 'Sneha Sharma')
        self.assertEqual(details['personal_email'], 'sneha.sharma.demo@example.com')
        self.assertEqual(details['emergency_name'], 'Demo Contact 61')
        self.assertEqual(details['current_pin_code'], demo.PIN_CODES[61 % 4])

    def test_made_up_ids_have_the_right_shape(self):
        ids = demo.statutory_and_bank(7, 'Test Person')
        self.assertRegex(ids['pan_number'], r'^[A-Z]{5}[0-9]{4}[A-Z]$')
        self.assertRegex(ids['aadhaar_number'], r'^[0-9]{12}$')
        self.assertNotEqual(demo.statutory_and_bank(8, 'Test Person')['pan_number'], ids['pan_number'])

    def test_ctc_follows_seniority_in_the_title(self):
        self.assertGreater(demo.annual_ctc_for('Head — Mobile'), demo.annual_ctc_for('Senior Mobile Specialist'))
        self.assertGreater(demo.annual_ctc_for('Mobile Associate II'), demo.annual_ctc_for('Mobile Trainee Associate'))

    def test_joining_dates_are_never_in_the_future(self):
        today = date(2026, 10, 8)
        for number in range(1, 80):
            self.assertLess(demo.joining_date(number, today), today)

    def test_lifecycle_mix_is_mostly_active(self):
        buckets = [demo.lifecycle_bucket(n) for n in range(1, 101)]
        self.assertEqual(buckets.count('active'), 80)
        self.assertEqual(buckets.count('onboarding'), 10)
        self.assertEqual(buckets.count('probation'), 10)

    def test_avatar_is_a_stable_png(self):
        first = generate_avatar_png('EMP00050', 'female')
        self.assertTrue(first.startswith(b'\x89PNG'))
        self.assertEqual(first, generate_avatar_png('EMP00050', 'female'))
        self.assertNotEqual(first, generate_avatar_png('EMP00051', 'female'))
