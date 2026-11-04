"""
Website registration → verified payment → Platform Admin approval.

Public plans / registration / status APIs (validation, server-side amount,
no personal data in status), payment only through a verified gateway event
(fake gateway through the apps.tenants.payments interface: duplicate events,
amount mismatch, failure), approval only when paid + pending (existing
provisioning + the same subscription service, no duplicates, code override),
rejection with reason + refund flag, notifications, provisioning failure.
"""
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.tenants.models import (
    Client, CompanyRegistration, CompanySubscription, PaymentTransaction, PlatformAdminAuditLog,
    PlatformNotification, SubscriptionPlan,
)
from apps.tenants.payments import PaymentGateway, VerifiedPayment, register_gateway, to_minor
from apps.tenants.registrations import RegistrationError, record_payment_event
from apps.tenants.subscriptions import preview_modules
from apps.tenants.tests_company_system_admin import _login_platform_admin, _make_platform_admin
from config.test_runner import TEST_COMPANY_CODE


@register_gateway
class FakeGateway(PaymentGateway):
    name = 'fake'

    def create_order(self, registration):
        return {'order_id': f'order_{registration.reference}', 'amount_minor': to_minor(registration.total),
                'currency': registration.currency, 'checkout': {'order_id': f'order_{registration.reference}',
                                                                 'key_id': 'public_test_key'}}

    def parse_webhook(self, body, headers):
        return None


FORM = {
    'plan': 'growth', 'billing_period': 'monthly', 'employee_count': 10, 'company_name': 'Acme Pvt Ltd',
    'company_code': 'acme1', 'contact_name': 'Contact Person', 'admin_email': 'Admin@Acme.test',
    'contact_phone': '+91 98765 43210', 'accept_terms': True,
}


class RegFixture(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        SubscriptionPlan.objects.filter(code__in=['starter', 'growth']).update(is_public=True)
        self.growth = SubscriptionPlan.objects.get(code='growth')
        self.admin = _make_platform_admin('reg.admin@test.com')
        self.pa = APIClient()
        _login_platform_admin(self.pa, 'reg.admin@test.com')
        self.web = APIClient()

    def register(self, **overrides):
        return self.web.post(reverse('public-registration'), {**FORM, **overrides}, format='json')

    def paid_registration(self, **overrides) -> CompanyRegistration:
        with override_settings(PAYMENT_GATEWAY='fake'):
            resp = self.register(**overrides)
        self.assertEqual(resp.status_code, 201, resp.data)
        reg = CompanyRegistration.objects.get(reference=resp.data['data']['reference'])
        txn = reg.payments.get()
        record_payment_event(VerifiedPayment(event_id=f'evt_{reg.reference}', order_id=txn.order_id,
                                             payment_id=f'pay_{reg.reference}', amount_minor=txn.amount_minor,
                                             currency=txn.currency, status='paid'), 'fake')
        reg.refresh_from_db()
        return reg

    def approve(self, reg, **body):
        with mock.patch('apps.tenants.views_saas.finish_provisioning_task.delay') as delay:
            resp = self.pa.post(reverse('saas-registration-approve', kwargs={'pk': reg.pk}), body, format='json')
        return resp, delay


class PublicApiTests(RegFixture):
    def test_plans_only_published_with_feature_status(self):
        data = self.web.get(reverse('public-plans')).data['data']
        codes = [p['code'] for p in data]
        self.assertEqual(codes, ['starter', 'growth'])                   # business not published
        growth = {f['key']: f['status'] for f in data[1]['features']}
        self.assertEqual(growth['payroll'], 'included')
        self.assertEqual(growth['employee_management'], 'included')      # core
        self.assertEqual(growth['assets'], 'not_included')
        self.assertEqual(growth['tds'], 'coming_soon')

    def test_register_computes_amount_and_waits_for_payment(self):
        resp = self.register()
        self.assertEqual(resp.status_code, 201, resp.data)
        d = resp.data['data']
        # 99 x 10 x 1 = 990 + 18% GST 178.20 = 1168.20
        self.assertEqual((d['subtotal'], d['gst_amount'], d['total']), ('990.00', '178.20', '1168.20'))
        self.assertEqual(d['payment'], {'available': False, 'message': mock.ANY})
        reg = CompanyRegistration.objects.get(reference=d['reference'])
        self.assertEqual((reg.company_code, reg.admin_email, reg.payment_status), ('ACME1', 'admin@acme.test', 'pending'))
        self.assertTrue(PlatformNotification.objects.filter(recipient=self.admin, kind='registration_received').exists())
        self.assertFalse(Client.objects.filter(company_code='ACME1').exists())

    def test_gst_inclusive_and_yearly(self):
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(gst_inclusive=True, billing_periods=['monthly', 'yearly'])
        d = self.register(billing_period='yearly').data['data']
        self.assertEqual(d['total'], '11880.00')                         # 99 x 10 x 12, GST inside
        self.assertEqual(d['gst_amount'], '1812.20')

    def test_validation(self):
        self.assertEqual(self.register(company_code='1bad').status_code, 400)
        self.assertEqual(self.register(company_code='public').status_code, 400)
        self.assertEqual(self.register(company_code=TEST_COMPANY_CODE).status_code, 400)
        self.assertEqual(self.register(accept_terms=False).status_code, 400)
        self.assertEqual(self.register(plan='business').status_code, 400)      # not published
        self.assertEqual(self.register(billing_period='yearly').status_code, 400)  # not offered
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(max_employees=5)
        self.assertEqual(self.register().status_code, 400)
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(max_employees=None)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 400)                     # code already registered
        self.assertEqual(self.register(company_code='other2', website='http://spam').status_code, 400)
        self.assertEqual(CompanyRegistration.objects.count(), 1)

    def test_status_has_no_personal_data(self):
        ref = self.register().data['data']['reference']
        data = self.web.get(reverse('public-registration-status', kwargs={'reference': ref.lower()})).data['data']
        self.assertEqual(data['status'], 'awaiting_payment')
        self.assertNotIn('admin@acme.test', str(data))
        self.assertNotIn('Contact Person', str(data))
        self.assertEqual(self.web.get(reverse('public-registration-status', kwargs={'reference': 'NOPE'})).status_code, 404)


