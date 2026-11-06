"""
Regression tests for three production subscription issues:
1. Asset Management reachable on plans without it (Starter, Growth,
   a custom "Enterprise" plan without assets) — every assets API blocked,
   and allowed on a plan that includes it.
2. Changing plan kept the old amount due — it is now recalculated from the
   new plan (price × employees × period, GST), shown in the preview, and the
   payment status follows.
3. Plan edits vs company access — snapshot rule kept, the subscription says
   when its plan was edited, "apply latest" re-applies it, the company row
   shows the effective modules, and modules can't be edited around the plan.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.urls import reverse

from apps.tenants.models import CompanySubscription, SubscriptionHistory, SubscriptionPlan
from apps.tenants.modules import resolve_modules
from apps.tenants.tests_saas import TODAY
from apps.tenants.tests_saas_access import AccessBase

ASSET_APIS = [
    ('get', '/api/assets/'), ('post', '/api/assets/'), ('get', '/api/assets/categories/'),
    ('post', '/api/assets/import/'), ('post', f'/api/assets/employees/{uuid.uuid4()}/assign/'),
    ('post', '/api/assets/assignments/import/'),
]


class PlanFixtures(AccessBase):
    def setUp(self):
        super().setUp()
        base = {'status': 'active', 'gst_rate': Decimal('18'), 'billing_periods': ['monthly', 'yearly']}
        self.ent_no_assets = SubscriptionPlan.objects.create(
            code='enterprise', name='Enterprise', price_per_employee=Decimal('149'),
            features=['payroll', 'expenses', 'recruitment', 'documents', 'wfh', 'announcements'], **base)
        self.ent_assets = SubscriptionPlan.objects.create(
            code='enterprise-assets', name='Enterprise + Assets', price_per_employee=Decimal('159'),
            features=['payroll', 'assets', 'documents'], **base)

    def asset_api_blocked(self):
        out = {}
        for method, path in ASSET_APIS:
            resp = getattr(self.web, method)(path, {}, format='json') if method == 'post' else self.web.get(path)
            out[f'{method.upper()} {path}'] = (resp.status_code == 403 and 'is not enabled for your company'
                                               in resp.json().get('message', ''))
        return out

    def sub(self):
        return CompanySubscription.objects.get(client=self.company)

    def url(self, name):
        return reverse(name, kwargs={'client_id': str(self.company.pk)})


class AssetRestrictionTests(PlanFixtures):
    def check_plan(self, plan, assets_allowed: bool):
        self.put_on(plan)
        blocked = self.asset_api_blocked()
        if assets_allowed:
            self.assertFalse(any(blocked.values()), blocked)
            self.assertIn('assets', self.login_modules())
        else:
            self.assertTrue(all(blocked.values()), blocked)          # incl. add, bulk assign, bulk import
            self.assertNotIn('assets', self.login_modules())
            self.assertNotIn('assets', self.token_modules())

    def test_starter_without_assets(self):
        self.check_plan(self.starter, False)

    def test_growth_without_assets(self):
        self.check_plan(self.growth, False)

    def test_enterprise_without_assets(self):
        self.check_plan(self.ent_no_assets, False)

    def test_enterprise_with_assets(self):
        self.check_plan(self.ent_assets, True)

    def test_enterprise_to_starter_removes_enterprise_modules(self):
        self.put_on(self.ent_assets)
        self.assertFalse(self.blocked('/api/payroll/settings/'))
        self.put_on(self.starter, change=True)
        self.assertTrue(self.blocked('/api/payroll/settings/'))
        self.assertTrue(all(self.asset_api_blocked().values()))
        self.assertEqual(self.login_modules(), resolve_modules(self.starter.features))


class UpgradePricingTests(PlanFixtures):
    def setUp(self):
        super().setUp()
        # Starter, 10 employees, monthly: 49 × 10 = 490 + 18% GST = 578.20 — paid in full.
        self.assertEqual(self.assign(employee_count=10, billing_period='monthly', amount_due='578.20').status_code, 201)
        pay = self.pa.post(self.url('saas-subscription-payments'), {
            'amount': '578.20', 'method': 'upi', 'paid_on': TODAY.isoformat(), 'confirm': True}, format='multipart')
        self.assertEqual(pay.status_code, 201, pay.data)
        self.assertEqual(self.sub().payment_status, 'paid')

    def change(self, plan, dry_run=False, **extra):
        return self.pa.post(self.url('saas-subscription-change-plan'),
                            {'plan': str(plan.pk), **({'dry_run': True} if dry_run else {}), **extra}, format='json')

    def test_preview_shows_old_and_new_amounts(self):
        data = self.change(self.ent_no_assets, dry_run=True).data['data']
        p = data['pricing']
        self.assertEqual((p['employee_count'], p['billing_period']), (10, 'monthly'))
        self.assertEqual((p['from']['plan'], p['from']['amount_due']), ('Starter', '578.20'))
        self.assertEqual((p['to']['plan'], p['to']['price_per_employee'], p['to']['subtotal'], p['to']['gst_amount'],
                          p['to']['amount_due']), ('Enterprise', '149.00', '1490.00', '268.20', '1758.20'))
        self.assertEqual(self.sub().plan_name, 'Starter')            # preview saves nothing

    def test_upgrade_recalculates_and_saves(self):
        resp = self.change(self.ent_no_assets)
        self.assertEqual(resp.status_code, 200, resp.data)
        sub = self.sub()
        self.assertEqual((sub.plan_name, str(sub.price_per_employee), str(sub.amount_due)),
                         ('Enterprise', '149.00', '1758.20'))
        self.assertEqual(sub.payment_status, 'partially_paid')        # 578.20 of 1758.20 received
        self.assertEqual(sorted(self.company.__class__.objects.get(pk=self.company.pk).enabled_modules),
                         resolve_modules(self.ent_no_assets.features))
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=sub, event='amount_due_changed').exists())

    def test_downgrade_and_yearly(self):
        self.change(self.ent_no_assets)
        self.change(self.starter)
        sub = self.sub()
        self.assertEqual((str(sub.amount_due), sub.payment_status), ('578.20', 'paid'))
        CompanySubscription.objects.filter(pk=sub.pk).update(billing_period='yearly')
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(billing_periods=['monthly'])
        refused = self.change(SubscriptionPlan.objects.get(pk=self.growth.pk))   # not offered yearly
        self.assertEqual(refused.status_code, 400)
        self.assertIn('billing_period', refused.data['data'])
        self.assertEqual(self.change(self.ent_no_assets).status_code, 200)       # 149 × 10 × 12 = 17880 + 18%
        self.assertEqual(str(self.sub().amount_due), '21098.40')

    def test_gst_inclusive_plan(self):
        SubscriptionPlan.objects.filter(pk=self.ent_no_assets.pk).update(gst_inclusive=True)
        p = self.change(SubscriptionPlan.objects.get(pk=self.ent_no_assets.pk), dry_run=True).data['data']['pricing']
        self.assertEqual((p['to']['subtotal'], p['to']['amount_due'], p['to']['gst_amount']),
                         ('1490.00', '1490.00', '227.29'))

    def test_employee_count_must_fit_new_plan(self):
        SubscriptionPlan.objects.filter(pk=self.ent_no_assets.pk).update(min_employees=50)
        resp = self.change(SubscriptionPlan.objects.get(pk=self.ent_no_assets.pk), dry_run=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('employee_count', resp.data['data'])


class PlanEditSnapshotTests(PlanFixtures):
    def test_edit_keeps_snapshot_then_apply_latest(self):
        self.assertEqual(self.assign(plan=self.ent_no_assets, employee_count=5, waive_reason='test').status_code, 201)
        self.assertFalse(self.sub().plan_outdated if hasattr(self.sub(), 'plan_outdated') else False)
        edit = self.pa.patch(reverse('saas-plan-detail', kwargs={'pk': self.ent_no_assets.pk}),
                             {'features': self.ent_no_assets.features + ['assets'], 'price_per_employee': '169'},
                             format='json')
        self.assertEqual(edit.status_code, 200, edit.data)
        detail = self.pa.get(reverse('saas-subscription-detail', kwargs={'client_id': str(self.company.pk)})).data['data']
        sub = detail['company']['subscription']
        self.assertTrue(sub['plan_outdated'])                         # company keeps its terms…
        self.assertNotIn('assets', sub['modules'])
        self.assertIn('assets', sub['latest_plan']['modules'])        # …and is told what changed
        self.assertTrue(all(self.asset_api_blocked().values()))
        apply = self.pa.post(self.url('saas-subscription-change-plan'), {'plan': str(self.ent_no_assets.pk)}, format='json')
        self.assertEqual(apply.status_code, 200, apply.data)
        self.assertFalse(apply.data['data']['plan_outdated'])
        self.assertEqual(str(self.sub().price_per_employee), '169.00')
        self.assertFalse(any(self.asset_api_blocked().values()))       # assets now applied

    def test_company_row_shows_effective_modules(self):
        self.put_on(self.starter)
        rows = self.pa.get(reverse('saas-subscription-list')).data['data']['results']
        row = next(r for r in rows if r['id'] == str(self.company.pk))
        self.assertEqual(row['effective_modules'], self.login_modules())

    def test_modules_cannot_be_edited_around_the_plan(self):
        url = reverse('platform-admin-company-detail', kwargs={'pk': str(self.company.pk)})
        self.assertEqual(self.pa.patch(url, {'enabled_modules': ['leave']}, format='json').status_code, 200)  # no plan yet
        self.put_on(self.starter)
        resp = self.pa.patch(url, {'enabled_modules': ['leave', 'assets']}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('assets', self.login_modules())
