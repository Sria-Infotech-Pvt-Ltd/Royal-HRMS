"""
Field validation across SaaS & Subscriptions: every form's API rejects bad
input with a field-specific message (never a 500) and still accepts valid input.
"""
from unittest import mock

from django.urls import reverse

from apps.tenants.models import CompanySubscription, SubscriptionPlan
from apps.tenants.tests_saas import TODAY, SaasFixture


def field_error(resp, field):
    """The serializer/view error list for `field` (nested new_company fields included)."""
    data = resp.data.get('data') or {}
    if field.startswith('new_company.'):
        data = data.get('new_company') or {}
        field = field.split('.', 1)[1]
    return data.get(field)


class PlanValidationTests(SaasFixture):
    BASE = {'code': 'valid-plan', 'name': 'Valid Plan', 'price_per_employee': '49.50', 'gst_rate': '18',
            'billing_periods': ['monthly'], 'features': ['leave'], 'status': 'draft'}

    def post(self, **over):
        return self.pa.post(reverse('saas-plan-list'), {**self.BASE, **over}, format='json')

    def test_valid_plan_accepted(self):
        resp = self.post(min_employees=1, max_employees=100000, description='Small teams')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_bad_values_rejected_per_field(self):
        cases = [
            ({'name': ''}, 'name'), ({'name': '1234'}, 'name'), ({'name': '<script>'}, 'name'),
            ({'code': ''}, 'code'), ({'code': '4'}, 'code'), ({'code': '9plan'}, 'code'), ({'code': 'my plan'}, 'code'),
            ({'price_per_employee': 'abc'}, 'price_per_employee'), ({'price_per_employee': '-1'}, 'price_per_employee'),
            ({'price_per_employee': '1.999'}, 'price_per_employee'),
            ({'gst_rate': 'ten'}, 'gst_rate'), ({'gst_rate': '-1'}, 'gst_rate'), ({'gst_rate': '100.01'}, 'gst_rate'),
            ({'min_employees': 0}, 'min_employees'), ({'min_employees': 'x'}, 'min_employees'),
            ({'max_employees': 100001}, 'max_employees'), ({'min_employees': 50, 'max_employees': 10}, 'max_employees'),
            ({'billing_periods': []}, 'billing_periods'), ({'billing_periods': ['weekly']}, 'billing_periods'),
            ({'currency': 'XYZ'}, 'currency'), ({'status': 'live'}, 'status'),
            ({'features': ['tds']}, 'features'), ({'display_order': -1}, 'display_order'),
            ({'description': 'x' * 1001}, 'description'),
        ]
        for over, field in cases:
            resp = self.post(**over)
            self.assertEqual(resp.status_code, 400, (over, resp.data))
            self.assertTrue(field_error(resp, field), (over, resp.data))
        self.assertFalse(SubscriptionPlan.objects.filter(code='valid-plan').exists())

    def test_existing_plan_still_editable(self):
        SubscriptionPlan.objects.filter(pk=self.starter.pk).update(code='Old_Code')    # pre-rule code
        url = reverse('saas-plan-detail', kwargs={'pk': self.starter.pk})
        resp = self.pa.patch(url, {'code': 'Old_Code', 'price_per_employee': '55'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class AssignValidationTests(SaasFixture):
    def new(self, company=None, **over):
        body = {'new_company': {'company_code': 'NEWCO9', 'company_name': 'New Co Pvt Ltd', 'admin_email': 'a@new.test',
                                **(company or {})},
                'plan': str(self.starter.pk), 'starts_on': TODAY.isoformat(), **over}
        return self.pa.post(reverse('saas-subscription-list'), {**body, 'dry_run': True}, format='json')

    def test_valid_new_company_preview(self):
        resp = self.new({'contact_name': "R. K. D'Souza", 'contact_phone': '+91 98765-43210', 'gstin': ''},
                        employee_count=10, billing_period='monthly', amount_due='590.00')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_bad_new_company_fields(self):
        for company, field in [
            ({'company_code': ''}, 'new_company.company_code'), ({'company_code': '1ABC'}, 'new_company.company_code'),
            ({'company_code': 'AB'}, 'new_company.company_code'), ({'company_code': 'NEW CO'}, 'new_company.company_code'),
            ({'company_code': 'ADMIN'}, 'new_company.company_code'),
            ({'company_name': ''}, 'new_company.company_name'), ({'company_name': '12345'}, 'new_company.company_name'),
            ({'admin_email': 'not-an-email'}, 'new_company.admin_email'), ({'admin_email': ''}, 'new_company.admin_email'),
            ({'contact_name': 'John123'}, 'new_company.contact_name'),
            ({'contact_phone': 'call me'}, 'new_company.contact_phone'), ({'contact_phone': '12'}, 'new_company.contact_phone'),
            ({'gstin': 'BADGSTIN'}, 'new_company.gstin'),
        ]:
            resp = self.new(company)
            self.assertEqual(resp.status_code, 400, (company, resp.data))
            self.assertTrue(field_error(resp, field), (company, resp.data))

    def test_bad_subscription_fields(self):
        for over, field in [
            ({'starts_on': 'not-a-date'}, 'starts_on'), ({'starts_on': '2026-02-30'}, 'starts_on'),
            ({'starts_on': '1990-01-01'}, 'starts_on'), ({'ends_on': '2026-01-01'}, 'ends_on'),
            ({'employee_count': 0}, 'employee_count'), ({'employee_count': -5}, 'employee_count'),
            ({'employee_count': 'ten'}, 'employee_count'), ({'employee_count': 100001}, 'employee_count'),
            ({'billing_period': 'weekly'}, 'billing_period'),
            ({'amount_due': '-10'}, 'amount_due'), ({'amount_due': 'abc'}, 'amount_due'), ({'amount_due': '0'}, 'amount_due'),
            ({'notes': 'x' * 1001}, 'notes'), ({'plan': 'not-a-uuid'}, 'plan'),
        ]:
            resp = self.new(**over)
            self.assertEqual(resp.status_code, 400, (over, resp.data))
            self.assertTrue(field_error(resp, field), (over, resp.data))

    def test_plan_limits_enforced(self):
        SubscriptionPlan.objects.filter(pk=self.starter.pk).update(min_employees=5, max_employees=50,
                                                                    billing_periods=['monthly'])
        for over, field in [({'employee_count': 4}, 'employee_count'), ({'employee_count': 51}, 'employee_count'),
                            ({'billing_period': 'yearly'}, 'billing_period')]:
            resp = self.new(**over)
            self.assertEqual(resp.status_code, 400, (over, resp.data))
            self.assertTrue(field_error(resp, field), (over, resp.data))
        self.assertEqual(self.new(employee_count=5).status_code, 200)       # boundary values allowed
        self.assertEqual(self.new(employee_count=50).status_code, 200)


@mock.patch('django.utils.timezone.localdate', return_value=TODAY)
class ManageValidationTests(SaasFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.assign(amount_due='500.00').status_code, 201)
        self.cid = str(self.company.pk)

    def url(self, name, **kw):
        return reverse(name, kwargs={'client_id': self.cid, **kw})

    def test_change_plan_employee_count(self, _):
        for bad in ('-5', 'abc', '12.5', '0', '100001', True):
            resp = self.pa.post(self.url('saas-subscription-change-plan'), {'plan': str(self.growth.pk),
                                                                           'employee_count': bad}, format='json')
            self.assertEqual(resp.status_code, 400, (bad, resp.data))
            self.assertTrue(field_error(resp, 'employee_count'))
        ok = self.pa.post(self.url('saas-subscription-change-plan'), {'plan': str(self.growth.pk),
                                                                     'employee_count': '25'}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(CompanySubscription.objects.get(client=self.company).employee_count, 25)

    def test_amount_due(self, _):
        for bad in ('abc', '-1', '0', '99999999999', 'NaN', 'Infinity'):
            resp = self.pa.post(self.url('saas-subscription-amount-due'), {'amount_due': bad}, format='json')
            self.assertEqual(resp.status_code, 400, (bad, resp.data))
        self.assertEqual(self.pa.post(self.url('saas-subscription-amount-due'), {'amount_due': '1180.50'},
                                      format='json').status_code, 200)

    def test_end_date(self, _):
        for bad in ('2026-02-30', 'tomorrow', '1999-12-31', '2026-01-01'):
            resp = self.pa.post(self.url('saas-subscription-period'), {'ends_on': bad}, format='json')
            self.assertEqual(resp.status_code, 400, (bad, resp.data))
        self.assertEqual(self.pa.post(self.url('saas-subscription-period'), {'ends_on': '2027-11-02'},
                                      format='json').status_code, 200)

    def test_payment_fields(self, _):
        base = {'amount': '100', 'method': 'upi', 'paid_on': TODAY.isoformat()}
        for over, field in [({'amount': 'abc'}, 'amount'), ({'amount': '-5'}, 'amount'), ({'amount': ''}, 'amount'),
                            ({'method': 'bitcoin'}, 'method'), ({'paid_on': '2026-02-30'}, 'paid_on'),
                            ({'paid_on': '1999-01-01'}, 'paid_on'), ({'reference': 'UTR<script>'}, 'reference'),
                            ({'notes': 'x' * 1001}, 'notes')]:
            resp = self.pa.post(self.url('saas-subscription-payments'), {**base, **over}, format='multipart')
            self.assertEqual(resp.status_code, 400, (over, resp.data))
            self.assertTrue(field_error(resp, field), (over, resp.data))
        ok = self.pa.post(self.url('saas-subscription-payments'), {**base, 'reference': 'UTR-123/45 #A'},
                          format='multipart')
        self.assertEqual(ok.status_code, 201, ok.data)

    def test_retry_provisioning_email(self, _):
        url = reverse('platform-admin-company-retry-provisioning', kwargs={'pk': self.cid})
        for bad in ('@', 'a@', 'no-at-sign', ''):
            resp = self.pa.post(url, {'admin_email': bad}, format='json')
            self.assertEqual(resp.status_code, 400, bad)
            self.assertTrue(field_error(resp, 'admin_email'))


class RegistrationValidationTests(SaasFixture):
    def test_names_validated(self):
        self.starter.is_public = True
        self.starter.save()
        base = {'plan': 'starter', 'employee_count': 5, 'company_name': 'Acme Pvt Ltd', 'company_code': 'ACMEX',
                'contact_name': 'Asha Rao', 'admin_email': 'a@acme.test', 'contact_phone': '9876543210',
                'accept_terms': True}
        for over, field in [({'company_name': '!!!'}, 'company_name'), ({'contact_name': 'Asha 99'}, 'contact_name'),
                            ({'employee_count': 0}, 'employee_count'), ({'contact_phone': 'abc'}, 'contact_phone')]:
            resp = self.client.post(reverse('public-registration'), {**base, **over}, content_type='application/json')
            self.assertEqual(resp.status_code, 400, (over, resp.json()))
