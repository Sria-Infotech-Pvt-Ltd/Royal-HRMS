"""
SaaS plans, subscriptions and module access.

Plans (catalogue validation, seeded plans, edits never touch subscriptions),
manual assignment (existing company / new company through the existing
provisioning), change plan with module-difference preview, period, status,
history + audit, provisioning retry, the legacy backfill command, and
SUBSCRIPTION_ENFORCEMENT (off / shadow / on) for the late-gated modules,
inactive subscriptions and the employee limit. Plus the login / token
module list used by the frontend.
"""
from __future__ import annotations

import datetime
import io
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.factories import make_role, make_user
from apps.tenants.models import (
    ALL_MODULES, Client, CompanySubscription, PlatformAdminAuditLog, SubscriptionHistory, SubscriptionPlan,
)
from apps.tenants.modules import resolve_modules, validate_features
from apps.tenants.tests_company_system_admin import _login_platform_admin, _make_platform_admin
from config.test_runner import TEST_COMPANY_CODE

TODAY = datetime.date(2026, 11, 3)


class SaasFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)                 # cached Client rows must not outlive a test
        self.company = Client.objects.get(company_code=TEST_COMPANY_CODE)
        self.original_modules = list(self.company.enabled_modules or [])
        _make_platform_admin('saas.admin@test.com')
        self.pa = APIClient()
        _login_platform_admin(self.pa, 'saas.admin@test.com')
        self.starter = SubscriptionPlan.objects.get(code='starter')
        self.growth = SubscriptionPlan.objects.get(code='growth')

    def assign(self, plan=None, **extra):
        body = {'client': str(self.company.pk), 'plan': str((plan or self.starter).pk),
                'starts_on': TODAY.isoformat(), **extra}
        return self.pa.post(reverse('saas-subscription-list'), body, format='json')

    def settle(self, client=None, amount='1000.00'):
        """Pay in full the way an admin would: amount due, then a confirmed payment."""
        client_id = str((client or self.company).pk)
        self.pa.post(reverse('saas-subscription-amount-due', kwargs={'client_id': client_id}),
                     {'amount_due': amount}, format='json')
        resp = self.pa.post(reverse('saas-subscription-payments', kwargs={'client_id': client_id}), {
            'amount': amount, 'method': 'upi', 'paid_on': TODAY.isoformat(), 'confirm': True}, format='multipart')
        assert resp.status_code == 201, resp.data
        return resp


