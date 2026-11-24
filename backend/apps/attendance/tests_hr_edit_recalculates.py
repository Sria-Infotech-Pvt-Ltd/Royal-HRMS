"""HR editing punch times recalculates the day (status, hours, late flag) unless HR deliberately picks another status."""
import datetime as dt
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.attendance.tests_recalculate_attendance import cfg

DAY = dt.date(2026, 11, 18)


class HrEditRecalculatesTests(TestCase):
    def setUp(self):
        patcher = mock.patch('apps.attendance.services_attendance._get_settings', return_value=cfg(full='8', half='4', break_minutes=30, grace=15, forgive_late=True))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.employee = make_user('hr-edit-emp@test.com', full_name='Edit Emp', employee_id='HE1', branch='Hyderabad')
        self.admin = make_user('hr-edit-admin@test.com', make_role('r_hredit', permission_codenames=['attendance.view', 'attendance.create']),
                               full_name='Admin', employee_id='HEA1', onboarding_status=User.ONBOARDING_COMPLETE)
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def record(self, **fields):
        defaults = dict(employee=self.employee, date=DAY, status='late', first_punch_in=dt.time(10, 14), last_punch_out=None, is_late=True)
        defaults.update(fields)
        return AttendanceRecord.objects.create(**defaults)

    def edit(self, record, **payload):
        response = self.client.patch(reverse('hr-attendance-detail', args=[record.pk]), payload, format='json')
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        record.refresh_from_db()
        return record

    def test_adding_the_missing_punch_out_turns_a_full_day_late_into_present(self):
        record = self.record()
        record = self.edit(record, status='late', clock_in='10:14', clock_out='19:20', reason='missed punch-out')
        self.assertEqual(record.status, 'present')
        self.assertTrue(record.is_late)                       # still flagged, so the calendar shows "Late login"
        self.assertEqual(record.total_working_minutes, 516)   # 9h06 on the clock minus the 30 minute break

    def test_a_short_day_stays_late(self):
        record = self.edit(self.record(), status='late', clock_in='10:14', clock_out='17:30', reason='fix')
        self.assertEqual(record.status, 'late')

    def test_a_status_hr_picks_on_purpose_is_kept(self):
        record = self.edit(self.record(), status='half_day', clock_in='10:14', clock_out='19:20', reason='manager decision')
        self.assertEqual(record.status, 'half_day')

    def test_a_note_typed_by_hr_is_kept(self):
        record = self.edit(self.record(), status='late', clock_in='10:14', clock_out='19:20', note='Approved by manager', reason='fix')
        self.assertEqual(record.note, 'Approved by manager')


class HrEditCorrectsOnlyTheClockInTests(HrEditRecalculatesTests):
    """The day has no clock-out yet and HR corrects the clock-in: the late flag and the Present / Late status follow the new time."""

    def test_correcting_a_late_clock_in_to_an_on_time_one_clears_the_late(self):
        record = self.edit(self.record(), status='late', clock_in='09:00', reason='punched at nine, system showed late')
        self.assertEqual(record.status, 'present')
        self.assertFalse(record.is_late)

    def test_the_time_inside_the_grace_period_is_not_late(self):
        record = self.edit(self.record(), status='late', clock_in='09:15', reason='fix')
        self.assertEqual((record.status, record.is_late), ('present', False))

    def test_correcting_to_a_time_after_the_grace_period_is_late(self):
        record = self.edit(self.record(status='present', is_late=False, first_punch_in=dt.time(9, 0)), status='present', clock_in='09:16', reason='fix')
        self.assertEqual((record.status, record.is_late), ('late', True))

    def test_a_status_hr_picks_on_purpose_is_kept(self):
        record = self.edit(self.record(), status='present', clock_in='11:00', reason='manager approved the late start')
        self.assertEqual(record.status, 'present')

    def test_an_unchanged_clock_in_changes_nothing(self):
        record = self.edit(self.record(), status='late', clock_in='10:14', note='kept', reason='note only')
        self.assertEqual((record.status, record.is_late, record.note), ('late', True, 'kept'))

    def test_a_note_typed_by_hr_survives_the_recalculation(self):
        record = self.edit(self.record(), status='late', clock_in='09:00', note='Approved by manager', reason='fix')
        self.assertEqual((record.status, record.note), ('present', 'Approved by manager'))
