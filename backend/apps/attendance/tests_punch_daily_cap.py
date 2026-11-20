"""
The daily punch cap (PunchRulesPolicy.max_punch_count): "one In and one Out a day" is a Multiple-punch policy with a cap of 2,
because the cap counts every punch event (In and Out each count as one).

Geofence, face check and day processing are stubbed: these tests are about the order rule and the cap only.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.attendance.models import AttendancePunch, PunchRulesPolicy
from apps.attendance.services_attendance import PunchService

_GEO = SimpleNamespace(is_allowed=True, branch=None, calculated_distance=None, is_inside_geofence=True, wfh_request=None, rejection_message='')
_NO_FACE = SimpleNamespace(required=False, embedding_provided=False, is_match=False, distance=None, fallback=False, blocked=False)


def _policy(punch_mode: str, cap: int) -> PunchRulesPolicy:
    return PunchRulesPolicy.objects.create(
        name=f'{punch_mode}-{cap}', policy_code=f'T-{punch_mode}-{cap}', punch_mode=punch_mode, max_punch_count=cap,
        is_default=True, is_active=True,
    )


@mock.patch('apps.attendance.services_attendance._write_punch_audit')
@mock.patch('apps.attendance.services_attendance.AttendanceProcessorService.process_day')
@mock.patch('apps.attendance.services_face_matching.FaceVerificationService.verify_for_punch', return_value=_NO_FACE)
@mock.patch('apps.attendance.services_geofencing.GeofencingService.validate', return_value=_GEO)
class DailyPunchCapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        # Migration 0054 ships a default "one in, one out a day" policy; these tests build their own, one at a time.
        PunchRulesPolicy.objects.all().delete()
        cls.employee = make_user('cap_emp@test.com', employee_id='CAP001')

    def punch(self, punch_type: str):
        return PunchService.record_punch(self.employee, {'punch_type': punch_type, 'source': 'web', 'attendance_mode': 'office'})

    def test_no_policy_means_no_daily_cap(self, *_):
        for punch_type in ('IN', 'OUT', 'IN', 'OUT', 'IN', 'OUT'):
            self.punch(punch_type)
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 6)

    def test_multiple_with_cap_two_allows_exactly_one_in_and_one_out(self, *_):
        _policy(PunchRulesPolicy.PUNCH_MODE_MULTIPLE, 2)
        self.punch('IN')
        self.punch('OUT')
        with self.assertRaisesMessage(ValueError, 'maximum number of punches for today (2)'):
            self.punch('IN')
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 2)

    def test_cap_two_still_needs_the_in_before_the_out(self, *_):
        _policy(PunchRulesPolicy.PUNCH_MODE_MULTIPLE, 2)
        with self.assertRaisesMessage(ValueError, 'not currently clocked in'):
            self.punch('OUT')
        self.assertEqual(AttendancePunch.objects.filter(employee=self.employee).count(), 0)

    def test_cap_four_allows_two_pairs(self, *_):
        _policy(PunchRulesPolicy.PUNCH_MODE_MULTIPLE, 4)
        for punch_type in ('IN', 'OUT', 'IN', 'OUT'):
            self.punch(punch_type)
        with self.assertRaisesMessage(ValueError, 'maximum number of punches for today (4)'):
            self.punch('IN')

    def test_the_cap_is_per_employee(self, *_):
        _policy(PunchRulesPolicy.PUNCH_MODE_MULTIPLE, 2)
        self.punch('IN')
        self.punch('OUT')
        other = make_user('cap_other@test.com', employee_id='CAP002')
        PunchService.record_punch(other, {'punch_type': 'IN', 'source': 'web', 'attendance_mode': 'office'})
        self.assertEqual(AttendancePunch.objects.filter(employee=other).count(), 1)


class OnePunchADayDefaultTests(TestCase):
    """The shipped default (migration 0054) is one In and one Out a day, and the session tells screens when the day is done."""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.employee = make_user('one_a_day@test.com', employee_id='ONE001')

    def test_a_default_policy_is_created_when_none_existed(self):
        policy = PunchRulesPolicy.objects.get(policy_code='PR-ONE-PER-DAY')
        self.assertEqual((policy.punch_mode, policy.max_punch_count, policy.is_default, policy.is_active), ('multiple', 2, True, True))

    def test_the_cap_is_two_events(self):
        self.assertEqual(PunchService.daily_punch_cap(), 2)

    def test_the_day_is_complete_only_after_the_punch_out(self):
        from django.utils import timezone
        today = timezone.localdate()
        self.assertFalse(PunchService.is_day_complete(self.employee, today))
        AttendancePunch.objects.create(employee=self.employee, punch_type='IN', punched_at=timezone.now(), source='web', attendance_mode='office')
        self.assertFalse(PunchService.is_day_complete(self.employee, today))          # in, not out yet
        AttendancePunch.objects.create(employee=self.employee, punch_type='OUT', punched_at=timezone.now(), source='web', attendance_mode='office')
        self.assertTrue(PunchService.is_day_complete(self.employee, today))
        self.assertTrue(PunchService.get_today_session(self.employee)['is_day_complete'])

    def test_with_no_policy_the_day_is_never_complete(self):
        from django.utils import timezone
        PunchRulesPolicy.objects.all().delete()
        AttendancePunch.objects.create(employee=self.employee, punch_type='IN', punched_at=timezone.now(), source='web', attendance_mode='office')
        AttendancePunch.objects.create(employee=self.employee, punch_type='OUT', punched_at=timezone.now(), source='web', attendance_mode='office')
        self.assertIsNone(PunchService.daily_punch_cap())
        self.assertFalse(PunchService.is_day_complete(self.employee, timezone.localdate()))
