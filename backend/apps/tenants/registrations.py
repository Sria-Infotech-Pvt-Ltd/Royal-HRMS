"""
Website registration workflow:

  quote()                 amount from the saved plan (server-side only)
  create_registration()   validate, save (payment pending), create a gateway
                          order when a gateway is configured, notify admins
  record_payment_event()  the ONLY way a registration becomes paid — called
                          with a signature-verified gateway event (Priority 5)
  approve()               paid + pending only, row-locked: create the company
                          with the existing provisioning (create_pending_client)
                          and assign the subscription with the same service as
                          manual assignment. The caller queues
                          finish_provisioning_task after commit.
  reject()                pending only, reason required; a paid registration is
                          flagged for refund per the approved policy
"""
from __future__ import annotations

import calendar
import re
import secrets
import string
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.tenants.models import (
    Client, CompanyRegistration, CompanySubscription, PaymentTransaction, PlatformAdmin, PlatformNotification,
    SubscriptionPlan,
)
from apps.tenants.payments import VerifiedPayment, get_gateway, to_minor
from apps.tenants.services import CompanyCodeTaken, create_pending_client
from apps.tenants.modules import resolve_modules
from apps.tenants.subscriptions import apply_subscription, assign_subscription

CODE_RE = re.compile(r'^[A-Z][A-Z0-9]{2,19}$')
RESERVED_CODES = {'PUBLIC', 'ADMIN', 'PLATFORM', 'ROYAL', 'ROYALHRMS', 'TEST', 'SYSTEM', 'API', 'WWW'}
MONTHS = {'monthly': 1, 'yearly': 12}
OPEN_STATUSES = (CompanyRegistration.APPROVAL_PENDING, CompanyRegistration.APPROVAL_APPROVED)


class RegistrationError(Exception):
    """Caller-fixable problem (shown to the customer / Platform Admin)."""


# ── Quote ─────────────────────────────────────────────────────────────────────

def public_plans():
    return SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE, is_public=True, is_legacy=False)


def quote(plan: SubscriptionPlan, employee_count: int, billing_period: str) -> dict:
    if billing_period not in MONTHS:
        raise RegistrationError('Billing period must be monthly or yearly.')
    if plan.billing_periods and billing_period not in plan.billing_periods:
        raise RegistrationError(f'The {plan.name} plan is not offered {billing_period}.')
    if employee_count < 1:
        raise RegistrationError('Employee count must be at least 1.')
    if plan.min_employees and employee_count < plan.min_employees:
        raise RegistrationError(f'The {plan.name} plan is for at least {plan.min_employees} employees.')
    if plan.max_employees and employee_count > plan.max_employees:
        raise RegistrationError(f'The {plan.name} plan is for up to {plan.max_employees} employees.')
    from apps.tenants.pricing import plan_charge
    amounts = plan_charge(plan, employee_count, billing_period)
    return {'plan_name': plan.name, 'plan_features': list(plan.features or []),
            'price_per_employee': plan.price_per_employee, 'months': amounts['months'],
            'subtotal': amounts['subtotal'], 'gst_rate': plan.gst_rate, 'gst_inclusive': plan.gst_inclusive,
            'gst_amount': amounts['gst_amount'], 'total': amounts['total'], 'currency': plan.currency}


# ── Create ────────────────────────────────────────────────────────────────────

def normalise_code(code: str) -> str:
    code = (code or '').strip().upper()
    if not CODE_RE.match(code):
        raise RegistrationError('Company code must be 3–20 letters or digits, starting with a letter.')
    if code in RESERVED_CODES:
        raise RegistrationError('This company code is reserved. Choose another.')
    return code


def code_available(code: str, exclude_registration=None) -> bool:
    if Client.objects.filter(company_code__iexact=code).exists():
        return False
    open_regs = CompanyRegistration.objects.filter(company_code__iexact=code, approval_status__in=OPEN_STATUSES)
    if exclude_registration is not None:
        open_regs = open_regs.exclude(pk=exclude_registration.pk)
    return not open_regs.exists()


def _new_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        ref = f'RH{timezone.now():%y%m}-' + ''.join(secrets.choice(alphabet) for _ in range(6))
        if not CompanyRegistration.objects.filter(reference=ref).exists():
            return ref
    raise RegistrationError('Could not generate a reference — please try again.')