class PaymentTests(RegFixture):
    def test_gateway_order_and_verified_payment(self):
        reg = self.paid_registration()
        self.assertEqual((reg.payment_status, reg.payments.get().status), ('paid', 'paid'))
        self.assertTrue(PlatformNotification.objects.filter(kind='registration_paid').exists())
        status_ = self.web.get(reverse('public-registration-status', kwargs={'reference': reg.reference})).data['data']
        self.assertEqual(status_['status'], 'under_review')

    def test_duplicate_event_ignored_and_mismatch_refused(self):
        reg = self.paid_registration()
        txn = reg.payments.get()
        dup = VerifiedPayment(event_id=txn.event_id, order_id=txn.order_id, payment_id='x', amount_minor=1,
                              currency='INR', status='paid')
        self.assertIsNone(record_payment_event(dup, 'fake'))
        with override_settings(PAYMENT_GATEWAY='fake'):
            resp = self.register(company_code='ACME2')
        other = CompanyRegistration.objects.get(reference=resp.data['data']['reference'])
        t2 = other.payments.get()
        with self.assertRaises(RegistrationError):
            record_payment_event(VerifiedPayment(event_id='e2', order_id=t2.order_id, payment_id='p2',
                                                 amount_minor=t2.amount_minor - 100, currency='INR', status='paid'), 'fake')
        other.refresh_from_db()
        self.assertEqual(other.payment_status, 'pending')

    def test_failed_payment(self):
        with override_settings(PAYMENT_GATEWAY='fake'):
            resp = self.register()
        reg = CompanyRegistration.objects.get(reference=resp.data['data']['reference'])
        t = reg.payments.get()
        record_payment_event(VerifiedPayment(event_id='e3', order_id=t.order_id, payment_id='', amount_minor=t.amount_minor,
                                             currency='INR', status='failed', failure_reason='card declined'), 'fake')
        reg.refresh_from_db()
        self.assertEqual(reg.payment_status, 'failed')


