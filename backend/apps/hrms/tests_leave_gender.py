"""Gender-restricted leave types (e.g. female-only "Pink Leave").

Covers: the apply-time check reads gender from the employee profile and refuses
inactive types; the policy list tells each employee which types they may apply
for; every balance-creating path respects the gender rule (create with gender,
HR "credit balances"); and the clean-up command removes only unused wrong-gender
balances, dry run by default.
"""
from __future__ import annotations

import datetime
import io
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.hrms.models import LeaveBalance, LeaveCreditTransaction, LeavePolicy, LeaveRequest
from apps.hrms.tests import _future_monday, _login

PINK = 'pink_leave_g'


class GenderLeaveBase(TestCase):
    def setUp(self):
        cache.clear()
        long_ago = datetime.date.today().replace(year=datetime.date.today().year - 3)
        emp_role = make_role('gender_leave_emp', permission_codenames=['leave.apply'])
        hr_role = make_role('gender_leave_hr', permission_codenames=['settings.edit', 'leave.approve'])
        self.hr = make_user('gl.hr@test.com', role=hr_role, password='TestPass123!', employee_id='GLHR',
                            date_of_joining=long_ago, onboarding_status='complete')
        EmployeeProfile.objects.create(user=self.hr, gender='female')
        self.man = make_user('gl.man@test.com', role=emp_role, password='TestPass123!', employee_id='GLM1',
                             date_of_joining=long_ago, onboarding_status='complete', reporting_manager=self.hr)
        EmployeeProfile.objects.create(user=self.man, gender='male')
        self.woman = make_user('gl.woman@test.com', role=emp_role, password='TestPass123!', employee_id='GLF1',
                               date_of_joining=long_ago, onboarding_status='complete', reporting_manager=self.hr)
        EmployeeProfile.objects.create(user=self.woman, gender='female')
        self.leave_date = _future_monday()

    def pink(self, **kw):
        kw.setdefault('applicable_gender', 'female')
        kw.setdefault('is_active', True)
        return LeavePolicy.objects.create(leave_type=PINK, leave_type_label='Pink Leave G',
                                          annual_days=Decimal('12.0'), **kw)

    def balance(self, user, leave_type=PINK, year=None, **kw):
        kw.setdefault('total_days', Decimal('12.0'))
        kw.setdefault('used_days', Decimal('0'))
        return LeaveBalance.objects.create(employee=user, leave_type=leave_type,
                                           year=year or self.leave_date.year, **kw)

    def client_for(self, email):
        c = APIClient()
        _login(c, email)
        return c

    def apply(self, email, leave_type=PINK):
        return self.client_for(email).post(reverse('leave-request-list'), {
            'leave_type': leave_type, 'duration': 'full_day', 'start_date': self.leave_date.isoformat(),
            'end_date': self.leave_date.isoformat(), 'reason': 'Personal reasons for this leave.',
        }, format='json')


class ApplyTimeGenderTests(GenderLeaveBase):
    def test_male_with_a_wrong_balance_cannot_apply(self):
        self.pink()
        self.balance(self.man)                                          # the pre-fix situation in production
        resp = self.apply('gl.man@test.com')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('gender restriction', str(resp.data))
        self.assertFalse(LeaveRequest.objects.filter(employee=self.man).exists())

    def test_female_can_apply(self):
        self.pink()
        self.balance(self.woman)
        resp = self.apply('gl.woman@test.com')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_no_recorded_gender_is_not_eligible(self):
        self.pink()
        self.man.profile.gender = ''
        self.man.profile.save()
        self.balance(self.man)
        self.assertEqual(self.apply('gl.man@test.com').status_code, 400)

    def test_inactive_type_cannot_be_applied_for(self):
        self.pink(applicable_gender='all', is_active=False)              # custom: rejected by the serializer
        self.balance(self.woman)
        self.assertEqual(self.apply('gl.woman@test.com').status_code, 400)
        # Built-ins (e.g. Paternity) pass the serializer even when inactive — the
        # policy check must refuse them (production: inactive Paternity, women hold balances).
        LeavePolicy.objects.update_or_create(leave_type='paternity', defaults={'applicable_gender': 'all',
                                                                                'is_active': False})
        cache.clear()
        self.balance(self.woman, leave_type='paternity')
        resp = self.apply('gl.woman@test.com', leave_type='paternity')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('not available', str(resp.data))


class PolicyListEligibilityTests(GenderLeaveBase):
    def eligible(self, email):
        rows = self.client_for(email).get(reverse('leave-policy-list')).data['data']
        return {r['leave_type']: r['eligible_for_me'] for r in rows}

    def test_female_only_type_is_flagged_per_employee(self):
        self.pink()
        LeavePolicy.objects.update_or_create(leave_type='paternity', defaults={'applicable_gender': 'male',
                                                                                'is_active': True})
        cache.clear()
        man, woman = self.eligible('gl.man@test.com'), self.eligible('gl.woman@test.com')
        self.assertEqual((man[PINK], woman[PINK]), (False, True))
        self.assertEqual((man['paternity'], woman['paternity']), (True, False))
        self.assertTrue(man['casual'] and woman['casual'])

    def test_inactive_type_is_not_eligible(self):
        self.pink(applicable_gender='all', is_active=False)
        cache.clear()
        self.assertFalse(self.eligible('gl.woman@test.com')[PINK])