def notify_admins(kind: str, title: str, message: str = '', link: str = '') -> None:
    PlatformNotification.objects.bulk_create([
        PlatformNotification(recipient=a, kind=kind, title=title, message=message, link=link)
        for a in PlatformAdmin.objects.filter(is_active=True)
    ])


def create_registration(*, plan: SubscriptionPlan, data: dict, ip: str | None) -> tuple[CompanyRegistration, dict]:
    """Returns (registration, payment) — payment is {'available': False} until
    a gateway is configured, else the order's public checkout values."""
    code = normalise_code(data['company_code'])
    with transaction.atomic():
        # Serialise registrations for the same code (no duplicate open sign-ups).
        if not code_available(code):
            raise RegistrationError('This company code is already taken. Choose another.')
        amounts = quote(plan, data['employee_count'], data['billing_period'])
        reg = CompanyRegistration.objects.create(
            reference=_new_reference(), company_name=data['company_name'].strip(), company_code=code,
            contact_name=data['contact_name'].strip(), admin_email=data['admin_email'].strip().lower(),
            contact_phone=data['contact_phone'].strip(), address=data.get('address', '').strip(),
            gstin=data.get('gstin', '').strip().upper(), employee_count=data['employee_count'], plan=plan,
            billing_period=data['billing_period'], terms_accepted_at=timezone.now(), signup_ip=ip, **amounts,
        )
    notify_admins('registration_received', f'New registration {reg.reference}',
                  f'{reg.company_name} — {reg.plan_name}, {reg.employee_count} employees. Waiting for payment.',
                  link='/platform-admin/saas/registrations')
    return reg, start_payment(reg)


def start_payment(reg: CompanyRegistration) -> dict:
    gateway = get_gateway()
    if gateway is None:
        return {'available': False,
                'message': 'Online payment is not available yet. Our team will contact you to complete payment.'}
    order = gateway.create_order(reg)
    if order['amount_minor'] != to_minor(reg.total) or order['currency'] != reg.currency:
        raise RegistrationError('Payment order does not match the registration amount.')
    PaymentTransaction.objects.create(registration=reg, gateway=gateway.name, order_id=order['order_id'],
                                      amount_minor=order['amount_minor'], currency=order['currency'])
    return {'available': True, 'gateway': gateway.name, **order['checkout']}


# ── Payment (verified gateway events only) ────────────────────────────────────

@transaction.atomic
def record_payment_event(event: VerifiedPayment, gateway_name: str) -> CompanyRegistration | None:
    """Apply a signature-verified gateway event. Idempotent (event_id and
    payment_id are unique); the amount and currency must match the order."""
    if event.event_id and PaymentTransaction.objects.filter(event_id=event.event_id).exists():
        return None                                              # duplicate delivery
    txn = (PaymentTransaction.objects.select_for_update().select_related('registration')
           .filter(gateway=gateway_name, order_id=event.order_id).first())
    if txn is None:
        raise RegistrationError(f'Unknown order {event.order_id}.')
    if event.amount_minor != txn.amount_minor or event.currency != txn.currency:
        txn.status, txn.failure_reason = PaymentTransaction.STATUS_FAILED, 'Amount or currency mismatch.'
        txn.event_id = event.event_id or None
        txn.save(update_fields=['status', 'failure_reason', 'event_id', 'updated_at'])
        raise RegistrationError('Payment amount or currency does not match the order.')
    reg = CompanyRegistration.objects.select_for_update().get(pk=txn.registration_id)
    txn.event_id = event.event_id or None
    if event.status == PaymentTransaction.STATUS_PAID:
        if txn.status == PaymentTransaction.STATUS_PAID:
            return reg
        txn.status, txn.payment_id = PaymentTransaction.STATUS_PAID, event.payment_id
        txn.save(update_fields=['status', 'payment_id', 'event_id', 'updated_at'])
        if reg.payment_status != CompanyRegistration.PAYMENT_PAID:
            reg.payment_status, reg.paid_at = CompanyRegistration.PAYMENT_PAID, timezone.now()
            reg.save(update_fields=['payment_status', 'paid_at', 'updated_at'])
            notify_admins('registration_paid', f'Payment received — {reg.reference}',
                          f'{reg.company_name} paid {reg.currency} {reg.total}. Waiting for your approval.',
                          link='/platform-admin/saas/registrations')
    else:
        txn.status, txn.failure_reason = PaymentTransaction.STATUS_FAILED, event.failure_reason[:255]
        txn.save(update_fields=['status', 'failure_reason', 'event_id', 'updated_at'])
        if reg.payment_status == CompanyRegistration.PAYMENT_PENDING:
            reg.payment_status = CompanyRegistration.PAYMENT_FAILED
            reg.save(update_fields=['payment_status', 'updated_at'])
    return reg


