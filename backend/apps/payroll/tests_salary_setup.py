"""Salary Setup: every employee reachable page by page with their salary record, KPI counts from a summary (not the
loaded page), one shared "payroll ready" rule, a hire-created salary showing as configured, out-of-range pages that
return nothing instead of the last page, and no duplicate revisions for an unchanged save."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.payroll.models import EmployeeSalaryConfig, SalaryStructure
from apps.payroll.services_payroll_readiness import (
    BLOCKER_NO_BANK, BLOCKER_NO_SALARY, BLOCKER_NO_STRUCTURE, BLOCKER_NOT_EFFECTIVE, payroll_readiness, payroll_employees,
)

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
TOMORROW = TODAY + datetime.timedelta(days=1)


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class SalarySetupBase(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('ss-admin@test.com', is_superuser=True)
        self.client = _api(self.admin)
        # Exactly one default structure, so every employee has a structure unless a test removes it.
        SalaryStructure.objects.update(is_default=False)
        self.structure = SalaryStructure.objects.create(name='Salary setup test default', is_default=True)
        self.employees = []

    def employee(self, n, bank=True, ctc=None, effective=YESTERDAY, **extra):
        user = make_user(f'ss-emp-{n}@test.com', employee_id=f'SS{n:03d}', full_name=f'Employee {n:03d}', **extra)
        if bank:
            EmployeeProfile.objects.update_or_create(user=user, defaults={'account_number': '1234567890', 'ifsc_code': 'HDFC0001234'})
        if ctc is not None:
            EmployeeSalaryConfig.objects.create(employee=user, annual_ctc=Decimal(ctc), effective_from=effective, is_active=True)
        self.employees.append(user)
        return user

    def get(self, name, **params):
        return self.client.get(reverse(name), params)

    def summary(self):
        return self.get('salary-setup-summary').data['data']


class PaginationAndKpiTests(SalarySetupBase):
    def test_every_employee_is_reachable_page_by_page_with_their_salary(self):
        for n in range(25):
            self.employee(n, ctc=600000 + n if n % 2 == 0 else None)
        seen = []
        for page in (1, 2, 3):
            resp = self.get('salary-setup-list', page=page, page_size=10, search='Employee ')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data['data']['count'], 25)
            self.assertEqual(resp.data['data']['total_pages'], 3)
            seen.extend(resp.data['data']['results'])
        self.assertEqual(len({row['uuid'] for row in seen}), 25)
        for row in seen:
            number = int(row['employee_id'][2:])
            self.assertEqual(row['state'], 'configured' if number % 2 == 0 else 'missing', row['employee_id'])
            self.assertEqual(row['salary'] is not None, number % 2 == 0)

    def test_the_kpis_come_from_the_summary_not_the_loaded_page(self):
        for n in range(25):
            self.employee(n, ctc=500000 if n < 17 else None)
        # The employees created by the factory for the admin also count; compare to the live definition.
        summary = self.summary()
        snapshot = payroll_readiness(payroll_employees())
        self.assertEqual(summary['total'], len(snapshot.employee_ids))
        self.assertEqual(summary['configured'], len(snapshot.configured_ids))
        self.assertEqual(summary['missing'], summary['total'] - summary['configured'])
        self.assertEqual(summary['payroll_ready'], len(snapshot.ready_ids))
        self.assertGreaterEqual(summary['configured'], 17)
        self.assertEqual(len(summary['requirements']), 3)

    def test_the_hr_dashboard_agrees_with_salary_setup(self):
        for n in range(6):
            self.employee(n, ctc=500000 if n < 4 else None)
        summary = self.summary()
        hr = self.client.get('/api/dashboard/hr/overview/')
        self.assertEqual(hr.status_code, 200, hr.data)
        payload = hr.data['data']
        self.assertEqual(payload['payroll_ready'], summary['payroll_ready'])
        self.assertEqual(payload['payroll_blocked'], summary['blocked'])

    def test_out_of_range_pages_are_empty_not_the_last_page(self):
        for n in range(5):
            self.employee(n, ctc=500000)
        resp = self.get('salary-setup-list', page=9, page_size=2, search='Employee ')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['results'], [])
        self.assertEqual(resp.data['data']['count'], 5)
        old = self.get('employee-salary-list', page=9, page_size=2)
        self.assertEqual(old.data['data']['results'], [])


class FiltersAndAccessTests(SalarySetupBase):
    def test_search_and_status_filters(self):
        self.employee(1, ctc=500000)
        self.employee(2)
        self.employee(3, bank=False, ctc=500000)
        names = lambda **params: {r['employee_id'] for r in self.get('salary-setup-list', search='Employee ', **params).data['data']['results']}
        self.assertEqual(names(), {'SS001', 'SS002', 'SS003'})
        self.assertEqual(names(status='configured'), {'SS001', 'SS003'})
        self.assertEqual(names(status='missing'), {'SS002'})
        self.assertEqual(names(status='ready'), {'SS001'})
        self.assertEqual(names(status='blocked'), {'SS002', 'SS003'})
        only = self.get('salary-setup-list', search='SS002').data['data']['results']
        self.assertEqual([r['employee_id'] for r in only], ['SS002'])

    def test_an_unknown_status_is_rejected(self):
        self.assertEqual(self.get('salary-setup-list', status='nonsense').status_code, 400)

    def test_viewing_needs_payroll_view(self):
        plain = make_user('ss-plain@test.com', role=make_role('ss_plain'))
        self.assertEqual(_api(plain).get(reverse('salary-setup-list')).status_code, 403)
        self.assertEqual(_api(plain).get(reverse('salary-setup-summary')).status_code, 403)

    def test_a_branch_user_only_sees_their_own_branch(self):
        self.employee(1, ctc=500000, branch='Alpha Office')
        self.employee(2, ctc=500000, branch='Beta Office')
        viewer = make_user('ss-branch@test.com', role=make_role('ss_branch', permission_codenames=['payroll.view']), branch='Alpha Office')
        rows = _api(viewer).get(reverse('salary-setup-list'), {'search': 'Employee '}).data['data']['results']
        self.assertEqual({r['employee_id'] for r in rows}, {'SS001'})


class PayrollReadyDefinitionTests(SalarySetupBase):
    def blockers(self, user):
        row = self.get('salary-setup-list', search=user.employee_id).data['data']['results'][0]
        return row['blockers'], row['payroll_ready'], row['state']

    def test_a_current_record_structure_and_bank_make_an_employee_ready(self):
        user = self.employee(1, ctc=600000)
        self.assertEqual(self.blockers(user), ([], True, 'configured'))

    def test_no_salary_record_blocks(self):
        user = self.employee(1)
        blockers, ready, state = self.blockers(user)
        self.assertEqual((blockers, ready, state), ([BLOCKER_NO_SALARY], False, 'missing'))

    def test_a_record_that_starts_in_the_future_is_configured_but_not_ready(self):
        user = self.employee(1, ctc=600000, effective=TOMORROW)
        blockers, ready, state = self.blockers(user)
        self.assertEqual((blockers, ready, state), ([BLOCKER_NOT_EFFECTIVE], False, 'scheduled'))
        self.assertEqual(self.summary()['scheduled'], 1)
        self.assertEqual(self.summary()['missing'], self.summary()['total'] - self.summary()['configured'])

    def test_missing_bank_details_block(self):
        user = self.employee(1, bank=False, ctc=600000)
        self.assertEqual(self.blockers(user)[0], [BLOCKER_NO_BANK])
        EmployeeProfile.objects.update_or_create(user=user, defaults={'account_number': '1234567890', 'ifsc_code': ''})
        self.assertEqual(self.blockers(user)[0], [BLOCKER_NO_BANK])

    def test_a_zero_ctc_record_does_not_count(self):
        user = self.employee(1, ctc=0)
        self.assertEqual(self.blockers(user)[0], [BLOCKER_NO_SALARY])

    def test_without_any_structure_employees_are_blocked(self):
        user = self.employee(1, ctc=600000)
        SalaryStructure.objects.update(is_default=False)
        self.assertEqual(self.blockers(user)[0], [BLOCKER_NO_STRUCTURE])
        config = EmployeeSalaryConfig.objects.get(employee=user)
        config.salary_structure = self.structure
        config.save(update_fields=['salary_structure'])
        self.assertEqual(self.blockers(user)[0], [])  # the record's own structure resolves it


class HireRecordTests(SalarySetupBase):
    def test_a_salary_set_at_hire_shows_as_configured_without_assigning_ctc(self):
        from apps.accounts.views_hire_complete import _assign_salary_and_tax

        user = self.employee(1, date_of_joining=YESTERDAY)
        _assign_salary_and_tax(user, {'annual_ctc': '720000'}, self.admin)
        row = self.get('salary-setup-list', search=user.employee_id).data['data']['results'][0]
        self.assertEqual(row['state'], 'configured')
        self.assertTrue(row['payroll_ready'])
        self.assertEqual(Decimal(row['salary']['annual_ctc']), Decimal('720000'))
        self.assertEqual(row['salary']['reason_note'], 'Set at hire')

    def test_a_hire_dated_in_the_future_is_scheduled_not_missing(self):
        from apps.accounts.views_hire_complete import _assign_salary_and_tax

        user = self.employee(1, date_of_joining=TOMORROW)
        _assign_salary_and_tax(user, {'annual_ctc': '720000'}, self.admin)
        self.assertEqual(self.get('salary-setup-list', search=user.employee_id).data['data']['results'][0]['state'], 'scheduled')


class SavingTests(SalarySetupBase):
    def _save(self, user, ctc, **extra):
        payload = {'employee': str(user.pk), 'annual_ctc': ctc, 'effective_from': TODAY.isoformat()}
        payload.update(extra)
        return self.client.post(reverse('employee-salary-list'), payload, format='json')

    def test_a_first_save_creates_the_record_and_the_row_shows_it(self):
        user = self.employee(1)
        resp = self._save(user, '600000')
        self.assertEqual(resp.status_code, 201, resp.data)
        row = self.get('salary-setup-list', search=user.employee_id).data['data']['results'][0]
        self.assertEqual(row['state'], 'configured')

    def test_saving_the_same_ctc_again_creates_no_revision(self):
        user = self.employee(1)
        self._save(user, '600000')
        for _ in range(2):
            again = self._save(user, '600000')
            self.assertEqual(again.status_code, 200, again.data)
            self.assertTrue(again.data['data']['unchanged'])
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=user).count(), 1)

    def test_the_same_pay_on_a_different_date_is_still_no_change(self):
        user = self.employee(1)
        self._save(user, '600000')
        again = self._save(user, '600000', effective_from=(TODAY + datetime.timedelta(days=30)).isoformat())
        self.assertTrue(again.data['data']['unchanged'])
        self.assertEqual(EmployeeSalaryConfig.objects.filter(employee=user).count(), 1)

    def test_a_different_ctc_creates_a_new_revision_and_retires_the_old_one(self):
        user = self.employee(1)
        self._save(user, '600000')
        changed = self._save(user, '650000', effective_from=(TODAY + datetime.timedelta(days=1)).isoformat())
        self.assertEqual(changed.status_code, 201, changed.data)
        records = EmployeeSalaryConfig.objects.filter(employee=user)
        self.assertEqual(records.count(), 2)
        self.assertEqual(records.filter(is_active=True).count(), 1)
        self.assertEqual(records.get(is_active=True).annual_ctc, Decimal('650000'))

    def test_a_different_structure_is_a_change(self):
        user = self.employee(1)
        self._save(user, '600000')
        other = SalaryStructure.objects.create(name='Another structure for setup test')
        changed = self._save(user, '600000', salary_structure=str(other.pk))
        self.assertEqual(changed.status_code, 201, changed.data)

    def test_empty_or_non_positive_ctc_is_rejected_with_a_message(self):
        user = self.employee(1)
        for ctc in ('', '0', '-5'):
            resp = self._save(user, ctc)
            self.assertEqual(resp.status_code, 400, (ctc, resp.data))
            self.assertTrue(resp.data['message'])
        self.assertFalse(EmployeeSalaryConfig.objects.filter(employee=user).exists())
