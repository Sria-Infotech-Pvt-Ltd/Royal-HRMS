"""
Display-only GPS accuracy indicators (apps.attendance.location_accuracy) and the
HR attendance detail fields built from them. Stored labels/accuracy are never
rewritten.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.location_accuracy import (
    accuracy_level, csv_accuracy_metres, display_location, format_accuracy, parse_accuracy,
)
from apps.attendance.models import AttendancePunch
from apps.attendance.services_attendance import AttendanceProcessorService
from config.test_runner import TEST_COMPANY_CODE

ADDRESS = 'Surat, Gujarat, India, 395009'
STREET = 'Palanpur Road, Surat, Gujarat, India, 395009'
OFFICE = 'Office – London Branch'


class LocationAccuracyHelperTests(SimpleTestCase):
    def test_precise_fix_leaves_address_unchanged(self):
        for value in (0, 8.2, 17, 100):
            with self.subTest(value=value):
                self.assertEqual(accuracy_level(value), 'precise')
                self.assertEqual(display_location(STREET, value), STREET)
        self.assertEqual(format_accuracy(16.84), '±17 m')

    def test_moderate_accuracy_is_marked_approximate_in_metres(self):
        self.assertEqual(accuracy_level(350), 'approximate')
        self.assertEqual(display_location(ADDRESS, 350), f'Location approximate (±350 m): {ADDRESS}')
        self.assertEqual(format_accuracy(381), '±390 m')    # rounds up, never understates
        self.assertEqual(format_accuracy(102), '±110 m')
        self.assertEqual(format_accuracy(1000), '±1000 m')

    def test_poor_accuracy_is_marked_approximate_in_km(self):
        self.assertEqual(accuracy_level(20000), 'very_approximate')
        self.assertEqual(display_location(ADDRESS, 20000), f'Approximate location (±20 km): {ADDRESS}')
        self.assertEqual(format_accuracy(1500), '±1.5 km')
        self.assertEqual(format_accuracy(50000), '±50 km')
        self.assertEqual(format_accuracy(Decimal('20000.00')), '±20 km')

    def test_unusually_large_values_stay_readable(self):
        self.assertEqual(format_accuracy(1_000_000_000), '±1,000,000 km')

    def test_missing_or_invalid_accuracy_is_unknown_not_precise(self):
        for value in (None, '', 'abc', -5, float('nan'), float('inf'), True):
            with self.subTest(value=value):
                self.assertIsNone(parse_accuracy(value))
                self.assertIsNone(accuracy_level(value))
                self.assertIsNone(format_accuracy(value))
                self.assertEqual(csv_accuracy_metres(value), '')
                self.assertEqual(display_location(ADDRESS, value), ADDRESS)

    def test_office_label_is_never_prefixed(self):
        self.assertEqual(display_location(OFFICE, 50000), OFFICE)

    def test_blank_text_stays_blank(self):
        self.assertEqual(display_location('', 20000), '')
        self.assertEqual(display_location(None, 20000), '')

    def test_csv_accuracy_is_whole_metres(self):
        self.assertEqual(csv_accuracy_metres(Decimal('16.84')), '17')
        self.assertEqual(csv_accuracy_metres(20000), '20000')


class AttendanceDetailAccuracyAPITests(TestCase):
    IST = ZoneInfo('Asia/Kolkata')
    DAY = datetime.date(2026, 10, 7)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        make_user('acc.hr@test.com', role=make_role('acc_hr', permission_codenames=['attendance.view']),
                  employee_id='EMPACCHR', full_name='Acc HR')
        self.employee = make_user('acc.emp@test.com', role=make_role('acc_staff'), employee_id='EMPACC01', full_name='Acc Emp')
        resp = self.client.post(
            reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': 'acc.hr@test.com', 'password': 'TestPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

    def _at(self, hh):
        return datetime.datetime(self.DAY.year, self.DAY.month, self.DAY.day, hh, 0, tzinfo=self.IST)

    def _detail(self, in_kw, out_kw):
        AttendancePunch.objects.create(employee=self.employee, punch_type=AttendancePunch.PUNCH_IN,
                                       punched_at=self._at(9), latitude=21.19, longitude=72.79, **in_kw)
        AttendancePunch.objects.create(employee=self.employee, punch_type=AttendancePunch.PUNCH_OUT,
                                       punched_at=self._at(18), latitude=21.20, longitude=72.80, **out_kw)
        record = AttendanceProcessorService.process_day(self.employee, self.DAY)
        resp = self.client.get(f"{reverse('hr-attendance-detail', kwargs={'pk': record.id})}?date={self.DAY.isoformat()}")
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['data']

    def test_clock_in_and_out_get_their_own_accuracy(self):
        d = self._detail(
            {'location_label': STREET, 'accuracy': Decimal('16.84')},
            {'location_label': ADDRESS, 'accuracy': Decimal('20000.00')},
        )
        self.assertEqual((d['clock_in_accuracy_text'], d['clock_in_accuracy_level']), ('±17 m', 'precise'))
        self.assertEqual(d['clock_in_location_display'], STREET)
        self.assertEqual((d['clock_out_accuracy_text'], d['clock_out_accuracy_level']), ('±20 km', 'very_approximate'))
        self.assertEqual(d['clock_out_location_display'], f'Approximate location (±20 km): {ADDRESS}')
        # Raw stored values are untouched.
        self.assertEqual(d['clock_out_location_label'], ADDRESS)
        self.assertAlmostEqual(d['clock_out_accuracy_m'], 20000.0)

    def test_null_accuracy_is_unknown(self):
        d = self._detail({'location_label': ADDRESS, 'accuracy': None}, {'location_label': '', 'accuracy': None})
        self.assertIsNone(d['clock_in_accuracy_m'])
        self.assertIsNone(d['clock_in_accuracy_level'])
        self.assertIsNone(d['clock_in_accuracy_text'])
        self.assertEqual(d['clock_in_location_display'], ADDRESS)
        self.assertIsNone(d['clock_out_location_display'])  # no label yet → nothing invented

    def test_office_label_not_marked_approximate(self):
        d = self._detail({'location_label': OFFICE, 'accuracy': Decimal('5000')}, {'location_label': OFFICE, 'accuracy': None})
        self.assertEqual(d['clock_in_location_display'], OFFICE)
        self.assertTrue(d['clock_in_location_is_office'])

    def test_punch_and_record_unchanged_by_accuracy(self):
        self._detail({'location_label': ADDRESS, 'accuracy': Decimal('50000')}, {'location_label': ADDRESS, 'accuracy': Decimal('5')})
        punch = AttendancePunch.objects.get(employee=self.employee, punch_type=AttendancePunch.PUNCH_IN)
        self.assertEqual((punch.location_label, punch.accuracy), (ADDRESS, Decimal('50000.00')))
