"""
Manual payment tracking (apps.tenants.billing): payment status is separate
from subscription and provisioning status, assignment never marks a
subscription paid, modules are applied only after payment is confirmed or
waived, and every payment change is kept (history + audit log).
"""
import datetime
import shutil
import tempfile
from unittest import mock

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.tenants import billing
from apps.tenants.models import (
    Client, CompanySubscription, PlatformAdminAuditLog, SubscriptionHistory, SubscriptionPayment,
)
from apps.tenants.modules import resolve_modules
from apps.tenants.tests_saas import TODAY, SaasFixture

PDF = b'%PDF-1.4\n%test receipt\n'


class PaymentFixture(SaasFixture):
    def setUp(self):
        super().setUp()
        self.receipts = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.receipts, ignore_errors=True)
        field = SubscriptionPayment._meta.get_field('receipt')
        patcher = mock.patch.object(field, 'storage', FileSystemStorage(location=self.receipts))
        patcher.start()
        self.addCleanup(patcher.stop)

    def url(self, name, **kw):
        return reverse(name, kwargs={'client_id': str(self.company.pk), **kw})

    def sub(self):
        return CompanySubscription.objects.get(client=self.company)

    def record(self, amount='500.00', confirm=False, **extra):
        body = {'amount': amount, 'method': 'neft', 'paid_on': TODAY.isoformat(), 'confirm': confirm, **extra}
        return self.pa.post(self.url('saas-subscription-payments'), body, format='multipart')

    def set_due(self, amount):
        return self.pa.post(self.url('saas-subscription-amount-due'), {'amount_due': amount}, format='json')


