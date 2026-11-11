"""
Maximum Late Arrivals Per Month (tracking only).

Scenarios: enabled with 5, disabled, 0 / 3 / 5 / over 5 late arrivals,
calendar-month reset, different employees, Late (Excused) not counted,
the existing late-mark LOP rule unchanged (identical payroll LOP whatever
this setting is), existing stats unchanged; plus the settings API
(read-only for employees, Leave Policy admins edit, validation, no
attendance settings created implicitly) and the HR "over the limit" list
(scoped like HR attendance).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.attendance import services_late_limit as late_limit
from apps.attendance.models import AttendanceLateMarkRules, AttendanceRecord, AttendanceSettings
from apps.payroll.tests_salary_components import SalaryFixtureMixin
from apps.payroll.views.cycles import process_payroll_cycle

NOV = (2026, 11)


def late(employee, day, excused=False, month=11, year=2026):
    return AttendanceRecord.objects.create(employee=employee, date=date(year, month, day), status='late',
                                           is_late=True, late_excused=excused, first_punch_in=time(10, 5))


class LimitBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.settings_row = AttendanceSettings.objects.create(is_active=True)
        self.rules = AttendanceLateMarkRules.objects.create(settings=self.settings_row, late_marks_per_lop=3,
                                                            late_mark_mode='every_n', lop_deduction_unit='full_day')
        emp_role = make_role('ll_staff', permission_codenames=['attendance.view', 'attendance.create'])
        self.emp = make_user('ll.emp@test.com', role=emp_role, full_name='Late Lena', branch='North', employee_id='LL1')
        self.emp2 = make_user('ll.emp2@test.com', role=emp_role, full_name='Punctual Pat', branch='North',
                              employee_id='LL2')
        self.south = make_user('ll.south@test.com', role=emp_role, full_name='South Sam', branch='South',
                               employee_id='LL3')

    def summary(self, employee=None, ym=NOV):
        return late_limit.summary(employee or self.emp, *ym)


class CountingTests(LimitBase):
    def test_defaults_enabled_with_five(self):
        self.assertEqual((self.rules.late_limit_enabled, self.rules.max_late_arrivals_per_month), (True, 5))
        self.assertEqual(late_limit.get_limit(), {'enabled': True, 'maximum': 5, 'configured': True})

    def test_zero_three_five_and_over(self):
        s = self.summary()
        self.assertEqual((s['late_arrivals'], s['remaining'], s['status'], s['status_label']), (0, 5, 'within', 'Within limit'))
        for d in (2, 3, 4):
            late(self.emp, d)
        s = self.summary()
        self.assertEqual((s['late_arrivals'], s['remaining'], s['status']), (3, 2, 'within'))
        for d in (5, 6):
            late(self.emp, d)
        s = self.summary()
        self.assertEqual((s['late_arrivals'], s['remaining'], s['status'], s['status_label']), (5, 0, 'reached', 'Limit reached'))
        late(self.emp, 9)
        s = self.summary()
        self.assertEqual((s['late_arrivals'], s['remaining'], s['status'], s['status_label']), (6, 0, 'exceeded', 'Limit exceeded'))

    def test_disabled_is_not_applied(self):
        AttendanceLateMarkRules.objects.filter(pk=self.rules.pk).update(late_limit_enabled=False)
        for d in range(2, 9):
            late(self.emp, d)
        s = self.summary()
        self.assertEqual((s['enabled'], s['late_arrivals'], s['remaining'], s['status']), (False, 7, None, None))
        self.assertEqual(late_limit.employees_at_or_over(type(self.emp).objects.all(), *NOV), [])

    def test_calendar_month_reset(self):
        for d in (25, 27, 28, 29, 30, 31):
            late(self.emp, d, month=10)
        late(self.emp, 1)
        self.assertEqual(self.summary(ym=(2026, 10))['status'], 'exceeded')
        nov = self.summary()
        self.assertEqual((nov['late_arrivals'], nov['remaining'], nov['status']), (1, 4, 'within'))

    def test_excused_days_not_counted(self):
        for d in (2, 3, 4, 5, 6):
            late(self.emp, d)
        late(self.emp, 9, excused=True)
        s = self.summary()
        self.assertEqual((s['late_arrivals'], s['status']), (5, 'reached'))

    def test_only_late_days_count(self):
        AttendanceRecord.objects.create(employee=self.emp, date=date(2026, 11, 2), status='present', is_late=False)
        AttendanceRecord.objects.create(employee=self.emp, date=date(2026, 11, 3), status='absent', is_late=False)
        self.assertEqual(self.summary()['late_arrivals'], 0)

    def test_different_employees_same_company_setting(self):
        for d in range(2, 9):
            late(self.emp, d)
        late(self.emp2, 2)
        a, b = self.summary(self.emp), self.summary(self.emp2)
        self.assertEqual((a['maximum'], a['status'], b['maximum'], b['status']), (5, 'exceeded', 5, 'within'))
        AttendanceLateMarkRules.objects.filter(pk=self.rules.pk).update(max_late_arrivals_per_month=8)
        self.assertEqual(self.summary(self.emp)['status'], 'within')        # 7 of 8 — not hardcoded to 5

    def test_bad_stored_value_falls_back(self):
        AttendanceLateMarkRules.objects.filter(pk=self.rules.pk).update(max_late_arrivals_per_month=0)
        self.assertEqual(late_limit.get_limit()['maximum'], 5)

    def test_no_attendance_settings_uses_defaults(self):
        AttendanceSettings.objects.all().delete()
        self.assertEqual(late_limit.get_limit(), {'enabled': True, 'maximum': 5, 'configured': False})


class ApiTests(LimitBase):
    def setUp(self):
        super().setUp()
        admin_role = make_role('ll_leave_admin', permission_codenames=['leave.approve', 'leave.view', 'attendance.view'])
        self.admin = make_user('ll.admin@test.com', role=admin_role, full_name='Leave Admin', employee_id='LLA')
        hr_role = make_role('ll_branch_hr', permission_codenames=['attendance.view', 'attendance.edit'])
        self.branch_hr = make_user('ll.hr@test.com', role=hr_role, full_name='North HR', branch='North', employee_id='LLH')
        mgr_role = make_role('ll_mgr', permission_codenames=['attendance.view'], can_manage_team=True)
        self.mgr = make_user('ll.mgr@test.com', role=mgr_role, full_name='Mgr', branch='North', employee_id='LLM')
        self.emp2.reporting_manager = self.mgr
        self.emp2.save(update_fields=['reporting_manager'])
        self.c = {}

    def api(self, user):
        if user.email not in self.c:
            cl = APIClient()
            _login(cl, user.email)
            self.c[user.email] = cl
        return self.c[user.email]

    def put(self, user, body):
        return self.api(user).put(reverse('attendance-late-arrival-limit'), body, format='json')

    def test_employee_reads_but_cannot_change(self):
        r = self.api(self.emp).get(reverse('attendance-late-arrival-limit'))
        self.assertEqual((r.status_code, r.data['data']['maximum'], r.data['data']['can_edit']), (200, 5, False))
        self.assertEqual(self.put(self.emp, {'enabled': False, 'maximum': 9}).status_code, 403)
        self.rules.refresh_from_db()
        self.assertEqual((self.rules.late_limit_enabled, self.rules.max_late_arrivals_per_month), (True, 5))

    def test_admin_changes_and_it_persists(self):
        r = self.put(self.admin, {'enabled': False, 'maximum': 4})
        self.assertEqual(r.status_code, 200, r.data)
        again = self.api(self.emp).get(reverse('attendance-late-arrival-limit'))
        self.assertEqual((again.data['data']['enabled'], again.data['data']['maximum']), (False, 4))
        self.rules.refresh_from_db()
        # The LOP rule on the same row is untouched.
        self.assertEqual((self.rules.late_marks_per_lop, self.rules.late_mark_mode, self.rules.lop_deduction_unit),
                         (3, 'every_n', 'full_day'))

    def test_validation(self):
        for body in ({'enabled': True, 'maximum': 0}, {'enabled': True, 'maximum': -2},
                     {'enabled': True, 'maximum': 'five'}, {'enabled': True, 'maximum': 32},
                     {'enabled': True, 'maximum': 2.5}, {'enabled': True}, {'maximum': 5}):
            r = self.put(self.admin, body)
            self.assertEqual(r.status_code, 400, body)
        self.rules.refresh_from_db()
        self.assertEqual(self.rules.max_late_arrivals_per_month, 5)

    def test_no_attendance_settings_are_created(self):
        AttendanceSettings.objects.all().delete()
        r = self.put(self.admin, {'enabled': True, 'maximum': 6})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(AttendanceSettings.objects.exists())     # no default LOP rule switched on

    def test_my_attendance_stats_show_the_limit(self):
        for d in (2, 3, 4):
            late(self.emp, d)
        r = self.api(self.emp).get(reverse('attendance-stats'), {'month': 11, 'year': 2026})
        self.assertEqual(r.status_code, 200, r.data)
        lim = r.data['data']['late_limit']
        self.assertEqual((lim['maximum'], lim['late_arrivals'], lim['remaining'], lim['status_label']),
                         (5, 3, 2, 'Within limit'))
        self.assertEqual(r.data['data']['late_arrivals'], 3)          # existing stat unchanged

    def test_hr_list_and_scope(self):
        for d in range(2, 9):
            late(self.emp, d)          # North, 7 — exceeded
        for d in range(2, 7):
            late(self.emp2, d)         # North, 5 — reached
        for d in range(2, 10):
            late(self.south, d)        # South, 8 — exceeded
        url = reverse('attendance-late-arrival-limit-employees')

        def names(user, **q):
            r = self.api(user).get(url, {'month': '2026-11', **q})
            self.assertEqual(r.status_code, 200, r.data)
            return [x['name'] for x in r.data['data']['results']]
        self.assertEqual(names(self.admin), ['South Sam', 'Late Lena'])
        self.assertEqual(names(self.admin, include_reached='true'), ['South Sam', 'Late Lena', 'Punctual Pat'])
        self.assertEqual(names(self.branch_hr), ['Late Lena'])                       # own branch only
        self.assertEqual(names(self.mgr, include_reached='true'), ['Punctual Pat'])  # direct reports only
        self.assertEqual(self.api(self.emp).get(url).status_code, 403)       # attendance.view alone is not enough
        self.assertEqual(self.api(self.admin).get(url, {'month': 'Nov'}).status_code, 400)


class LopUnchangedTests(SalaryFixtureMixin, TestCase):
    """The existing late-mark LOP rule gives the same LOP whatever this setting is."""

    def setUp(self):
        cache.clear()
        self.make_fixtures()
        self.assign(self.emp_a, ctc='600000', effective='2026-01-01')
        s = AttendanceSettings.objects.create(is_active=True)
        self.rules = AttendanceLateMarkRules.objects.create(settings=s, late_marks_per_lop=3, late_mark_mode='every_n',
                                                            lop_deduction_unit='full_day')
        for d in range(5, 12):                                    # 7 late days in January
            AttendanceRecord.objects.create(employee=self.emp_a, date=date(2026, 1, d), status='late', is_late=True)

    def lop(self):
        if not hasattr(self, '_cycle'):
            self._cycle = self.cycle(1)
        process_payroll_cycle(self._cycle)            # reprocessing recalculates the same cycle
        return self.payslip(self._cycle, self.emp_a).lop_days

    def test_three_late_marks_one_lop_unchanged(self):
        expected = self.lop()
        self.assertEqual(expected, Decimal('2'))                    # 7 // 3 = 2 full days
        for enabled, maximum in ((True, 5), (False, 5), (True, 1), (True, 31)):
            AttendanceLateMarkRules.objects.filter(pk=self.rules.pk).update(
                late_limit_enabled=enabled, max_late_arrivals_per_month=maximum)
            self.assertEqual(self.lop(), expected, (enabled, maximum))