# ── Review ────────────────────────────────────────────────────────────────────

def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@transaction.atomic
def approve(*, registration_id, admin, company_code: str | None = None) -> CompanyRegistration:
    """Paid + pending only. Creates the company (pending provisioning) and its
    subscription in one transaction; the caller queues provisioning after commit."""
    reg = CompanyRegistration.objects.select_for_update().select_related('plan').get(pk=registration_id)
    if reg.approval_status != CompanyRegistration.APPROVAL_PENDING:
        raise RegistrationError(f'This registration is already {reg.get_approval_status_display().lower()}.')
    if reg.payment_status != CompanyRegistration.PAYMENT_PAID:
        raise RegistrationError('Only a registration with a verified payment can be approved.')
    if company_code:
        reg.company_code = normalise_code(company_code)
    if not code_available(reg.company_code, exclude_registration=reg):
        raise RegistrationError(f'Company code {reg.company_code} is taken — approve with a different code.')
    modules = resolve_modules(reg.plan_features)
    try:
        client = create_pending_client(
            company_code=reg.company_code, company_name=reg.company_name, modules=modules,
            contact_name=reg.contact_name, contact_phone=reg.contact_phone, address=reg.address, gstin=reg.gstin,
            expected_employee_count=reg.employee_count, contract_start_date=timezone.localdate(),
        )
    except CompanyCodeTaken:
        raise RegistrationError(f'Company code {reg.company_code} is taken — approve with a different code.')
    starts = timezone.localdate()
    sub = assign_subscription(
        client=client, plan=reg.plan, starts_on=starts, ends_on=_add_months(starts, reg.months),
        employee_count=reg.employee_count, billing_period=reg.billing_period,
        source=CompanySubscription.SOURCE_WEBSITE, admin=admin, notes=f'Website registration {reg.reference}',
        apply=False,
    )
    # The customer gets what they paid for at registration (price and
    # features), even if the plan was edited since.
    sub.price_per_employee, sub.gst_rate, sub.gst_inclusive = reg.price_per_employee, reg.gst_rate, reg.gst_inclusive
    sub.plan_features = list(reg.plan_features)
    # Approval requires payment_status 'paid', which only a verified gateway
    # payment can set (record_payment_event) — so the subscription is paid.
    sub.payment_status, sub.amount_due = CompanySubscription.PAYMENT_PAID, reg.total
    sub.save(update_fields=['price_per_employee', 'gst_rate', 'gst_inclusive', 'plan_features', 'payment_status',
                            'amount_due', 'updated_at'])
    apply_subscription(client)
    reg.approval_status, reg.client = CompanyRegistration.APPROVAL_APPROVED, client
    reg.reviewed_by, reg.reviewed_at = admin, timezone.now()
    reg.save(update_fields=['company_code', 'approval_status', 'client', 'reviewed_by', 'reviewed_at', 'updated_at'])
    return reg


@transaction.atomic
def reject(*, registration_id, admin, reason: str) -> CompanyRegistration:
    reason = (reason or '').strip()
    if not reason:
        raise RegistrationError('Enter a reason for rejecting.')
    reg = CompanyRegistration.objects.select_for_update().get(pk=registration_id)
    if reg.approval_status != CompanyRegistration.APPROVAL_PENDING:
        raise RegistrationError(f'This registration is already {reg.get_approval_status_display().lower()}.')
    reg.approval_status, reg.rejection_reason = CompanyRegistration.APPROVAL_REJECTED, reason[:2000]
    reg.reviewed_by, reg.reviewed_at = admin, timezone.now()
    if reg.payment_status == CompanyRegistration.PAYMENT_PAID:
        reg.refund_status = CompanyRegistration.REFUND_PENDING     # handled per the approved refund policy
    reg.save(update_fields=['approval_status', 'rejection_reason', 'reviewed_by', 'reviewed_at', 'refund_status',
                            'updated_at'])
    return reg
