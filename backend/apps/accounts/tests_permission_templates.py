"""
Tests for reusable permission templates (PermissionTemplate) and bulk-
applying one to many positions at once (backend/apps/accounts/views/
permission_templates.py) — the "give the same access to 50 managers
without editing each one" feature.
"""
from __future__ import annotations

from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_permission, make_role, make_user, place_in_seat
from apps.accounts.models import AuditLog, OrgUnit, PermissionTemplate, Placement, Position


def make_vacant_position(title: str) -> Position:
    unit, _ = OrgUnit.objects.get_or_create(name='Template Test Unit')
    return Position.objects.create(org_unit=unit, title=title, grade='L1')


class PermissionTemplateCrudTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('template-admin@test.com', role=make_role('template_admin', permission_codenames=['settings.edit']))
        self.client.force_authenticate(user=self.admin)
        make_permission('employees.view')
        make_permission('leave.approve')

    def test_create_template(self):
        resp = self.client.post(
            reverse('permission-template-list'),
            {'name': 'Manager', 'description': 'Standard manager access', 'can_manage_team': True,
             'codenames': ['employees.view', 'leave.approve']},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['name'], 'Manager')
        self.assertEqual(set(resp.data['data']['permission_codenames']), {'employees.view', 'leave.approve'})
        self.assertTrue(resp.data['data']['can_manage_team'])

    def test_duplicate_name_rejected(self):
        PermissionTemplate.objects.create(name='Manager')
        resp = self.client.post(reverse('permission-template-list'), {'name': 'manager', 'codenames': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_codename_rejected(self):
        resp = self.client.post(reverse('permission-template-list'), {'name': 'Bad', 'codenames': ['not.real']}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_list_returns_all_templates(self):
        PermissionTemplate.objects.create(name='A')
        PermissionTemplate.objects.create(name='B')
        resp = self.client.get(reverse('permission-template-list'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual({t['name'] for t in resp.data['data']}, {'A', 'B'})

    def test_update_template(self):
        template = PermissionTemplate.objects.create(name='HR')
        template.permissions.add(make_permission('employees.view'))
        resp = self.client.put(
            reverse('permission-template-detail', args=[template.id]),
            {'name': 'HR Admin', 'codenames': ['leave.approve']},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['permission_codenames'], ['leave.approve'])

    def test_delete_template(self):
        template = PermissionTemplate.objects.create(name='Temp')
        resp = self.client.delete(reverse('permission-template-detail', args=[template.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(PermissionTemplate.objects.filter(pk=template.id).exists())

    def test_without_settings_edit_403s(self):
        plain = make_user('template-plain@test.com', role=make_role('template_plain'))
        self.client.force_authenticate(user=plain)
        resp = self.client.get(reverse('permission-template-list'))
        self.assertEqual(resp.status_code, 403)


class PermissionTemplateApplyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = make_user('template-apply-admin@test.com', role=make_role('template_apply_admin', permission_codenames=['settings.edit']))
        self.client.force_authenticate(user=self.admin)
        self.template = PermissionTemplate.objects.create(name='Manager', can_manage_team=True)
        self.template.permissions.add(make_permission('employees.view'), make_permission('leave.approve'))

    def test_apply_to_multiple_positions_at_once(self):
        p1 = make_vacant_position('Team Lead A')
        p2 = make_vacant_position('Team Lead B')
        resp = self.client.post(
            reverse('permission-template-apply', args=[self.template.id]),
            {'position_ids': [str(p1.id), str(p2.id)]},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        for position in (p1, p2):
            position.refresh_from_db()
            self.assertTrue(position.can_manage_team)
            codenames = set(position.position_permissions.values_list('permission__codename', flat=True))
            self.assertEqual(codenames, {'employees.view', 'leave.approve'})

    def test_apply_replaces_existing_permissions_not_merges(self):
        position = make_vacant_position('Replace Me')
        from apps.accounts.models import Permission, PositionPermission
        stale = make_permission('payroll.view')
        PositionPermission.objects.create(position=position, permission=stale)
        self.client.post(reverse('permission-template-apply', args=[self.template.id]), {'position_ids': [str(position.id)]}, format='json')
        position.refresh_from_db()
        codenames = set(position.position_permissions.values_list('permission__codename', flat=True))
        self.assertNotIn('payroll.view', codenames)
        self.assertEqual(codenames, {'employees.view', 'leave.approve'})

    def test_apply_forces_relogin_of_current_holder(self):
        position = make_vacant_position('Holder Position')
        holder = make_user('template-holder@test.com')
        Placement.objects.create(position=position, employee=holder, effective_from=date(2000, 1, 1))
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(holder)
        self.client.post(reverse('permission-template-apply', args=[self.template.id]), {'position_ids': [str(position.id)]}, format='json')
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=token['jti']).exists())

    def test_apply_is_audited(self):
        position = make_vacant_position('Audited Position')
        self.client.post(reverse('permission-template-apply', args=[self.template.id]), {'position_ids': [str(position.id)]}, format='json')
        self.assertTrue(AuditLog.objects.filter(action='permission_template_applied', object_id=str(self.template.id)).exists())

    def test_apply_with_unknown_position_404s(self):
        resp = self.client.post(
            reverse('permission-template-apply', args=[self.template.id]),
            {'position_ids': ['00000000-0000-0000-0000-000000000000']},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_apply_with_empty_list_rejected(self):
        resp = self.client.post(reverse('permission-template-apply', args=[self.template.id]), {'position_ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_apply_without_permission_403s(self):
        plain = make_user('template-apply-plain@test.com', role=make_role('template_apply_plain'))
        self.client.force_authenticate(user=plain)
        position = make_vacant_position('No Access Position')
        resp = self.client.post(reverse('permission-template-apply', args=[self.template.id]), {'position_ids': [str(position.id)]}, format='json')
        self.assertEqual(resp.status_code, 403)
