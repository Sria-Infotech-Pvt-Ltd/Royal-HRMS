"""
Regression tests from the Priorities 1–4 local test pass:
default enforcement mode, direct API blocking right after a plan change
(cache invalidation), plan lifecycle actions, legacy plan protection,
public API never blocked by a company's subscription, a registration keeping
the plan it paid for, and no route that can mark a registration paid.
"""
from __future__ import annotations

from datetime import date
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.tenants.models import Client, CompanyRegistration, CompanySubscription, SubscriptionPlan
from apps.tenants.subscriptions import resolve_modules
from apps.tenants.tests_company_system_admin import _login_platform_admin, _make_platform_admin
from apps.tenants.tests_registrations import FORM
from config.test_runner import TEST_COMPANY_CODE


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.company = Client.objects.get(company_code=TEST_COMPANY_CODE)
        self.pa_admin = _make_platform_admin('regr.admin@test.com')
        self.pa = APIClient()
        _login_platform_admin(self.pa, 'regr.admin@test.com')

    def tenant_client(self, perms):
        role = make_role(f'regr_{len(perms)}', permission_codenames=perms)
        user = make_user(f'regr{len(perms)}@test.com', role=role, full_name='Regr User')
        c = APIClient()
        resp = c.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                         'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return c


class EnforcementDefaultsAndApiTests(Base):
    def test_default_mode_is_off(self):
        self.assertEqual(settings.SUBSCRIPTION_ENFORCEMENT, 'off')
        self.assertFalse(settings.SUBSCRIPTION_ALLOW_OVERRIDES)
        self.assertEqual(settings.PAYMENT_GATEWAY, '')

    def test_plan_change_blocks_module_api_immediately(self):
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=resolve_modules(['payroll']))
        cache.clear()
        c = self.tenant_client(['payroll.view'])
        self.assertEqual(c.get('/api/payroll/settings/').status_code, 200)
        starter = SubscriptionPlan.objects.get(code='starter')
        resp = self.pa.post(reverse('saas-subscription-list'), {
            'client': str(self.company.pk), 'plan': str(starter.pk), 'starts_on': '2026-11-03'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(c.get('/api/payroll/settings/').status_code, 200)   # unpaid: nothing applied yet
        resp = self.pa.post(reverse('saas-subscription-waiver', kwargs={'client_id': str(self.company.pk)}),
                            {'waive': True, 'reason': 'Regression test'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # Same session, no re-login: the cached company was invalidated, so the
        # module gate already sees Starter (no payroll). Enforced regardless of mode.
        blocked = c.get('/api/payroll/settings/')
        self.assertEqual(blocked.status_code, 403)
        self.assertIn('not enabled for your company', blocked.json()['message'])

    def test_public_api_not_blocked_by_inactive_subscription(self):
        starter = SubscriptionPlan.objects.get(code='starter')
        self.pa.post(reverse('saas-subscription-list'), {
            'client': str(self.company.pk), 'plan': str(starter.pk), 'starts_on': '2026-11-03'}, format='json')
        CompanySubscription.objects.filter(client=self.company).update(status='inactive')
        c = self.tenant_client(['employees.view'])                  # signed in to the inactive company
        with override_settings(SUBSCRIPTION_ENFORCEMENT='on'):
            self.assertEqual(c.get('/api/employees/').status_code, 403)
            self.assertEqual(c.get(reverse('public-plans')).status_code, 200)


class PlanLifecycleTests(Base):
    def test_activate_publish_unpublish_deactivate(self):
        plan = self.pa.post(reverse('saas-plan-list'), {'code': 'lite', 'name': 'Lite', 'features': ['leave'],
                                                         'price_per_employee': '29'}, format='json').data['data']
        url = reverse('saas-plan-detail', kwargs={'pk': plan['id']})
        self.assertEqual(plan['status'], 'draft')
        self.assertEqual(self.pa.patch(url, {'is_public': True}, format='json').status_code, 400)   # draft
        self.assertEqual(self.pa.patch(url, {'status': 'active'}, format='json').data['data']['status'], 'active')
        self.assertTrue(self.pa.patch(url, {'is_public': True}, format='json').data['data']['is_public'])
        self.assertIn('lite', [p['code'] for p in APIClient().get(reverse('public-plans')).data['data']])
        self.assertFalse(self.pa.patch(url, {'is_public': False}, format='json').data['data']['is_public'])
        self.assertNotIn('lite', [p['code'] for p in APIClient().get(reverse('public-plans')).data['data']])
        resp = self.pa.patch(url, {'status': 'inactive'}, format='json')
        self.assertEqual(resp.data['data']['status'], 'inactive')
        bad = self.pa.patch(url, {'billing_periods': ['weekly']}, format='json')
        self.assertEqual(bad.status_code, 400)

    def test_legacy_plan_features_fixed(self):
        from apps.tenants.management.commands.assign_legacy_subscriptions import legacy_plan
        plan = legacy_plan(create=True)
        url = reverse('saas-plan-detail', kwargs={'pk': plan.pk})
        self.assertEqual(self.pa.patch(url, {'features': ['leave']}, format='json').status_code, 400)
        self.assertEqual(self.pa.patch(url, {'status': 'active'}, format='json').status_code, 400)
        # Not assignable by hand either.
        resp = self.pa.post(reverse('saas-subscription-list'), {
            'client': str(self.company.pk), 'plan': str(plan.pk), 'starts_on': '2026-11-03'}, format='json')
        self.assertEqual(resp.status_code, 400)


class RegistrationSafeguardTests(Base):
    def setUp(self):
        super().setUp()
        SubscriptionPlan.objects.filter(code='growth').update(is_public=True)
        resp = APIClient().post(reverse('public-registration'), FORM, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.reg = CompanyRegistration.objects.get(reference=resp.data['data']['reference'])

    def test_no_route_marks_payment_paid(self):
        url = reverse('saas-registration-detail', kwargs={'pk': self.reg.pk})
        for method in ('put', 'patch', 'post'):
            resp = getattr(self.pa, method)(url, {'payment_status': 'paid'}, format='json')
            self.assertEqual(resp.status_code, 405, method)
        public = reverse('public-registration-status', kwargs={'reference': self.reg.reference})
        self.assertEqual(APIClient().post(public, {'payment_status': 'paid'}, format='json').status_code, 405)
        # Submitting the form with payment fields set doesn't make it paid either.
        resp = APIClient().post(reverse('public-registration'), {**FORM, 'company_code': 'ACMEX',
                                                                 'payment_status': 'paid'}, format='json')
        self.assertEqual(CompanyRegistration.objects.get(reference=resp.data['data']['reference']).payment_status,
                         'pending')
        self.reg.refresh_from_db()
        self.assertEqual(self.reg.payment_status, 'pending')
        with mock.patch('apps.tenants.views_saas.finish_provisioning_task.delay') as delay:
            resp = self.pa.post(reverse('saas-registration-approve', kwargs={'pk': self.reg.pk}), {}, format='json')
        self.assertEqual(resp.status_code, 400)
        delay.assert_not_called()

    def test_registration_keeps_paid_features_when_plan_edited(self):
        growth = SubscriptionPlan.objects.get(code='growth')
        self.assertIn('payroll', self.reg.plan_features)
        growth.features = [f for f in growth.features if f != 'payroll']
        growth.save()
        # The review screen (and approval, which uses the same snapshot) still
        # shows the modules the customer registered for.
        data = self.pa.get(reverse('saas-registration-detail', kwargs={'pk': self.reg.pk})).data['data']
        self.assertIn('payroll', data['modules'])
        self.reg.refresh_from_db()
        self.assertIn('payroll', self.reg.plan_features)


class ApplyWithoutSchemaTests(Base):
    """apply_subscription must never create a company schema (that's the
    background provisioning task's job) — found in the local integration run."""

    def test_pending_company_without_schema_is_not_provisioned_by_plan_change(self):
        from django_tenants.utils import schema_context

        from apps.tenants.subscriptions import assign_subscription
        pending = Client(schema_name='tenant_noschema', company_code='NOSCHEMA', company_name='No Schema',
                         provisioning_status=Client.PROVISIONING_PENDING, enabled_modules=[])
        pending.auto_create_schema = False
        with schema_context('public'):
            pending.save()
        fresh = Client.objects.get(pk=pending.pk)            # reloaded: auto_create_schema back to default
        starter = SubscriptionPlan.objects.get(code='starter')
        with mock.patch.object(Client, 'create_schema') as create_schema:
            assign_subscription(client=fresh, plan=starter, starts_on=date(2026, 11, 3), ends_on=None,
                                employee_count=None, source='manual')
        create_schema.assert_not_called()
        fresh.refresh_from_db()
        self.assertEqual(sorted(fresh.enabled_modules), resolve_modules(starter.features))

    def test_cache_invalidated_after_apply(self):
        from core.cache_service import TenantClientCacheService
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=['leave'])
        cache.clear()
        self.assertEqual(TenantClientCacheService.get(self.company.schema_name).enabled_modules, ['leave'])
        growth = SubscriptionPlan.objects.get(code='growth')
        self.pa.post(reverse('saas-subscription-list'), {
            'client': str(self.company.pk), 'plan': str(growth.pk), 'starts_on': '2026-11-03',
            'waive_reason': 'Regression test'}, format='json')
        self.assertEqual(sorted(TenantClientCacheService.get(self.company.schema_name).enabled_modules),
                         resolve_modules(growth.features))