@mock.patch('django.utils.timezone.localdate', return_value=TODAY)
class ManualPaymentTests(PaymentFixture):
    def test_assignment_is_never_payment(self, _):
        resp = self.assign(amount_due='1180.00')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('awaiting payment', resp.data['message'])
        sub = self.sub()
        self.assertEqual((sub.status, sub.payment_status, sub.provisioning_status),
                         ('active', 'pending', 'awaiting_payment'))      # three independent statuses
        self.assertEqual(str(sub.amount_due), '1180.00')
        self.assertFalse(sub.payments.exists())
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), sorted(self.original_modules))

    def test_partial_then_full_payment_applies_subscription(self, _):
        self.assign(amount_due='1000.00')
        first = self.record('400.00', reference='UTR111', notes='first instalment')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.sub().payment_status, 'pending')           # recorded, not yet confirmed
        pid = first.data['data']['payment']['id']
        ok = self.pa.post(self.url('saas-subscription-payment-verify', payment_id=pid))
        self.assertEqual(ok.status_code, 200, ok.data)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('partially_paid', 'awaiting_payment'))
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), sorted(self.original_modules))

        second = self.record('600.00', confirm=True, reference='UTR222')
        self.assertEqual(second.status_code, 201, second.data)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('paid', 'success'))
        self.assertIsNotNone(sub.provisioned_at)
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), resolve_modules(self.starter.features))
        self.assertEqual(second.data['data']['subscription']['amount_received'], '1000.00')

        p = SubscriptionPayment.objects.get(reference='UTR111')
        self.assertEqual((p.status, p.recorded_by.email, p.reviewed_by.email),
                         ('verified', 'saas.admin@test.com', 'saas.admin@test.com'))
        events = list(SubscriptionHistory.objects.filter(subscription=sub).values_list('event', flat=True))
        for e in ('assigned', 'payment_recorded', 'payment_verified', 'provisioned'):
            self.assertIn(e, events)
        actions = set(PlatformAdminAuditLog.objects.values_list('action', flat=True))
        self.assertTrue({'saas_payment_recorded', 'saas_payment_verified'} <= actions)

    def test_confirming_needs_amount_due(self, _):
        self.assign()
        resp = self.record(confirm=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('subscription amount', resp.data['message'])        # "amount due" relabelled
        self.assertFalse(SubscriptionPayment.objects.exists())            # nothing half-saved
        pid = self.record().data['data']['payment']['id']
        self.assertEqual(self.pa.post(self.url('saas-subscription-payment-verify', payment_id=pid)).status_code, 400)

    def test_rejected_payment_kept_and_not_counted(self, _):
        self.assign(amount_due='500.00')
        pid = self.record('500.00', reference='CHQ9').data['data']['payment']['id']
        no_reason = self.pa.post(self.url('saas-subscription-payment-reject', payment_id=pid), {}, format='json')
        self.assertEqual(no_reason.status_code, 400)
        resp = self.pa.post(self.url('saas-subscription-payment-reject', payment_id=pid),
                            {'reason': 'Cheque bounced'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('failed', 'awaiting_payment'))
        p = SubscriptionPayment.objects.get(pk=pid)
        self.assertEqual((p.status, p.rejection_reason), ('rejected', 'Cheque bounced'))
        # A decided payment can't be flipped; the same reference can be recorded again.
        self.assertEqual(self.pa.post(self.url('saas-subscription-payment-verify', payment_id=pid)).status_code, 400)
        self.assertEqual(self.record('500.00', reference='CHQ9').status_code, 201)

    def test_duplicate_reference_refused(self, _):
        self.assign(amount_due='500.00')
        self.assertEqual(self.record(reference='UTR1').status_code, 201)
        self.assertEqual(self.record(reference='utr1').status_code, 400)

    def test_input_validation(self, _):
        self.assign(amount_due='500.00')
        self.assertEqual(self.record('0').status_code, 400)
        self.assertEqual(self.record(method='crypto').status_code, 400)
        future = (TODAY + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.record(paid_on=future).status_code, 400)
        self.assertEqual(self.set_due('0').status_code, 400)
        self.assertEqual(self.set_due('abc').status_code, 400)

    def test_waiver_needs_reason_and_applies(self, _):
        self.assign()
        waiver = self.url('saas-subscription-waiver')
        self.assertEqual(self.pa.post(waiver, {'waive': True}, format='json').status_code, 400)
        resp = self.pa.post(waiver, {'waive': True, 'reason': 'Pilot month'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status, sub.payment_waiver_reason),
                         ('waived', 'success', 'Pilot month'))
        self.assertTrue(PlatformAdminAuditLog.objects.filter(action='saas_payment_waived').exists())
        # Removing the waiver restores the payment status but never removes access.
        resp = self.pa.post(waiver, {'waive': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('pending', 'success'))
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), resolve_modules(self.starter.features))

    def test_waiver_at_assignment(self, _):
        resp = self.assign(waive_reason='Complimentary')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((self.sub().payment_status, self.sub().provisioning_status), ('waived', 'success'))

    def test_plan_change_before_payment_applies_nothing(self, _):
        self.assign(amount_due='500.00')
        resp = self.pa.post(self.url('saas-subscription-change-plan'), {'plan': str(self.growth.pk)}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), sorted(self.original_modules))
        self.record('500.00', confirm=True)
        self.company.refresh_from_db()
        self.assertEqual(sorted(self.company.enabled_modules), resolve_modules(self.growth.features))

    def test_failed_apply_marked_failed_then_retry(self, _):
        self.assign(amount_due='500.00')
        with mock.patch('apps.tenants.billing.apply_subscription', side_effect=RuntimeError('db down')):
            self.record('500.00', confirm=True)
        sub = self.sub()
        self.assertEqual((sub.payment_status, sub.provisioning_status), ('paid', 'failed'))   # never "success"
        self.assertTrue(sub.provisioning_error)
        resp = self.pa.post(self.url('saas-subscription-provision'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.sub().provisioning_status, 'success')

    def test_receipt_upload_and_download(self, _):
        self.assign(amount_due='500.00')
        resp = self.record(receipt=SimpleUploadedFile('bank slip.pdf', PDF, content_type='application/pdf'))
        self.assertEqual(resp.status_code, 201, resp.data)
        payment = resp.data['data']['payment']
        self.assertTrue(payment['has_receipt'])
        self.assertEqual(payment['receipt_name'], 'bank slip.pdf')
        got = self.pa.get(self.url('saas-subscription-payment-receipt', payment_id=payment['id']))
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got['Content-Type'], 'application/pdf')
        self.assertEqual(got.content, PDF)
        self.assertEqual(got['Cache-Control'], 'private, no-store')

    def test_receipt_type_and_size_checked(self, _):
        self.assign(amount_due='500.00')
        txt = SimpleUploadedFile('r.txt', b'hello', content_type='text/plain')
        self.assertEqual(self.record(receipt=txt).status_code, 400)
        big = SimpleUploadedFile('r.pdf', PDF + b'0' * (5 * 1024 * 1024), content_type='application/pdf')
        self.assertEqual(self.record(receipt=big).status_code, 400)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_payments_cannot_be_edited_or_deleted(self, _):
        self.assign(amount_due='500.00')
        pid = self.record().data['data']['payment']['id']
        url = self.url('saas-subscription-payments')
        for method in (self.pa.put, self.pa.patch, self.pa.delete):
            self.assertEqual(method(url, {'payment_status': 'paid'}, format='json').status_code, 405)
        self.assertEqual(self.pa.get(self.url('saas-subscription-payment-verify', payment_id=pid)).status_code, 405)
        self.assertEqual(self.sub().payment_status, 'pending')

    def test_requires_platform_admin(self, _):
        from rest_framework.test import APIClient
        self.assign(amount_due='500.00')
        anon = APIClient()
        self.assertIn(anon.get(self.url('saas-subscription-payments')).status_code, (401, 403))
        self.assertIn(anon.post(self.url('saas-subscription-waiver'), {'waive': True, 'reason': 'x'},
                                format='json').status_code, (401, 403))
        self.assertEqual(self.sub().payment_status, 'pending')

    def test_detail_includes_payment_history(self, _):
        self.assign(amount_due='500.00')
        self.record('200.00', reference='A1')
        self.record('300.00', reference='A2', confirm=True)
        data = self.pa.get(reverse('saas-subscription-detail', kwargs={'client_id': str(self.company.pk)})).data['data']
        self.assertEqual({p['reference'] for p in data['payments']}, {'A1', 'A2'})
        self.assertEqual(data['company']['subscription']['unconfirmed_payments'], 1)
        listed = self.pa.get(reverse('saas-subscription-list')).data['data']['results']
        row = next(r for r in listed if r['id'] == str(self.company.pk))
        self.assertEqual(row['subscription']['payment_status'], 'partially_paid')


