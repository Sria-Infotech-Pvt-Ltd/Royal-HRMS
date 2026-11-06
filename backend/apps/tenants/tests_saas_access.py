"""
Subscription-based module access, end to end: a company sees and can use
only its plan's modules — login / token module list, the API gate (incl. the
documents / assets / wfh "late" modules once a plan is applied), the
dashboards' data, notifications — and upgrades / downgrades take effect
immediately. A company without a plan (legacy) keeps its current behaviour.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.factories import make_role, make_user
from apps.tenants.models import ALL_MODULES, Client, CompanySubscription
from apps.tenants.modules import resolve_modules
from apps.tenants.tests_saas import TODAY, SaasFixture
from config.test_runner import TEST_COMPANY_CODE

NOT_ENABLED = 'is not enabled for your company'
ALL_PERMS = ['employees.view', 'settings.edit', 'recruitment.view', 'payroll.view', 'leave.view', 'expenses.view',
             'attendance.create', 'assets.view', 'documents.view', 'wfh.view', 'announcements.view']


class AccessBase(SaasFixture):
    def setUp(self):
        super().setUp()
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=list(ALL_MODULES))
        cache.clear()
        role = make_role('access_hr', permission_codenames=ALL_PERMS, can_manage_team=True)
        self.user = make_user('access.hr@test.com', role=role, full_name='Access HR')
        self.web = APIClient()
        self.login_resp = self.login()

    def login(self):
        resp = self.web.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': self.user.email,
                                                'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def put_on(self, plan, change=False):
        """Assign (or change to) `plan` and settle payment so it is applied."""
        if change:
            resp = self.pa.post(reverse('saas-subscription-change-plan', kwargs={'client_id': str(self.company.pk)}),
                                {'plan': str(plan.pk)}, format='json')
        else:
            resp = self.assign(plan=plan, waive_reason='access test')
        self.assertIn(resp.status_code, (200, 201), resp.data)

    def login_modules(self):
        return sorted(self.login().data['data']['user']['enabled_modules'])

    def token_modules(self):
        return sorted(AccessToken(self.web.cookies['royal_access_token'].value)['modules'])

    def blocked(self, path):
        resp = self.web.get(path)
        return resp.status_code == 403 and NOT_ENABLED in resp.json().get('message', '')


class LoginAndGateTests(AccessBase):
    def test_company_without_plan_keeps_current_behaviour(self):
        self.assertIn('assets', self.login_modules())
        self.assertFalse(self.blocked('/api/assets/categories/'))
        self.assertFalse(self.blocked('/api/payroll/settings/'))

    def test_starter_sees_and_uses_only_starter(self):
        self.put_on(self.starter)
        starter = resolve_modules(self.starter.features)
        self.assertEqual(self.login_modules(), starter)          # login response
        self.assertEqual(self.token_modules(), starter)          # access-token claim (menus, route guard)
        for path in ('/api/payroll/settings/', '/api/recruitment/candidates/', '/api/assets/categories/',
                     '/api/expenses/'):
            self.assertTrue(self.blocked(path), path)
        for path in ('/api/documents/', '/api/leave/requests/'):
            self.assertFalse(self.blocked(path), path)

    def test_upgrade_then_downgrade_take_effect_immediately(self):
        self.put_on(self.starter)
        self.assertTrue(self.blocked('/api/payroll/settings/'))
        self.put_on(self.growth, change=True)                     # same session, no re-login
        self.assertFalse(self.blocked('/api/payroll/settings/'))
        self.assertIn('payroll', self.login_modules())
        self.put_on(self.starter, change=True)
        self.assertTrue(self.blocked('/api/payroll/settings/'))
        self.assertNotIn('payroll', self.login_modules())

    def test_business_includes_assets(self):
        business = self.starter.__class__.objects.get(code='business')
        self.put_on(business)
        self.assertFalse(self.blocked('/api/assets/categories/'))
        self.assertEqual(self.login_modules(), resolve_modules(business.features))

    def test_awaiting_payment_changes_nothing(self):
        before = self.login_modules()
        self.assertEqual(self.assign(amount_due='500.00').status_code, 201)
        self.assertEqual(self.login_modules(), before)
        self.assertFalse(self.blocked('/api/assets/categories/'))

    def test_deactivation_follows_enforcement_setting(self):
        self.put_on(self.starter)
        CompanySubscription.objects.filter(client=self.company).update(status='inactive')
        self.assertFalse(self.blocked('/api/leave/requests/'))
        with override_settings(SUBSCRIPTION_ENFORCEMENT='on'):
            resp = self.web.get('/api/leave/requests/')
            self.assertEqual(resp.status_code, 403)

    def test_platform_admin_unaffected(self):
        self.put_on(self.starter)
        self.assertEqual(self.pa.get(reverse('saas-subscription-list')).status_code, 200)
        self.assertEqual(self.pa.get(reverse('saas-plan-list')).status_code, 200)


class DashboardIsolationTests(AccessBase):
    def setUp(self):
        super().setUp()
        self.put_on(self.starter)            # no payroll, recruitment, expenses, assets

    def test_single_module_widgets_blocked(self):
        self.assertTrue(self.blocked('/api/dashboard/hr/recruitment-funnel/'))
        self.assertFalse(self.blocked('/api/dashboard/hr/attendance-summary/'))      # attendance is in Starter

    def test_kpis_and_queue_hide_missing_modules(self):
        kpis = self.web.get('/api/dashboard/hr/kpis/').json()['data']
        self.assertIsNone(kpis['active_interviews'])
        queue = self.web.get('/api/dashboard/hr/action-queue/').json()['data']
        self.assertIsNone(queue['candidate_reviews'])
        self.assertIsNone(queue['expense_claims'])
        self.assertIsNotNone(queue['leave_approvals'])
        emp = self.web.get('/api/dashboard/employee/kpis/').json()['data']
        self.assertIsNone(emp['pending_expense_claims'])

    def test_cached_queue_is_masked_after_downgrade(self):
        self.put_on(self.growth, change=True)
        self.assertIsNotNone(self.web.get('/api/dashboard/hr/action-queue/').json()['data']['expense_claims'])
        self.put_on(self.starter, change=True)                 # cached copy still holds expense counts
        self.assertIsNone(self.web.get('/api/dashboard/hr/action-queue/').json()['data']['expense_claims'])

    def test_manager_dashboard(self):
        make_user('access.report@test.com', full_name='Report', reporting_manager=self.user)
        data = self.web.get('/api/dashboard/manager/').json()['data']
        ids = {q['id'] for q in data['quick_actions']}
        self.assertNotIn('my_payslip', ids)
        self.assertNotIn('interviews', ids)
        self.assertIn('apply_leave', ids)

    def test_notifications_and_audit_hide_missing_modules(self):
        from apps.accounts.models import AuditLog
        from apps.notifications.models import Notification
        for module in ('payroll', 'leave'):
            Notification.objects.create(user=self.user, title=module, message='m', notification_type='general',
                                        module=module)
        data = self.web.get('/api/notifications/').json()['data']
        modules = {n['module'] for n in data['results']}
        self.assertEqual(modules, {'leave'})
        self.assertEqual(data['unread_count'], 1)
        AuditLog.objects.create(user=self.user, action='payroll_x', module='payroll')
        AuditLog.objects.create(user=self.user, action='leave_x', module='leave')
        logs = self.web.get('/api/dashboard/system-admin/audit-logs/').json()['data']
        listed = {row.get('module') for row in (logs.get('results') or logs.get('logs') or [])}
        self.assertNotIn('payroll', listed)