class CatalogueAndPlanTests(SaasFixture):
    def test_dependencies_and_feature_rules(self):
        self.assertEqual(resolve_modules(['payroll']), ['attendance', 'leave', 'payroll'])
        self.assertEqual(resolve_modules(['face_attendance', 'mobile_access']), ['attendance', 'face_attendance'])
        _, errors = validate_features(['tds', 'employee_management', 'nope'])
        self.assertEqual(len(errors), 3)

    def test_seeded_plans_are_active_not_public(self):
        plans = {p.code: p for p in SubscriptionPlan.objects.filter(code__in=['starter', 'growth', 'business'])}
        self.assertEqual({p.status for p in plans.values()}, {'active'})
        self.assertFalse(any(p.is_public for p in plans.values()))
        self.assertIn('payroll', plans['growth'].features)
        self.assertNotIn('payroll', plans['starter'].features)
        self.assertNotIn('tds', plans['growth'].features)                      # not built → not sold

    def test_create_plan_validation_and_audit(self):
        url = reverse('saas-plan-list')
        bad = self.pa.post(url, {'code': 'x1', 'name': 'X', 'features': ['training']}, format='json')
        self.assertEqual(bad.status_code, 400)
        bad = self.pa.post(url, {'code': 'x1', 'name': 'X', 'status': 'draft', 'is_public': True}, format='json')
        self.assertEqual(bad.status_code, 400)                                 # only active plans can be published
        resp = self.pa.post(url, {'code': 'Enterprise', 'name': 'Enterprise', 'price_per_employee': '199',
                                  'features': ['payroll', 'priority_support'], 'billing_periods': ['monthly', 'yearly'],
                                  'status': 'active', 'is_public': True}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['code'], 'enterprise')
        self.assertEqual(resp.data['data']['modules'], ['attendance', 'leave', 'payroll'])
        self.assertTrue(PlatformAdminAuditLog.objects.filter(action='saas_plan_created').exists())

    def test_editing_plan_never_changes_existing_subscription(self):
        self.assertEqual(self.assign().status_code, 201)
        self.settle()
        url = reverse('saas-plan-detail', kwargs={'pk': self.starter.pk})
        resp = self.pa.patch(url, {'features': self.starter.features + ['assets'], 'price_per_employee': '59'},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        sub = CompanySubscription.objects.get(client=self.company)
        self.assertNotIn('assets', sub.plan_features)
        self.assertEqual(str(sub.price_per_employee), '49.00')
        self.company.refresh_from_db()
        self.assertNotIn('assets', self.company.enabled_modules)
        log = PlatformAdminAuditLog.objects.get(action='saas_plan_updated')
        self.assertEqual(log.changes['price_per_employee'], {'from': '49.00', 'to': '59.00'})

    def test_plan_currency(self):
        url = reverse('saas-plan-list')
        base = {'name': 'Cur', 'price_per_employee': '49', 'features': ['leave'], 'status': 'active'}
        inr = self.pa.post(url, {**base, 'code': 'cur-inr'}, format='json')
        self.assertEqual((inr.status_code, inr.data['data']['currency']), (201, 'INR'))      # default
        usd = self.pa.post(url, {**base, 'code': 'cur-usd', 'currency': 'usd '}, format='json')
        self.assertEqual((usd.status_code, usd.data['data']['currency']), (201, 'USD'))      # ISO code stored
        for bad in ('XYZ', '$', 'RUPEE', ''):
            self.assertEqual(self.pa.post(url, {**base, 'code': 'cur-bad', 'currency': bad}, format='json').status_code,
                             400, bad)
        self.assertFalse(SubscriptionPlan.objects.filter(code='cur-bad').exists())

    def test_editing_plan_currency_keeps_subscription_snapshot(self):
        self.assertEqual(self.assign().status_code, 201)
        url = reverse('saas-plan-detail', kwargs={'pk': self.starter.pk})
        self.assertEqual(self.pa.patch(url, {'price_per_employee': '55'}, format='json').data['data']['currency'], 'INR')
        self.assertEqual(self.pa.patch(url, {'currency': 'EUR'}, format='json').status_code, 200)
        sub = CompanySubscription.objects.get(client=self.company)
        self.assertEqual((sub.currency, str(sub.price_per_employee)), ('INR', '49.00'))      # snapshot untouched
        # A plan already stored with an unlisted code can still be edited without changing it.
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(currency='JPY')
        resp = self.pa.patch(reverse('saas-plan-detail', kwargs={'pk': self.growth.pk}),
                             {'currency': 'JPY', 'price_per_employee': '100'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_code_locked_once_in_use(self):
        self.assign()
        resp = self.pa.patch(reverse('saas-plan-detail', kwargs={'pk': self.starter.pk}), {'code': 'basic'},
                             format='json')
        self.assertEqual(resp.status_code, 400)

    def test_requires_platform_admin(self):
        self.assertIn(APIClient().get(reverse('saas-plan-list')).status_code, (401, 403))


class AssignmentTests(SaasFixture):
    def test_preview_then_assign_existing_company(self):
        preview = self.assign(dry_run=True)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['data']['modules'], resolve_modules(self.starter.features))
        self.assertFalse(CompanySubscription.objects.filter(client=self.company).exists())

        resp = self.assign(employee_count=25)
        self.assertEqual(resp.status_code, 201, resp.data)
        sub = CompanySubscription.objects.get(client=self.company)
        self.assertEqual((sub.source, sub.plan_name, sub.employee_count), ('manual', 'Starter', 25))
        # Assignment alone is never payment: nothing applied yet.
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('pending', 'awaiting_payment'))
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), sorted(self.original_modules))
        hist = SubscriptionHistory.objects.get(subscription=sub)
        self.assertEqual(hist.before['modules_before'], sorted(self.original_modules))
        self.settle()
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), resolve_modules(self.starter.features))
        sub.refresh_from_db()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('paid', 'success'))
        self.assertTrue(PlatformAdminAuditLog.objects.filter(action='saas_subscription_assigned').exists())
        self.assertEqual(self.assign().status_code, 400)                       # one subscription per company

    def test_inactive_plan_and_bad_dates_refused(self):
        draft = SubscriptionPlan.objects.create(code='draft1', name='Draft', status='draft', features=['leave'])
        self.assertEqual(self.assign(plan=draft).status_code, 400)
        self.assertEqual(self.assign(ends_on='2026-01-01').status_code, 400)

    def test_new_company_uses_existing_provisioning(self):
        with mock.patch('apps.tenants.tasks.finish_provisioning_task.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.pa.post(reverse('saas-subscription-list'), {
                    'new_company': {'company_code': 'NEWCO1', 'company_name': 'New Co',
                                    'admin_email': 'admin@newco.test'},
                    'plan': str(self.growth.pk), 'starts_on': TODAY.isoformat(), 'employee_count': 40,
                }, format='json')
            self.assertEqual(resp.status_code, 202, resp.data)
            client = Client.objects.get(company_code='NEWCO1')
            self.assertEqual(client.provisioning_status, Client.PROVISIONING_AWAITING_PAYMENT)
            delay.assert_not_called()                                         # nothing set up before payment
            with self.captureOnCommitCallbacks(execute=True):
                self.settle(client)
            client.refresh_from_db()
            self.assertEqual(client.provisioning_status, Client.PROVISIONING_PENDING)
            delay.assert_called_once_with(str(client.pk), 'admin@newco.test', resolve_modules(self.growth.features))
        self.assertEqual(client.subscription.source, 'manual')
        with mock.patch('apps.tenants.tasks.finish_provisioning_task.delay'):
            dup = self.pa.post(reverse('saas-subscription-list'), {
                'new_company': {'company_code': 'newco1', 'company_name': 'Again', 'admin_email': 'a@b.test'},
                'plan': str(self.growth.pk), 'starts_on': TODAY.isoformat(),
            }, format='json')
        self.assertEqual(dup.status_code, 400)                                 # no duplicate tenant

    def test_overrides_off_by_default(self):
        from apps.tenants.subscriptions import SubscriptionError, check_overrides
        with self.assertRaises(SubscriptionError):
            check_overrides(['assets'], [])


