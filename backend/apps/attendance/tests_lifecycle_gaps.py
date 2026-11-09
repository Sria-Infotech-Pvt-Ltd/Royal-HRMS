"""
Lifecycle rules on the attendance entry points that are not the web punch: biometric/device pushes, correction
(regularization) requests, and absence alerts. A Pre-Joining, Unknown (no joining date) or Terminated employee may not punch
by any route, and may not trigger absence alerts; an Active employee can and does.
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services_lifecycle_status as lifecycle
from apps.accounts.factories import make_user
from apps.accounts.models import User
from apps.accounts.tests_employee_scope import make_branch
from apps.attendance import services_absence as absence
from apps.attendance.models import AttendanceCorrection, AttendancePunch
from apps.attendance.models_device import AttendanceDevice, DevicePunchLog
from apps.attendance.services_device_push import push_punches
from apps.hrms.models import SEP_APPROVED, SeparationRequest

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


def _person(name: str, number: int, joined, branch: str, **extra) -> User:
    return make_user(
        f'lg_{name}@test.com', employee_id=f'LG{number:03d}', branch=branch, date_of_joining=joined,
        onboarding_status=User.ONBOARDING_COMPLETE, **extra,
    )


def _separate(employee: User, last_day: datetime.date) -> None:
    SeparationRequest.objects.create(
        employee=employee, separation_type='resignation', request_date=TODAY - 40 * DAY,
        proposed_last_working_day=last_day, status=SEP_APPROVED,
    )


class _Fixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('LG-A', 'Lifecycle Gaps Branch')
        name = cls.branch.branch_name
        cls.active = _person('active', 1, TODAY - 30 * DAY, name)
        cls.pre = _person('pre', 2, TODAY + 5 * DAY, name)
        cls.unknown = _person('unknown', 3, None, name)
        cls.terminated = _person('terminated', 4, TODAY - 100 * DAY, name)
        _separate(cls.terminated, TODAY - DAY)
        cls.on_notice = _person('notice', 5, TODAY - 100 * DAY, name)
        _separate(cls.on_notice, TODAY + 3 * DAY)
        cls.by_stage = {'Active': cls.active, 'Pre-Joining': cls.pre, 'Unknown': cls.unknown, 'Terminated': cls.terminated}


class DevicePunchTests(_Fixtures):
    """A device serves ONLY active employees of its own branch whose Employment Stage allows punching. It is told a generic
    code, never a date or an account state; the internal log keeps the specific (non-personal) reason."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_branch = make_branch('LG-B', 'Lifecycle Gaps Other Branch')
        cls.elsewhere = _person('elsewhere', 20, TODAY - 30 * DAY, cls.other_branch.branch_name)
        cls.inactive = _person('inactive', 21, TODAY - 30 * DAY, cls.branch.branch_name, is_active=False)
        cls.rehired = _person('rehired', 22, TODAY - 60 * DAY, cls.branch.branch_name)
        _separate(cls.rehired, TODAY - 200 * DAY)
        cls.extended = _person('extended', 23, TODAY - 400 * DAY, cls.branch.branch_name)
        _separate(cls.extended, TODAY - 10 * DAY)
        _separate(cls.extended, TODAY + 20 * DAY)

    def setUp(self):
        self.device = AttendanceDevice.objects.create(code='LG-DEV', name='Lifecycle device', branch=self.branch)

    def _push(self, employee_code: str, punch_id: str, device=None):
        return push_punches(device or self.device, [{
            'device_punch_id': punch_id, 'employee_code': employee_code, 'punch_type': 'IN', 'device_time': timezone.now(),
        }])[0]

    def _log(self, punch_id: str, device=None) -> DevicePunchLog:
        return DevicePunchLog.objects.get(device=device or self.device, device_punch_id=punch_id)

    def test_only_an_active_employee_of_the_branch_is_accepted(self):
        for stage, employee in self.by_stage.items():
            result = self._push(employee.employee_id, f'p-{employee.employee_id}')
            punches = AttendancePunch.objects.filter(employee=employee, source='biometric').count()
            expected = ('accepted', 1) if stage == 'Active' else ('rejected', 0)
            self.assertEqual((result.status, punches), expected, stage)

    def test_lifecycle_rejections_are_generic_for_the_device_and_specific_in_the_log(self):
        expected_internal = {self.pre: 'pre_joining', self.unknown: 'no_joining_date', self.terminated: 'terminated'}
        for employee, internal in expected_internal.items():
            result = self._push(employee.employee_id, f'why-{employee.employee_id}')
            self.assertEqual((result.status, result.reason), ('rejected', 'not_eligible'))
            entry = self._log(f'why-{employee.employee_id}')
            self.assertEqual((entry.status, entry.reject_reason, entry.punch_id), ('rejected', internal, None))

    def test_a_device_is_never_told_a_date_or_personal_detail(self):
        for employee in (self.pre, self.unknown, self.terminated, self.inactive, self.elsewhere):
            result = self._push(employee.employee_id, f'safe-{employee.employee_id}')
            told = str(result.as_dict())
            for secret in (str(TODAY.year), 'joining', 'Nov', employee.full_name, employee.email, employee.branch):
                self.assertNotIn(secret, told, (employee.employee_id, secret))
            self.assertIn(result.reason, ('not_eligible', 'unknown_employee'))

    def test_an_employee_of_another_branch_is_rejected_like_an_unknown_code(self):
        other = self._push(self.elsewhere.employee_id, 'xb-1')
        missing = self._push('NO-SUCH-CODE', 'xb-2')
        self.assertEqual((other.status, other.reason), (missing.status, missing.reason))          # indistinguishable to the device
        self.assertEqual(self._log('xb-1').reject_reason, 'wrong_branch')
        self.assertEqual(self._log('xb-2').reject_reason, 'unknown_employee')
        self.assertFalse(AttendancePunch.objects.filter(employee=self.elsewhere).exists())

    def test_the_other_branchs_own_device_accepts_them(self):
        other_device = AttendanceDevice.objects.create(code='LG-DEV-B', name='Other device', branch=self.other_branch)
        self.assertEqual(self._push(self.elsewhere.employee_id, 'ok-b', device=other_device).status, 'accepted')
        self.assertEqual(self._push(self.active.employee_id, 'no-a', device=other_device).status, 'rejected')

    def test_an_inactive_employee_is_rejected(self):
        result = self._push(self.inactive.employee_id, 'in-1')
        self.assertEqual((result.status, result.reason), ('rejected', 'not_eligible'))
        self.assertEqual(self._log('in-1').reject_reason, 'inactive_employee')
        self.assertFalse(AttendancePunch.objects.filter(employee=self.inactive).exists())

    def test_a_device_without_a_branch_serves_nobody(self):
        unassigned = AttendanceDevice.objects.create(code='LG-DEV-NONE', name='No branch', branch=None)
        result = self._push(self.active.employee_id, 'nb-1', device=unassigned)
        self.assertEqual((result.status, result.reason), ('rejected', 'unknown_employee'))
        self.assertEqual(self._log('nb-1', device=unassigned).reject_reason, 'device_has_no_branch')

    def test_employment_after_a_rehire_or_an_extension_is_accepted(self):
        self.assertEqual(self._push(self.on_notice.employee_id, 'notice-1').status, 'accepted')
        self.assertEqual(self._push(self.rehired.employee_id, 'rehire-1').status, 'accepted')     # old separation is history
        self.assertEqual(self._push(self.extended.employee_id, 'ext-1').status, 'accepted')       # latest last day is in the future

    def test_a_branch_is_matched_by_name_for_an_employee_without_a_branch_record(self):
        User.objects.filter(pk=self.active.pk).update(branch_fk=None)
        self.assertEqual(self._push(self.active.employee_id, 'legacy-1').status, 'accepted')
        User.objects.filter(pk=self.active.pk).update(branch='Some Other Name')
        self.assertEqual(self._push(self.active.employee_id, 'legacy-2').status, 'rejected')

    def test_a_rejected_push_is_not_retried_as_new(self):
        self._push(self.pre.employee_id, 'again-1')
        self.assertEqual(self._push(self.pre.employee_id, 'again-1').status, 'duplicate')
        self.assertEqual(AttendancePunch.objects.filter(employee=self.pre).count(), 0)


