"""Salary structures: components change from an effective date, warn how many employees are affected, keep history,
and every change to a structure, a component or an allowance is written to the audit log."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.payroll.models import (
    EmployeeSalaryConfig, PayComponent, SalaryComponent, SalaryComponentRevision, SalaryStructure,
)
from apps.payroll.services_salary_structure import effective_components, next_pay_cycle_start

LONG_AGO = datetime.date(1900, 1, 1)


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class SalaryStructureChangeTests(TestCase):
    def setUp(self):
        cache.clear()
        admin_role = make_role('structure_admin', permission_codenames=['payroll.view', 'payroll.create', 'payroll.edit', 'payroll.delete'])
        self.admin = make_user('structure-admin@test.com', role=admin_role)
        self.viewer = make_user('structure-viewer@test.com', role=make_role('structure_viewer', permission_codenames=['payroll.view']))
        self.employee = make_user('structure-employee@test.com', employee_id='STR001')
        self.structure = SalaryStructure.objects.create(name='Effective-date test structure')
        self.cycle_start = next_pay_cycle_start()

    def _component(self, name='Special Pay', order=10, is_active=True):
        component = SalaryComponent.objects.create(
            structure=self.structure, name=name, code=name.upper().replace(' ', '_'),
            component_type=SalaryComponent.TYPE_EARNING, calculation_type=SalaryComponent.CALC_FIXED,
            value=Decimal('500'), order=order, is_active=is_active,
        )
        # What the migration does for every existing component: a baseline revision in force from the start.
        SalaryComponentRevision.objects.create(component=component, effective_from=LONG_AGO, configuration={
            'code': component.code, 'name': name, 'component_type': 'earning', 'calculation_type': 'fixed',
            'value': '500', 'is_taxable': True, 'is_active': is_active, 'order': order,
        })
        return component

    def _assign_employee(self):
        return EmployeeSalaryConfig.objects.create(
            employee=self.employee, annual_ctc=Decimal('600000'), effective_from=datetime.date(2026, 1, 1),
            salary_structure=self.structure, is_active=True,
        )

    def _components_url(self, *parts):
        return '/'.join(['/api/payroll/structures', str(self.structure.pk), 'components', *[str(p) for p in parts]]) + '/'

    # ── adding a component ─────────────────────────────────────────────────────

    def test_new_component_starts_on_the_next_pay_cycle_and_is_audited(self):
        resp = _api(self.admin).post(self._components_url(), {
            'name': 'Internet', 'component_type': 'earning', 'calculation_type': 'fixed', 'value': '300', 'order': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['effective_from'], self.cycle_start.isoformat())
        self.assertTrue(AuditLog.objects.filter(action='salary_component_created', module='payroll').exists())
        # Not part of the structure before it takes effect, part of it from then on.
        before = {c.name for c in effective_components(self.structure, self.cycle_start - datetime.timedelta(days=1))}
        after = {c.name for c in effective_components(self.structure, self.cycle_start)}
        self.assertNotIn('Internet', before)
        self.assertIn('Internet', after)

    def test_a_change_cannot_start_before_the_next_pay_cycle(self):
        resp = _api(self.admin).post(self._components_url(), {
            'name': 'Backdated', 'component_type': 'earning', 'calculation_type': 'fixed', 'value': '1',
            'effective_from': (self.cycle_start - datetime.timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    # ── disabling a component ──────────────────────────────────────────────────

    def test_disabling_is_scheduled_warns_the_count_and_keeps_history(self):
        component = self._component()
        self._assign_employee()
        resp = _api(self.admin).put(self._components_url(component.pk), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['affected_employee_count'], 1)

        today = datetime.date.today()
        self.assertIn('Special Pay', {c.name for c in effective_components(self.structure, today)})
        self.assertNotIn('Special Pay', {c.name for c in effective_components(self.structure, self.cycle_start)})
        # The baseline revision (history) is untouched.
        self.assertTrue(SalaryComponentRevision.objects.filter(component=component, effective_from=LONG_AGO).exists())
        entry = AuditLog.objects.get(action='salary_component_updated')
        self.assertTrue(entry.changes['before']['is_active'])
        self.assertFalse(entry.changes['after']['is_active'])

    def test_disabling_does_not_touch_stored_employee_values(self):
        component = self._component()
        config = self._assign_employee()
        config.earnings_override = {component.code: 750}
        config.save(update_fields=['earnings_override'])
        _api(self.admin).put(self._components_url(component.pk), {'is_active': False}, format='json')
        config.refresh_from_db()
        self.assertEqual(config.earnings_override, {component.code: 750})

    def test_re_enabling_flags_a_reset_of_old_overrides(self):
        component = self._component(is_active=False)
        resp = _api(self.admin).put(self._components_url(component.pk), {'is_active': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        revision = SalaryComponentRevision.objects.get(component=component, effective_from=self.cycle_start)
        self.assertTrue(revision.reset_override)

    def test_deactivate_endpoint_schedules_and_audits(self):
        component = self._component()
        resp = _api(self.admin).delete(self._components_url(component.pk))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['effective_from'], self.cycle_start.isoformat())
        self.assertTrue(AuditLog.objects.filter(action='salary_component_deactivated').exists())

    # ── reordering ─────────────────────────────────────────────────────────────

    def test_reorder_applies_from_the_effective_date_and_is_audited(self):
        first = self._component('First Pay', order=10)
        second = self._component('Second Pay', order=20)
        resp = _api(self.admin).post(self._components_url('reorder'), {'component_ids': [str(second.pk), str(first.pk)]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        names_now = [c.name for c in effective_components(self.structure, datetime.date.today())]
        names_later = [c.name for c in effective_components(self.structure, self.cycle_start)]
        self.assertEqual(names_now, ['First Pay', 'Second Pay'])
        self.assertEqual(names_later, ['Second Pay', 'First Pay'])
        self.assertTrue(AuditLog.objects.filter(action='salary_component_reordered').exists())

    def test_reorder_rejects_a_component_from_another_structure(self):
        other = SalaryStructure.objects.create(name='Another structure')
        stray = SalaryComponent.objects.create(
            structure=other, name='Stray', component_type='earning', calculation_type='fixed', value=1,
        )
        resp = _api(self.admin).post(self._components_url('reorder'), {'component_ids': [str(stray.pk)]}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── access ─────────────────────────────────────────────────────────────────

    def test_view_only_users_cannot_change_components(self):
        component = self._component()
        client = _api(self.viewer)
        self.assertEqual(client.put(self._components_url(component.pk), {'is_active': False}, format='json').status_code, 403)
        self.assertEqual(client.post(self._components_url(), {'name': 'x'}, format='json').status_code, 403)
        self.assertEqual(client.post(self._components_url('reorder'), {'component_ids': [str(component.pk)]}, format='json').status_code, 403)


class SalaryStructureAuditTests(TestCase):
    def setUp(self):
        cache.clear()
        admin_role = make_role('structure_audit_admin', permission_codenames=['payroll.view', 'payroll.create', 'payroll.edit', 'payroll.delete'])
        self.admin = make_user('structure-audit@test.com', role=admin_role)
        self.employee = make_user('structure-audit-emp@test.com', employee_id='STR002')

    def test_creating_and_editing_a_structure_is_audited(self):
        client = _api(self.admin)
        created = client.post('/api/payroll/structures/', {'name': 'Audit structure', 'description': 'first'}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        structure_id = created.data['data']['id']
        self.assertTrue(AuditLog.objects.filter(action='salary_structure_created', object_id=structure_id).exists())

        updated = client.put(f'/api/payroll/structures/{structure_id}/', {'description': 'second'}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        entry = AuditLog.objects.get(action='salary_structure_updated', object_id=structure_id)
        self.assertEqual(entry.changes['before']['description'], 'first')
        self.assertEqual(entry.changes['after']['description'], 'second')

    def test_an_edit_that_changes_nothing_is_not_logged(self):
        structure = SalaryStructure.objects.create(name='Quiet structure', description='same')
        _api(self.admin).put(f'/api/payroll/structures/{structure.pk}/', {'description': 'same'}, format='json')
        self.assertFalse(AuditLog.objects.filter(action='salary_structure_updated').exists())

    def test_switching_the_default_is_audited_and_leaves_one_default(self):
        old_default = SalaryStructure.objects.filter(is_default=True).first() or SalaryStructure.objects.create(name='Old default', is_default=True)
        new = SalaryStructure.objects.create(name='New default candidate')
        resp = _api(self.admin).put(f'/api/payroll/structures/{new.pk}/', {'is_default': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(SalaryStructure.objects.filter(is_default=True).count(), 1)
        old_default.refresh_from_db()
        self.assertFalse(old_default.is_default)
        self.assertTrue(AuditLog.objects.filter(action='salary_structure_updated', object_id=str(new.pk)).exists())

    def test_a_structure_in_use_cannot_be_deleted(self):
        structure = SalaryStructure.objects.create(name='In-use structure')
        EmployeeSalaryConfig.objects.create(
            employee=self.employee, annual_ctc=Decimal('600000'), effective_from=datetime.date(2026, 1, 1),
            salary_structure=structure, is_active=True,
        )
        resp = _api(self.admin).delete(f'/api/payroll/structures/{structure.pk}/')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn('1 employee', resp.data['message'])
        structure.refresh_from_db()
        self.assertTrue(structure.is_active)
        self.assertFalse(AuditLog.objects.filter(action='salary_structure_deleted').exists())

    def test_an_unused_structure_is_deactivated_and_audited(self):
        structure = SalaryStructure.objects.create(name='Unused structure')
        resp = _api(self.admin).delete(f'/api/payroll/structures/{structure.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        structure.refresh_from_db()
        self.assertFalse(structure.is_active)
        self.assertTrue(AuditLog.objects.filter(action='salary_structure_deleted', object_id=str(structure.pk)).exists())

    def test_the_default_structure_cannot_be_deleted(self):
        structure = SalaryStructure.objects.create(name='Protected default', is_default=True)
        self.assertEqual(_api(self.admin).delete(f'/api/payroll/structures/{structure.pk}/').status_code, 400)

    def test_allowance_catalogue_changes_are_audited(self):
        client = _api(self.admin)
        created = client.post('/api/payroll/allowances/', {'name': 'Gym Allowance', 'is_taxable': True}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        allowance_id = created.data['data']['id']
        self.assertTrue(AuditLog.objects.filter(action='payroll_allowance_created', object_id=allowance_id).exists())

        updated = client.put(f'/api/payroll/allowances/{allowance_id}/', {'is_active': False}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        entry = AuditLog.objects.get(action='payroll_allowance_updated', object_id=allowance_id)
        self.assertTrue(entry.changes['before']['is_active'])
        self.assertFalse(entry.changes['after']['is_active'])
        self.assertFalse(PayComponent.objects.get(pk=allowance_id).is_active)
