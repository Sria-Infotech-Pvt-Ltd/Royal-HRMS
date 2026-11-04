"""
Manual payment tracking for subscriptions (payments received outside the
app: UPI, bank transfer, NEFT/RTGS, cash, cheque). No payment gateway here —
see apps.tenants.payments for that separate interface.

  record_payment()   add a payment row ('recorded'); counts only once confirmed
  verify_payment()   Platform Admin confirms the money was received
  reject_payment()   wrong / bounced entry — kept, never deleted
  waive_payment()    explicit, reasoned waiver (trial, complimentary, ...)
  set_amount_due()   what the customer owes for this subscription

payment_status is derived from confirmed payments vs amount_due (except
'waived'). Assigning a subscription never marks it paid. The subscription's
modules are applied only when payment is Paid or Waived (provision()); until
then it stays 'awaiting_payment' and the company keeps its current modules
(a new company isn't set up at all). Every change writes SubscriptionHistory.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.tenants.models import Client, CompanySubscription, SubscriptionHistory, SubscriptionPayment
from apps.tenants.subscriptions import apply_subscription, effective_modules, summary

logger = logging.getLogger(__name__)

Sub = CompanySubscription
READY_TO_PROVISION = (Sub.PAYMENT_PAID, Sub.PAYMENT_WAIVED)


class PaymentError(Exception):
    """Caller-fixable problem (shown to the Platform Admin)."""


def _history(sub, event, admin, note='', before=None):
    SubscriptionHistory.objects.create(subscription=sub, event=event, before=before or {}, after=summary(sub),
                                       admin=admin, note=note[:1000])


def _lock(sub) -> CompanySubscription:
    return Sub.objects.select_for_update().select_related('plan', 'client').get(pk=sub.pk)


def amount_received(sub) -> Decimal:
    total = sub.payments.filter(status=SubscriptionPayment.STATUS_VERIFIED).aggregate(t=Sum('amount'))['t']
    return total or Decimal('0')


def derive_payment_status(sub) -> str:
    if sub.payment_status == Sub.PAYMENT_WAIVED:
        return Sub.PAYMENT_WAIVED
    received = amount_received(sub)
    if received > 0:
        if sub.amount_due is not None and received >= sub.amount_due:
            return Sub.PAYMENT_PAID
        return Sub.PAYMENT_PARTIAL
    if sub.payments.filter(status=SubscriptionPayment.STATUS_REJECTED).exists():
        return Sub.PAYMENT_FAILED
    return Sub.PAYMENT_PENDING


def _refresh_status(sub, admin):
    """Re-derive payment_status; provision when it became Paid."""
    new = derive_payment_status(sub)
    if new != sub.payment_status:
        sub.payment_status = new
        sub.save(update_fields=['payment_status', 'updated_at'])
    provision_if_ready(sub, admin)


# ─── Payments ────────────────────────────────────────────────────────────────

@transaction.atomic
def record_payment(*, sub, amount: Decimal, method: str, paid_on, reference: str = '', notes: str = '',
                   receipt=None, admin=None, confirm: bool = False) -> SubscriptionPayment:
    sub = _lock(sub)
    reference = (reference or '').strip()
    if reference and sub.payments.filter(reference__iexact=reference).exclude(
            status=SubscriptionPayment.STATUS_REJECTED).exists():
        raise PaymentError(f'A payment with reference "{reference}" is already recorded for this subscription.')
    if confirm and sub.amount_due is None:
        raise PaymentError('Set the amount due before confirming payments.')
    payment = SubscriptionPayment(
        subscription=sub, amount=amount, currency=sub.currency, method=method, paid_on=paid_on,
        reference=reference, notes=(notes or '').strip(), recorded_by=admin,
        receipt_name=(getattr(receipt, 'name', '') or '')[:255],
    )
    if receipt is not None:
        payment.receipt = receipt
    payment.save()
    _history(sub, SubscriptionHistory.EVENT_PAYMENT_RECORDED, admin, _describe(payment))
    if confirm:
        _verify(sub, payment, admin)
    return payment


def _describe(p: SubscriptionPayment) -> str:
    ref = f', ref {p.reference}' if p.reference else ''
    return f'{p.amount} {p.currency} via {p.get_method_display()} on {p.paid_on.isoformat()}{ref}'


def _verify(sub, payment, admin):
    payment.status = SubscriptionPayment.STATUS_VERIFIED
    payment.reviewed_by = admin
    payment.reviewed_at = timezone.now()
    payment.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    _history(sub, SubscriptionHistory.EVENT_PAYMENT_VERIFIED, admin, _describe(payment))
    _refresh_status(sub, admin)


def _locked_payment(sub, payment_id) -> tuple[CompanySubscription, SubscriptionPayment]:
    sub = _lock(sub)
    payment = SubscriptionPayment.objects.select_for_update().filter(subscription=sub, pk=payment_id).first()
    if payment is None:
        raise SubscriptionPayment.DoesNotExist
    if payment.status != SubscriptionPayment.STATUS_RECORDED:
        raise PaymentError('This payment has already been confirmed or rejected.')
    return sub, payment


@transaction.atomic
def verify_payment(*, sub, payment_id, admin=None) -> SubscriptionPayment:
    sub, payment = _locked_payment(sub, payment_id)
    if sub.amount_due is None:
        raise PaymentError('Set the amount due before confirming payments.')
    _verify(sub, payment, admin)
    return payment


@transaction.atomic
def reject_payment(*, sub, payment_id, admin=None, reason: str = '') -> SubscriptionPayment:
    reason = (reason or '').strip()
    if not reason:
        raise PaymentError('Give a reason for rejecting this payment.')
    sub, payment = _locked_payment(sub, payment_id)
    payment.status = SubscriptionPayment.STATUS_REJECTED
    payment.rejection_reason = reason
    payment.reviewed_by = admin
    payment.reviewed_at = timezone.now()
    payment.save(update_fields=['status', 'rejection_reason', 'reviewed_by', 'reviewed_at'])
    _history(sub, SubscriptionHistory.EVENT_PAYMENT_REJECTED, admin, f'{_describe(payment)} — {reason}')
    _refresh_status(sub, admin)
    return payment


@transaction.atomic
def set_amount_due(*, sub, amount: Decimal, admin=None, note: str = '') -> CompanySubscription:
    if amount is None or amount <= 0:
        raise PaymentError('Amount due must be more than zero (use "Waive payment" for no charge).')
    sub = _lock(sub)
    before = {'amount_due': str(sub.amount_due) if sub.amount_due is not None else None}
    sub.amount_due = amount
    sub.save(update_fields=['amount_due', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_AMOUNT_DUE_CHANGED, admin,
             f'{before["amount_due"] or "not set"} → {amount} {sub.currency}' + (f' — {note}' if note else ''),
             before=before)
    _refresh_status(sub, admin)
    return sub


@transaction.atomic
def waive_payment(*, sub, admin=None, reason: str = '') -> CompanySubscription:
    reason = (reason or '').strip()
    if not reason:
        raise PaymentError('Give a reason for waiving the payment.')
    sub = _lock(sub)
    if sub.payment_status == Sub.PAYMENT_WAIVED:
        raise PaymentError('Payment is already waived.')
    sub.payment_status = Sub.PAYMENT_WAIVED
    sub.payment_waiver_reason = reason
    sub.save(update_fields=['payment_status', 'payment_waiver_reason', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_PAYMENT_WAIVED, admin, reason)
    provision_if_ready(sub, admin)
    return sub


@transaction.atomic
def remove_waiver(*, sub, admin=None, note: str = '') -> CompanySubscription:
    """Back to the status the confirmed payments give. Never removes access
    already granted — deactivate the subscription for that."""
    sub = _lock(sub)
    if sub.payment_status != Sub.PAYMENT_WAIVED:
        raise PaymentError('Payment is not waived.')
    sub.payment_status = Sub.PAYMENT_PENDING
    sub.payment_status = derive_payment_status(sub)
    sub.payment_waiver_reason = ''
    sub.save(update_fields=['payment_status', 'payment_waiver_reason', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_PAYMENT_WAIVER_REMOVED, admin, note)
    return sub


# ─── Provisioning (applying the subscription) ────────────────────────────────

def provision_if_ready(sub, admin=None):
    if sub.provisioning_status == Sub.PROVISION_AWAITING_PAYMENT and sub.payment_status in READY_TO_PROVISION:
        provision(sub, admin)


def provision(sub, admin=None):
    """Apply the subscription. Existing company: write its modules now and
    mark Success only once they are in place. New company (registry row
    only): queue the normal provisioning task after commit; the task marks
    Success when the schema, seed data, admin and modules are done."""
    client = Client.objects.get(pk=sub.client_id)
    if client.provisioning_status == Client.PROVISIONING_AWAITING_PAYMENT:
        if not sub.pending_admin_email:
            _provision_failed(sub, admin, 'The company admin email is missing.')
            return
        Client.objects.filter(pk=client.pk).update(provisioning_status=Client.PROVISIONING_PENDING,
                                                   updated_at=timezone.now())
        sub.provisioning_status = Sub.PROVISION_PENDING
        sub.provisioning_error = ''
        sub.save(update_fields=['provisioning_status', 'provisioning_error', 'updated_at'])
        client_id, email, modules = str(client.pk), sub.pending_admin_email, effective_modules(sub)
        transaction.on_commit(lambda: _queue_new_company(client_id, email, modules))
        return
    try:
        with transaction.atomic():
            modules = apply_subscription(client)
            client.refresh_from_db(fields=['enabled_modules'])
            if sorted(client.enabled_modules or []) != modules:
                raise RuntimeError('modules were not applied')
    except Exception:
        logger.exception('Applying subscription failed for %s.', client.company_code)
        _provision_failed(sub, admin, 'The modules could not be applied. Try again.')
        return
    sub.provisioning_status = Sub.PROVISION_SUCCESS
    sub.provisioning_error = ''
    sub.provisioned_at = timezone.now()
    sub.save(update_fields=['provisioning_status', 'provisioning_error', 'provisioned_at', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_PROVISIONED, admin, 'Modules and limits applied.')


def _provision_failed(sub, admin, message):
    sub.provisioning_status = Sub.PROVISION_FAILED
    sub.provisioning_error = message[:255]
    sub.save(update_fields=['provisioning_status', 'provisioning_error', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_PROVISIONING_FAILED, admin, message)


def _queue_new_company(client_id, admin_email, modules):
    from apps.tenants.tasks import finish_provisioning_task
    try:
        finish_provisioning_task.delay(client_id, admin_email, modules)
    except Exception:
        logger.exception('Failed to queue provisioning for %s — broker unreachable.', client_id)
        Client.objects.filter(pk=client_id).update(provisioning_status=Client.PROVISIONING_FAILED)
        mark_provisioning_failed(client_id, 'Provisioning could not be started (task queue unreachable). '
                                            'Use "Retry provisioning".')


@transaction.atomic
def retry_apply(*, sub, admin=None) -> CompanySubscription:
    """Re-apply an existing company's subscription after a failed apply."""
    sub = _lock(sub)
    if sub.provisioning_status != Sub.PROVISION_FAILED or sub.payment_status not in READY_TO_PROVISION:
        raise PaymentError('Only a failed provisioning with Paid or Waived payment can be retried here.')
    if sub.client.provisioning_status != Client.PROVISIONING_ACTIVE:
        raise PaymentError('The company itself is not set up yet — use "Retry provisioning" for the company.')
    provision(sub, admin)
    return sub


# Called by the provisioning tasks (apps.tenants.tasks) for new companies.

def mark_provisioned(client_id):
    sub = Sub.objects.filter(client_id=client_id).exclude(provisioning_status=Sub.PROVISION_SUCCESS).first()
    if sub is None or sub.provisioning_status == Sub.PROVISION_AWAITING_PAYMENT:
        return
    sub.provisioning_status = Sub.PROVISION_SUCCESS
    sub.provisioning_error = ''
    sub.provisioned_at = timezone.now()
    sub.pending_admin_email = ''
    sub.save(update_fields=['provisioning_status', 'provisioning_error', 'provisioned_at', 'pending_admin_email',
                            'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_PROVISIONED, None, 'Company set up with the subscribed modules.')


def mark_provisioning_failed(client_id, message='Company setup failed. Use "Retry provisioning".'):
    sub = Sub.objects.filter(client_id=client_id, provisioning_status=Sub.PROVISION_PENDING).first()
    if sub is not None:
        _provision_failed(sub, None, message)