class CorrectionRequestTests(_Fixtures):
    URL = '/api/attendance/correction/'

    def _post(self, employee: User):
        client = APIClient()
        client.force_authenticate(user=employee)
        reason = AttendanceCorrection.REASON_CHOICES[0][0]
        return client.post(self.URL, {
            'date': (TODAY - DAY).isoformat(), 'punch_type': 'IN', 'correct_in_time': '09:30:00', 'reason': reason,
        }, format='json')

    def test_pre_joining_unknown_and_terminated_are_refused(self):
        for stage in ('Pre-Joining', 'Unknown', 'Terminated'):
            employee = self.by_stage[stage]
            response = self._post(employee)
            self.assertEqual(response.status_code, 403, f'{stage}: {response.content}')
            self.assertEqual(response.json()['message'], lifecycle.block_message(employee, lifecycle.ACTION_PUNCH), stage)
            self.assertFalse(AttendanceCorrection.objects.filter(employee=employee).exists(), stage)

    def test_an_active_employee_can_still_request_a_correction(self):
        response = self._post(self.active)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AttendanceCorrection.objects.filter(employee=self.active).exists())

    def test_an_employee_on_notice_can_still_request_a_correction(self):
        self.assertEqual(self._post(self.on_notice).status_code, 201)


class AbsenceAlertTests(_Fixtures):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        name = cls.branch.branch_name
        cls.joined_three_days_ago = _person('joined3', 10, TODAY - 3 * DAY, name)
        cls.joined_yesterday = _person('joinedy', 11, TODAY - DAY, name)
        cls.joins_today = _person('joinstoday', 12, TODAY, name)

    def _alerts(self, threshold: int = 2) -> dict:
        """employee_id -> consecutive absent days, for everyone an alert would be sent for."""
        config = SimpleNamespace(is_enabled=True, alert_after_days=threshold, notify_whom='manager')
        fired: dict = {}
        with mock.patch.object(absence, '_get_config', return_value=config), \
             mock.patch.object(absence, '_alert_sent_today', return_value=False), \
             mock.patch.object(absence, '_get_weekly_off_days', side_effect=lambda employee, start, end: defaultdict(set)), \
             mock.patch.object(absence, '_get_approved_leave_dates', return_value=set()), \
             mock.patch.object(absence, '_fire_alert', side_effect=lambda employee, days, whom: fired.__setitem__(employee.employee_id, days)):
            absence.detect_absence_alerts()
        return fired

    def test_no_alert_before_joining_or_without_a_joining_date(self):
        fired = self._alerts()
        self.assertNotIn(self.pre.employee_id, fired)
        self.assertNotIn(self.unknown.employee_id, fired)

    def test_after_joining_only_days_since_joining_count(self):
        fired = self._alerts()
        self.assertEqual(fired[self.joined_three_days_ago.employee_id], 2)   # reaches the threshold, days before joining ignored
        self.assertNotIn(self.joined_yesterday.employee_id, fired)           # only one working day since joining: under the threshold
        self.assertNotIn(self.joins_today.employee_id, fired)                # joins today: no earlier day can be an absence
        self.assertIn(self.active.employee_id, fired)

    def test_days_before_joining_are_never_counted(self):
        # Threshold 5 would be reached by 6 empty days; the employee joined 3 days ago, so at most 3 can ever count.
        fired = self._alerts(threshold=5)
        self.assertNotIn(self.joined_three_days_ago.employee_id, fired)
        with mock.patch.object(absence, '_get_weekly_off_days', side_effect=lambda employee, start, end: defaultdict(set)), \
             mock.patch.object(absence, '_get_approved_leave_dates', return_value=set()):
            self.assertEqual(absence._count_consecutive_absent_days(self.joined_three_days_ago, TODAY, 5), 3)
            self.assertEqual(absence._count_consecutive_absent_days(self.joins_today, TODAY, 5), 0)

    def test_no_alert_after_termination_but_still_during_notice(self):
        fired = self._alerts()
        self.assertNotIn(self.terminated.employee_id, fired)       # approved last working day has passed
        self.assertIn(self.on_notice.employee_id, fired)           # still employed until the last working day

    def test_onboarding_state_no_longer_decides_who_is_checked(self):
        User.objects.filter(pk=self.active.pk).update(onboarding_status=User.ONBOARDING_PENDING)
        self.assertIn(self.active.employee_id, self._alerts())
