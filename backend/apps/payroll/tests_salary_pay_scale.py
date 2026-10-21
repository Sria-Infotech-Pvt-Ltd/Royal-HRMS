"""The Basic pay dialog stores pay-scale details and earnings overrides on the salary record."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeeSalaryConfig

BRANCH = 'Test Branch'
URL = '/api/payroll/employee-salary/'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class SalaryPayScaleFieldsTests(TestCase):
    def setUp(self):
        cache.clear()
        editor_role = make_role('ps_payroll', permission_codenames=['payroll.view', 'payroll.edit', 'employees.view'])
        viewer_role = make_role('ps_viewer', permission_codenames=['payroll.view'])
        self.editor = make_user('ps_edit@test.com', role=editor_role, employee_id='PS1', branch=BRANCH)
        self.viewer = make_user('ps_view@test.com', role=viewer_role, employee_id='PS2', branch=BRANCH)
        self.employee = make_user('ps_emp@test.com', employee_id='PS3', branch=BRANCH)

    def _body(self, **overrides):
        body = {
            'employee': self.employee.employee_id, 'annual_ctc': '900000', 'effective_from': '2026-04-01',
            'reason': 'initial', 'pay_scale_group': 'L2', 'pay_scale_level': '01', 'basic_percent': 45,
            'earnings_override': {'hra': 20000, 'conv': 1600},
        }
        body.update(overrides)
        return body

    def test_editor_can_store_pay_scale_details_and_overrides(self):
        response = _api(self.editor).post(URL, self._body(), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        config = EmployeeSalaryConfig.objects.get(employee=self.employee)
        self.assertEqual((config.pay_scale_group, config.pay_scale_level, config.basic_percent), ('L2', '01', 45))
        self.assertEqual(config.earnings_override, {'hra': 20000, 'conv': 1600})
        self.assertEqual(config.get_reason_display(), 'Initial basic pay')

    def test_history_returns_the_stored_details(self):
        _api(self.editor).post(URL, self._body(), format='json')
        rows = _api(self.editor).get(f'/api/payroll/employee-salary/history/{self.employee.pk}/').data['data']
        self.assertEqual(rows[0]['pay_scale_group'], 'L2')
        self.assertEqual(rows[0]['earnings_override'], {'hra': 20000, 'conv': 1600})

    def test_same_record_can_be_updated_in_place(self):
        created = _api(self.editor).post(URL, self._body(), format='json').data['data']
        response = _api(self.editor).put(f'{URL}{created["id"]}/', {'basic_percent': 50, 'earnings_override': {}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(EmployeeSalaryConfig.objects.get(pk=created['id']).basic_percent, 50)

    def test_invalid_values_are_rejected(self):
        for bad in (
            {'pay_scale_group': 'Z9'}, {'pay_scale_level': '99'}, {'basic_percent': 33},
            {'earnings_override': {'special': 5}}, {'earnings_override': {'hra': -1}}, {'earnings_override': {'hra': 'x'}},
        ):
            response = _api(self.editor).post(URL, self._body(**bad), format='json')
            self.assertEqual(response.status_code, 400, bad)

    def test_a_viewer_cannot_save(self):
        self.assertEqual(_api(self.viewer).post(URL, self._body(), format='json').status_code, 403)


class AnnualCtcRoundTripTests(TestCase):
    """UAT: 400000 came back as 399996. The save endpoint must store and return the annual CTC exactly as sent."""

    def setUp(self):
        cache.clear()
        editor_role = make_role('ctc_payroll', permission_codenames=['payroll.view', 'payroll.edit', 'employees.view'])
        self.editor = make_user('ctc_edit@test.com', role=editor_role, employee_id='CTC1', branch=BRANCH)

    def _save_and_read_back(self, annual_ctc, employee_id):
        employee = make_user(f'{employee_id.lower()}@test.com', employee_id=employee_id, branch=BRANCH)
        body = {
            'employee': employee.employee_id, 'annual_ctc': annual_ctc, 'effective_from': '2026-10-12',
            'reason': 'initial', 'pay_scale_group': 'L2', 'pay_scale_level': '01', 'basic_percent': 40,
            'earnings_override': {},
        }
        response = _api(self.editor).post(URL, body, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        stored = EmployeeSalaryConfig.objects.get(employee=employee).annual_ctc
        history = _api(self.editor).get(f'/api/payroll/employee-salary/history/{employee.pk}/').data['data']
        return stored, history[0]['annual_ctc']

    def test_uat_values_round_trip_exactly(self):
        for index, annual_ctc in enumerate((400000, 750000, 2800000, 400001, 399999, 1000000, 123457)):
            with self.subTest(annual_ctc=annual_ctc):
                stored, returned = self._save_and_read_back(annual_ctc, f'CTCRT{index}')
                self.assertEqual(int(stored), annual_ctc)
                self.assertEqual(int(float(returned)), annual_ctc)

    def test_update_in_place_keeps_exact_amount(self):
        employee = make_user('ctc_upd@test.com', employee_id='CTCUPD', branch=BRANCH)
        created = _api(self.editor).post(URL, {
            'employee': employee.employee_id, 'annual_ctc': 750000, 'effective_from': '2026-10-12', 'reason': 'initial',
        }, format='json').data['data']
        response = _api(self.editor).put(f'{URL}{created["id"]}/', {'annual_ctc': 400000}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(int(EmployeeSalaryConfig.objects.get(pk=created['id']).annual_ctc), 400000)