class ApprovalTests(RegFixture):
    def test_unpaid_cannot_be_approved(self):
        reg = CompanyRegistration.objects.get(reference=self.register().data['data']['reference'])
        resp, delay = self.approve(reg)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('verified payment', resp.data['message'])
        delay.assert_not_called()
        self.assertFalse(Client.objects.filter(company_code='ACME1').exists())

    def test_approve_paid_uses_existing_provisioning_and_subscription(self):
        reg = self.paid_registration()
        # Plan edited after payment: price and modules — the customer still gets what they paid for.
        SubscriptionPlan.objects.filter(pk=self.growth.pk).update(
            price_per_employee=Decimal('120'), features=[f for f in self.growth.features if f != 'payroll'])
        resp, delay = self.approve(reg)
        self.assertEqual(resp.status_code, 200, resp.data)
        client = Client.objects.get(company_code='ACME1')
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_PENDING)
        self.assertEqual(sorted(client.enabled_modules), preview_modules(self.growth))
        delay.assert_called_once_with(str(client.pk), 'admin@acme.test', client.enabled_modules)
        sub = client.subscription
        self.assertEqual((sub.source, sub.employee_count, str(sub.price_per_employee)), ('website', 10, '99.00'))
        # Paid by the verified gateway payment; set up by the provisioning task.
        self.assertEqual((sub.payment_status, sub.amount_due), ('paid', reg.total))
        self.assertEqual(sub.provisioning_status, 'pending')
        self.assertIsNotNone(sub.ends_on)
        reg.refresh_from_db()
        self.assertEqual((reg.approval_status, reg.client_id), ('approved', client.pk))
        self.assertTrue(PlatformAdminAuditLog.objects.filter(action='saas_registration_approved').exists())
        again, delay2 = self.approve(reg)
        self.assertEqual(again.status_code, 400)                                 # no second tenant
        delay2.assert_not_called()
        self.assertEqual(Client.objects.filter(company_code='ACME1').count(), 1)

    def test_code_taken_at_approval_can_be_overridden(self):
        reg = self.paid_registration()
        CompanyRegistration.objects.filter(pk=reg.pk).update(company_code=TEST_COMPANY_CODE)
        resp, _ = self.approve(reg)
        self.assertEqual(resp.status_code, 400)
        resp, _ = self.approve(reg, company_code='acmenew')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(Client.objects.filter(company_code='ACMENEW').exists())

    def test_queue_failure_marks_failed_for_retry(self):
        reg = self.paid_registration()
        with mock.patch('apps.tenants.views_saas.finish_provisioning_task.delay', side_effect=RuntimeError):
            resp = self.pa.post(reverse('saas-registration-approve', kwargs={'pk': reg.pk}), {}, format='json')
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(Client.objects.get(company_code='ACME1').provisioning_status, Client.PROVISIONING_FAILED)
        status_ = self.web.get(reverse('public-registration-status', kwargs={'reference': reg.reference})).data['data']
        self.assertEqual(status_['status'], 'setup_delayed')

    def test_reject_needs_reason_and_flags_refund(self):
        reg = self.paid_registration()
        url = reverse('saas-registration-reject', kwargs={'pk': reg.pk})
        self.assertEqual(self.pa.post(url, {'reason': ' '}, format='json').status_code, 400)
        resp = self.pa.post(url, {'reason': 'Duplicate company'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        reg.refresh_from_db()
        self.assertEqual((reg.approval_status, reg.refund_status), ('rejected', 'pending'))
        resp, _ = self.approve(reg)
        self.assertEqual(resp.status_code, 400)
        # The code is free again after rejection.
        self.assertEqual(self.register().status_code, 201)

    def test_list_filters_and_requires_platform_admin(self):
        self.paid_registration()
        self.register(company_code='ACME3')
        url = reverse('saas-registration-list')
        self.assertEqual(self.pa.get(url, {'status': 'pending_approval'}).data['data']['count'], 1)
        self.assertEqual(self.pa.get(url, {'status': 'awaiting_payment'}).data['data']['count'], 1)
        self.assertIn(APIClient().get(url).status_code, (401, 403))


class NotificationTests(RegFixture):
    def test_unread_count_and_mark_read(self):
        self.register()
        other = _make_platform_admin('reg.other@test.com')
        url = reverse('platform-admin-notifications')
        data = self.pa.get(url).data['data']
        self.assertEqual(data['unread_count'], 1)
        others = PlatformNotification.objects.filter(recipient=other)
        resp = self.pa.post(reverse('platform-admin-notifications-read'),
                            {'ids': [str(n.pk) for n in others] + [data['results'][0]['id']]}, format='json')
        self.assertEqual(resp.data['data']['updated'], 1)                       # own only
        self.assertEqual(self.pa.get(url).data['data']['unread_count'], 0)