class ManageSubscriptionTests(SaasFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.assign().status_code, 201)
        self.base = f'/api/platform-admin/saas/subscriptions/{self.company.pk}/'

    def test_change_plan_preview_and_apply(self):
        preview = self.pa.post(self.base + 'change-plan/', {'plan': str(self.growth.pk), 'dry_run': True}, format='json')
        self.assertIn('payroll', preview.data['data']['difference']['added'])
        self.assertEqual(CompanySubscription.objects.get(client=self.company).plan_name, 'Starter')
        resp = self.pa.post(self.base + 'change-plan/', {'plan': str(self.growth.pk)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.company.refresh_from_db()
        self.assertIn('payroll', self.company.enabled_modules)
        self.assertTrue(SubscriptionHistory.objects.filter(event='plan_changed').exists())

    def test_period_and_status(self):
        self.assertEqual(self.pa.post(self.base + 'period/', {'ends_on': '2027-11-02'}, format='json').status_code, 200)
        self.assertEqual(self.pa.post(self.base + 'period/', {'ends_on': '2020-01-01'}, format='json').status_code, 400)
        self.assertEqual(self.pa.post(self.base + 'status/', {'active': False}, format='json').status_code, 200)
        sub = CompanySubscription.objects.get(client=self.company)
        self.assertEqual((sub.ends_on, sub.status), (datetime.date(2027, 11, 2), 'inactive'))
        events = list(SubscriptionHistory.objects.filter(subscription=sub).values_list('event', flat=True))
        self.assertTrue({'assigned', 'extended', 'deactivated'} <= set(events))
        detail = self.pa.get(self.base)
        self.assertEqual(len(detail.data['data']['history']), 3)

    def test_dashboard_and_list(self):
        data = self.pa.get(reverse('saas-dashboard')).data['data']
        self.assertGreaterEqual(data['subscriptions_active'], 1)
        rows = self.pa.get(reverse('saas-subscription-list'), {'search': TEST_COMPANY_CODE}).data['data']['results']
        self.assertEqual(rows[0]['subscription']['plan_code'], 'starter')


class RetryProvisioningTests(SaasFixture):
    def test_only_failed_companies(self):
        url = reverse('platform-admin-company-retry-provisioning', kwargs={'pk': self.company.pk})
        self.assertEqual(self.pa.post(url, {'admin_email': 'a@b.test'}, format='json').status_code, 400)
        failed = Client(schema_name='tenant_failco', company_code='FAILCO', company_name='Fail Co',
                        provisioning_status=Client.PROVISIONING_FAILED)
        failed.auto_create_schema = False
        from django_tenants.utils import schema_context
        with schema_context('public'):                     # registry rows are created on public
            failed.save()
        url = reverse('platform-admin-company-retry-provisioning', kwargs={'pk': failed.pk})
        with mock.patch('apps.tenants.views_saas.retry_provisioning_task.delay') as delay:
            resp = self.pa.post(url, {'admin_email': 'admin@fail.test'}, format='json')
            again = self.pa.post(url, {'admin_email': 'admin@fail.test'}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertEqual(again.status_code, 400)                                # already claimed
        delay.assert_called_once_with(str(failed.pk), 'admin@fail.test')
        failed.refresh_from_db()
        self.assertEqual(failed.provisioning_status, Client.PROVISIONING_PENDING)


class LegacyBackfillTests(SaasFixture):
    def run_cmd(self, *args):
        out = io.StringIO()
        call_command('assign_legacy_subscriptions', *args, stdout=out)
        return out.getvalue()

    def test_preview_writes_nothing_then_apply_keeps_modules(self):
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=['attendance', 'leave', 'payroll'])
        out = self.run_cmd()
        self.assertIn('PREVIEW ONLY', out)
        self.assertFalse(CompanySubscription.objects.filter(client=self.company).exists())
        self.run_cmd('--apply')
        self.company.refresh_from_db()
        # Kept exactly + the previously ungated modules; nothing it had switched off came on.
        self.assertEqual(sorted(self.company.enabled_modules),
                         ['assets', 'attendance', 'documents', 'leave', 'payroll', 'wfh'])
        sub = self.company.subscription
        self.assertEqual((sub.source, sub.plan.code, sub.ends_on), ('legacy', 'legacy', None))
        self.assertIn('Every company already has', self.run_cmd('--apply'))

    def test_full_company_gets_everything(self):
        Client.objects.filter(pk=self.company.pk).update(
            enabled_modules=[m for m in ALL_MODULES if m not in ('documents', 'assets', 'wfh')])
        self.run_cmd('--apply')
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), sorted(ALL_MODULES))