@mock.patch('django.utils.timezone.localdate', return_value=TODAY)
class NewCompanyAwaitingPaymentTests(PaymentFixture):
    def new_company(self, code='PAYCO1', **extra):
        return self.pa.post(reverse('saas-subscription-list'), {
            'new_company': {'company_code': code, 'company_name': 'Pay Co', 'admin_email': 'admin@payco.test'},
            'plan': str(self.starter.pk), 'starts_on': TODAY.isoformat(), **extra}, format='json')

    def test_not_swept_while_awaiting_payment_then_provisioned(self, _):
        from apps.tenants.tasks import sweep_stale_provisioning
        self.assertEqual(self.new_company(amount_due='500.00').status_code, 202)
        client = Client.objects.get(company_code='PAYCO1')
        old = timezone.now() - datetime.timedelta(days=3)
        Client.objects.filter(pk=client.pk).update(created_at=old, updated_at=old)
        sweep_stale_provisioning()
        client.refresh_from_db()
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_AWAITING_PAYMENT)   # untouched

        with mock.patch('apps.tenants.tasks.finish_provisioning_task.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.pa.post(reverse('saas-subscription-payments', kwargs={'client_id': str(client.pk)}), {
                    'amount': '500.00', 'method': 'rtgs', 'paid_on': TODAY.isoformat(), 'confirm': True},
                    format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        delay.assert_called_once_with(str(client.pk), 'admin@payco.test', resolve_modules(self.starter.features))
        client.refresh_from_db()
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_PENDING)
        # Setup has only just started: the sweep (updated_at based) leaves it alone.
        sweep_stale_provisioning()
        client.refresh_from_db()
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_PENDING)
        sub = CompanySubscription.objects.get(client=client)
        self.assertEqual(sub.provisioning_status, 'pending')
        billing.mark_provisioned(client.pk)                                  # what the task does on success
        sub.refresh_from_db()
        self.assertEqual((sub.provisioning_status, sub.pending_admin_email), ('success', ''))

    def test_stale_setup_marks_subscription_failed(self, _):
        from apps.tenants.tasks import sweep_stale_provisioning
        with mock.patch('apps.tenants.tasks.finish_provisioning_task.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                self.new_company(waive_reason='Trial')
        client = Client.objects.get(company_code='PAYCO1')
        old = timezone.now() - datetime.timedelta(hours=1)
        Client.objects.filter(pk=client.pk).update(updated_at=old)
        sweep_stale_provisioning()
        client.refresh_from_db()
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_FAILED)
        self.assertEqual(CompanySubscription.objects.get(client=client).provisioning_status, 'failed')

    def test_queue_down_marks_failed_not_success(self, _):
        with mock.patch('apps.tenants.tasks.finish_provisioning_task.delay', side_effect=OSError('broker down')):
            with self.captureOnCommitCallbacks(execute=True):
                self.new_company(waive_reason='Trial')
        client = Client.objects.get(company_code='PAYCO1')
        self.assertEqual(client.provisioning_status, Client.PROVISIONING_FAILED)
        self.assertEqual(CompanySubscription.objects.get(client=client).provisioning_status, 'failed')


class ExistingDataTests(PaymentFixture):
    def test_legacy_backfill_applied_and_payment_not_assumed(self):
        from io import StringIO

        from django.core.management import call_command
        call_command('assign_legacy_subscriptions', '--apply', stdout=StringIO())
        sub = self.sub()
        self.assertEqual((sub.source, sub.payment_status, sub.provisioning_status), ('legacy', 'pending', 'success'))