class BalanceCreationGenderTests(GenderLeaveBase):
    def test_create_with_gender_gives_balances_only_to_that_gender(self):
        resp = self.client_for('gl.hr@test.com').post(reverse('leave-policy-list'), {
            'leave_type_label': 'Pink Leave G', 'annual_days': 12, 'applicable_gender': 'female',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        holders = set(LeaveBalance.objects.filter(leave_type=PINK).values_list('employee_id', flat=True))
        self.assertIn(self.woman.pk, holders)
        self.assertNotIn(self.man.pk, holders)

    def test_hr_credit_balances_respects_gender(self):
        self.pink()
        resp = self.client_for('gl.hr@test.com').post(reverse('leave-balance-credit'),
                                                     {'year': datetime.date.today().year}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        holders = set(LeaveBalance.objects.filter(leave_type=PINK).values_list('employee_id', flat=True))
        self.assertIn(self.woman.pk, holders)
        self.assertNotIn(self.man.pk, holders)


class CleanupCommandTests(GenderLeaveBase):
    def run_cmd(self, **options):
        from apps.hrms.management.commands.cleanup_gender_ineligible_leave_balances import Command
        from apps.tenants.models import Client
        from config.test_runner import TEST_COMPANY_CODE
        client = Client.objects.get(company_code=TEST_COMPANY_CODE)
        options.setdefault('policy', None)
        options.setdefault('year', self.year)
        options.setdefault('apply', False)
        out = io.StringIO()
        Command(stdout=out).handle_tenant(client, **options)
        return out.getvalue()

    def setUp(self):
        super().setUp()
        self.year = datetime.date.today().year
        self.pink()
        self.wrong = self.balance(self.man, year=self.year)
        self.right = self.balance(self.woman, year=self.year)

    def test_dry_run_deletes_nothing(self):
        out = self.run_cmd()
        self.assertIn('Unused balances to remove: 1', out)
        self.assertIn('GLM1', out)
        self.assertIn('[DRY RUN]', out)
        self.assertNotIn('gl.man@test.com', out)                        # IDs only, no emails
        self.assertTrue(LeaveBalance.objects.filter(pk=self.wrong.pk).exists())

    def test_apply_removes_only_unused_wrong_gender_rows(self):
        out = self.run_cmd(apply=True)
        self.assertIn('Removed 1 LeaveBalance row(s).', out)
        self.assertFalse(LeaveBalance.objects.filter(pk=self.wrong.pk).exists())
        self.assertTrue(LeaveBalance.objects.filter(pk=self.right.pk).exists())

    def test_used_credited_or_requested_rows_are_kept_for_review(self):
        self.wrong.used_days = Decimal('1')
        self.wrong.save()
        man2 = make_user('gl.man2@test.com', role=self.man.role, employee_id='GLM2', onboarding_status='complete')
        EmployeeProfile.objects.create(user=man2, gender='male')
        credited = self.balance(man2, year=self.year)
        LeaveCreditTransaction.objects.create(
            balance=credited, employee=man2, leave_type=PINK, year=self.year,
            txn_type=LeaveCreditTransaction._meta.get_field('txn_type').choices[0][0], amount=Decimal('1'),
            total_before=Decimal('11'), total_after=Decimal('12'), reason='HR credit', idempotency_key='gl-test-1')
        out = self.run_cmd(apply=True)
        self.assertIn('Kept for HR review:        2', out)
        self.assertIn('day(s) used', out)
        self.assertIn('has credit history', out)
        self.assertTrue(LeaveBalance.objects.filter(pk=self.wrong.pk).exists())
        self.assertTrue(LeaveBalance.objects.filter(pk=credited.pk).exists())

    def test_other_years_untouched(self):
        old = self.balance(self.man, year=self.year - 1)
        self.run_cmd(apply=True)
        self.assertTrue(LeaveBalance.objects.filter(pk=old.pk).exists())


class GenderChangeUpdatesBalancesTests(GenderLeaveBase):
    """HR narrows a type to one gender: this year's unused balances held by the other
    gender disappear at once; used / HR-credited ones and other years are kept."""

    def put(self, gender):
        return self.client_for('gl.hr@test.com').put(
            reverse('leave-policy-detail', kwargs={'leave_type': PINK}), {'applicable_gender': gender}, format='json')

    def test_narrowing_to_female_removes_unused_male_balances(self):
        self.pink(applicable_gender='all')
        year = datetime.date.today().year
        man_bal, woman_bal = self.balance(self.man, year=year), self.balance(self.woman, year=year)
        old = self.balance(self.man, year=year - 1)
        resp = self.put('female')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('Removed 1 unused balance', resp.data['message'])
        self.assertFalse(LeaveBalance.objects.filter(pk=man_bal.pk).exists())
        self.assertTrue(LeaveBalance.objects.filter(pk=woman_bal.pk).exists())
        self.assertTrue(LeaveBalance.objects.filter(pk=old.pk).exists())      # past years untouched

    def test_used_balance_is_kept(self):
        self.pink(applicable_gender='all')
        bal = self.balance(self.man, year=datetime.date.today().year, used_days=Decimal('2'))
        self.assertEqual(self.put('female').status_code, 200)
        self.assertTrue(LeaveBalance.objects.filter(pk=bal.pk).exists())

    def test_widening_back_to_all_gives_balances_again(self):
        self.pink(applicable_gender='female')
        self.assertEqual(self.put('all').status_code, 200)
        self.assertTrue(LeaveBalance.objects.filter(employee=self.man, leave_type=PINK).exists())