class EnforcementTests(SaasFixture):
    def setUp(self):
        super().setUp()
        role = make_role('saas_tenant_hr', permission_codenames=['documents.view', 'employees.view',
                                                                  'employees.create'])
        self.hr = make_user('saas.hr@test.com', role=role, full_name='Saas HR')
        Client.objects.filter(pk=self.company.pk).update(
            enabled_modules=[m for m in self.original_modules if m != 'documents'])
        cache.clear()

    def tenant_client(self):
        c = APIClient()
        resp = c.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': self.hr.email,
                                         'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return c, resp

    def test_late_gated_module_by_mode(self):
        c, _ = self.tenant_client()
        for mode, expected in (('off', 200), ('shadow', 200), ('on', 403)):
            with override_settings(SUBSCRIPTION_ENFORCEMENT=mode):
                self.assertEqual(c.get('/api/documents/').status_code, expected, mode)

    def test_inactive_subscription_blocks_only_when_on(self):
        self.assign()
        CompanySubscription.objects.filter(client=self.company).update(status='inactive')
        c, _ = self.tenant_client()
        with override_settings(SUBSCRIPTION_ENFORCEMENT='off'):
            self.assertEqual(c.get('/api/employees/').status_code, 200)
        with override_settings(SUBSCRIPTION_ENFORCEMENT='on'):
            resp = c.get('/api/employees/')
            self.assertEqual(resp.status_code, 403)
            self.assertIn('subscription is inactive', resp.json()['message'])
            self.tenant_client()                                               # login still works

    def test_login_and_token_carry_modules(self):
        enabled = sorted(m for m in self.original_modules if m != 'documents')
        for mode, expected in (
            # Until enforcement is on, documents / assets / wfh stay visible (API doesn't gate them yet).
            ('off', sorted(set(enabled) | {'documents', 'assets', 'wfh'})),
            ('on', enabled),
        ):
            with override_settings(SUBSCRIPTION_ENFORCEMENT=mode):
                _, resp = self.tenant_client()
                self.assertEqual(resp.data['data']['user']['enabled_modules'], expected, mode)
                token = AccessToken(resp.cookies['royal_access_token'].value)
                self.assertEqual(token['modules'], expected, mode)

    def test_employee_limit_only_when_on(self):
        self.assign()
        CompanySubscription.objects.filter(client=self.company).update(max_employees=1)
        c, _ = self.tenant_client()
        body = {'first_name': 'Limit', 'last_name': 'Test', 'email': 'limit.test@test.com'}
        with override_settings(SUBSCRIPTION_ENFORCEMENT='on'):
            resp = c.post('/api/employees/', body, format='json')
            self.assertEqual(resp.status_code, 403)
            self.assertIn('allows up to 1', resp.json()['message'])
