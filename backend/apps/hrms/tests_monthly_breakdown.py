"""
Phase A — monthly leave policy settings and the employee dashboard's
month-by-month breakdown.

Policy settings (credit_schedule, monthly_carry_forward) are recorded only;
these tests also check they change no balance. The dashboard breakdown shows
recorded monthly credits / other adjustments / leave used per month, kept
separate from the yearly available balance.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import (
    CREDIT_SCHEDULE_ANNUAL, CREDIT_SCHEDULE_MONTHLY, REQ_APPROVED, LeaveBalance, LeavePolicy, LeaveRequest,
)
from apps.hrms.services_leave_credit import apply_adjustment, set_monthly_credit
from apps.hrms.tests_leave_credits import PASSWORD, YEAR, _Fixtures, _key
from config.test_runner import TEST_COMPANY_CODE

DASHBOARD_URL = '/api/dashboard/employee/leave-balances/'


def _ready(user):
    user.onboarding_status = user.ONBOARDING_COMPLETE
    user.assessment_status = 'complete'
    user.save(update_fields=['onboarding_status', 'assessment_status'])


class _Base(_Fixtures):
    def _login(self, user):
        resp = self.client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                                   'password': PASSWORD}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class LeavePolicyMonthlySettingsTests(_Base, TestCase):
    def setUp(self):
        self.make_fixtures()
        self.client = APIClient()
        self.editor = make_user('mb.editor@test.com', role=make_role('mb_editor', permission_codenames=['settings.edit']),
                                employee_id='MBED01', full_name='Policy Editor')

    def test_existing_policies_default_to_annual(self):
        self.assertEqual((self.casual.credit_schedule, self.casual.monthly_carry_forward), (CREDIT_SCHEDULE_ANNUAL, True))
        self._login(self.editor)
        rows = {p['leave_type']: p for p in self.client.get(reverse('leave-policy-list')).data['data']}
        self.assertEqual(rows['casual']['credit_schedule'], 'annual')
        self.assertTrue(rows['casual']['monthly_carry_forward'])

    def test_save_and_retrieve_settings_without_touching_balances(self):
        self._login(self.editor)
        url = reverse('leave-policy-detail', kwargs={'leave_type': 'casual'})
        before = {pk: v for pk, *v in LeaveBalance.objects.values_list('pk', 'total_days', 'used_days', 'carried_forward')}
        resp = self.client.patch(url, {'credit_schedule': 'monthly', 'monthly_carry_forward': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data['data']['credit_schedule'], resp.data['data']['monthly_carry_forward']), ('monthly', False))
        self.casual.refresh_from_db()
        self.assertEqual((self.casual.credit_schedule, self.casual.monthly_carry_forward), (CREDIT_SCHEDULE_MONTHLY, False))
        after = {pk: v for pk, *v in LeaveBalance.objects.filter(pk__in=before).values_list('pk', 'total_days', 'used_days', 'carried_forward')}
        self.assertEqual(after, before)   # saving the settings changed no existing balance
        # yearly carry-forward settings untouched
        self.assertEqual((self.casual.can_carry_forward, self.casual.max_carry_forward_days), (False, 0))

    def test_invalid_schedule_rejected(self):
        self._login(self.editor)
        url = reverse('leave-policy-detail', kwargs={'leave_type': 'casual'})
        self.assertEqual(self.client.patch(url, {'credit_schedule': 'weekly'}, format='json').status_code, 400)
        self.casual.refresh_from_db()
        self.assertEqual(self.casual.credit_schedule, CREDIT_SCHEDULE_ANNUAL)

    def test_new_leave_type_can_be_created_monthly(self):
        self._login(self.editor)
        resp = self.client.post(reverse('leave-policy-list'), {
            'leave_type_label': 'Pink Leave', 'annual_days': '0', 'credit_schedule': 'monthly', 'monthly_carry_forward': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        policy = LeavePolicy.objects.get(leave_type='pink_leave')
        self.assertEqual((policy.credit_schedule, policy.monthly_carry_forward), ('monthly', False))

    def test_unauthorised_user_cannot_change_settings(self):
        self._login(self.employee)
        url = reverse('leave-policy-detail', kwargs={'leave_type': 'casual'})
        self.assertEqual(self.client.patch(url, {'credit_schedule': 'monthly'}, format='json').status_code, 403)


class DashboardMonthlyBreakdownTests(_Base, TestCase):
    def setUp(self):
        self.make_fixtures()
        cache.clear()
        self.client = APIClient()
        _ready(self.employee)
        _ready(self.other_hyd)
        self.casual.credit_schedule = CREDIT_SCHEDULE_MONTHLY
        self.casual.save(update_fields=['credit_schedule'])
        # casual: annual balance 12 (fixture) + monthly credits Mar 2, Apr 1 + a manual +0.5
        set_monthly_credit(employee=self.employee, leave_type='casual', year=YEAR, month=3, value='2', actor=self.admin)
        set_monthly_credit(employee=self.employee, leave_type='casual', year=YEAR, month=4, value='1', actor=self.admin)
        apply_adjustment(employee=self.employee, leave_type='casual', year=YEAR, amount='0.5', reason='Bonus',
                         actor=self.admin, idempotency_key=_key())
        # earned: a monthly credit too, so two leave types have month rows
        set_monthly_credit(employee=self.employee, leave_type='earned', year=YEAR, month=3, value='1.5', actor=self.admin)
        # one approved day of casual leave in March
        day = datetime.date(YEAR, 3, 10)
        LeaveRequest.objects.create(employee=self.employee, leave_type='casual', start_date=day, end_date=day,
                                    total_days=Decimal('1'), reason='x', status=REQ_APPROVED)
        # someone else's credit must never appear
        set_monthly_credit(employee=self.other_hyd, leave_type='casual', year=YEAR, month=3, value='5', actor=self.admin)

    def _get(self, **params):
        resp = self.client.get(DASHBOARD_URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return {b['leave_type']: b for b in resp.data['data']['balances']}

    def test_months_show_recorded_credits_and_usage_per_leave_type(self):
        self._login(self.employee)
        rows = self._get(year=YEAR)
        casual = rows['casual']
        self.assertEqual((casual['credit_schedule'], casual['monthly_carry_forward']), ('monthly', True))
        self.assertTrue(casual['leave_type_label'])
        by_month = {m['month']: m for m in casual['monthly']['months']}
        self.assertEqual(by_month[3]['monthly_credit'], 2.0)
        self.assertEqual(by_month[3]['used'], 1.0)
        self.assertEqual(by_month[4]['monthly_credit'], 1.0)
        self.assertEqual(sum(m['other_adjustments'] for m in casual['monthly']['months']), 0.5)
        self.assertEqual({m['month']: m['monthly_credit'] for m in rows['earned']['monthly']['months'] if m['monthly_credit']}, {3: 1.5})
        self.assertEqual(rows['earned']['credit_schedule'], 'annual')

    def test_yearly_balance_stays_the_available_figure(self):
        self._login(self.employee)
        casual = self._get(year=YEAR)['casual']
        balance = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=YEAR)
        self.assertEqual((casual['total_days'], casual['used_days'], casual['remaining']),
                         (float(balance.total_days), float(balance.used_days), float(balance.total_days - balance.used_days)))
        recorded = sum(m['monthly_credit'] for m in casual['monthly']['months'])
        self.assertEqual(recorded, 3.0)
        self.assertNotEqual(recorded, casual['remaining'])   # monthly credits are not presented as the balance
        for m in casual['monthly']['months']:
            self.assertEqual(set(m), {'month', 'label', 'monthly_credit', 'other_adjustments', 'used'})  # no expiry/carry figures

    def test_only_own_data(self):
        self._login(self.employee)
        casual = self._get(year=YEAR, employee_id='CREMP02')['casual']   # an employee_id param is ignored
        self.assertEqual({m['month']: m['monthly_credit'] for m in casual['monthly']['months'] if m['monthly_credit']}, {3: 2.0, 4: 1.0})
        self._login(self.other_hyd)
        other = self._get(year=YEAR)['casual']
        self.assertEqual({m['month']: m['monthly_credit'] for m in other['monthly']['months'] if m['monthly_credit']}, {3: 5.0})
        self.assertEqual(self.client.get(DASHBOARD_URL).status_code, 200)
        self.client.logout()
        self.client.cookies.clear()
        self.assertIn(self.client.get(DASHBOARD_URL).status_code, (401, 403))

    def test_cache_refreshes_after_monthly_credit_edit(self):
        self._login(self.employee)
        self.assertEqual({m['month']: m['monthly_credit'] for m in self._get(year=YEAR)['casual']['monthly']['months']}[3], 2.0)
        with self.captureOnCommitCallbacks(execute=True):
            set_monthly_credit(employee=self.employee, leave_type='casual', year=YEAR, month=3, value='3', actor=self.admin)
        casual = self._get(year=YEAR)['casual']
        self.assertEqual({m['month']: m['monthly_credit'] for m in casual['monthly']['months']}[3], 3.0)
        self.assertEqual(casual['total_days'], float(LeaveBalance.objects.get(
            employee=self.employee, leave_type='casual', year=YEAR).total_days))

    def test_months_run_to_current_month_plus_months_with_activity(self):
        from django.utils import timezone
        self._login(self.employee)
        months = self._get(year=YEAR)['casual']['monthly']['months']
        this_month = timezone.localdate().month
        self.assertTrue(set(range(1, this_month + 1)) <= {m['month'] for m in months})
        for m in months:   # later months appear only when something was recorded
            if m['month'] > this_month:
                self.assertTrue(m['monthly_credit'] or m['other_adjustments'] or m['used'])
