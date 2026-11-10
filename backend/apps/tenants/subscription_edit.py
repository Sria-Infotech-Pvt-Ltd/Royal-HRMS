"""
Edit a company's subscription after assignment (Platform Admin):
plan, employee count, billing period, start / end date, notes and the
subscription amount.

The amount is either
  * automatic — the plan's price per employee x employees x months in the
    billing period, + GST (or GST included), via apps.tenants.pricing.charge;
  * manual — an adjustment entered by the admin, with a required reason.
When no amount mode is given, the amount is recalculated only if something it
depends on (plan, employees, billing period) changed, so editing notes or
dates never overwrites a manual amount.

Payments are never changed: the payment status is re-derived from the
confirmed payments against the new amount (apps.tenants.billing), exactly as
for a plan change, and modules follow the existing rules (applied only once
payment is settled). Every saved edit writes one "edited" history entry.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.tenants import validators
from apps.tenants.models import CompanySubscription, SubscriptionHistory, SubscriptionPayment, SubscriptionPlan
from apps.tenants.pricing import charge
from apps.tenants.subscriptions import (
    SubscriptionError, _check_dates, _check_plan, _history, apply_subscription, effective_modules, module_diff,
    preview_modules, snapshot_fields, summary,
)

EVENT_EDITED = 'edited'
AUTO, MANUAL = 'auto', 'manual'
LABELS = {
    'plan_name': 'Plan', 'employee_count': 'Employees', 'billing_period': 'Billing period',
    'starts_on': 'Start date', 'ends_on': 'End date', 'notes': 'Notes', 'amount_due': 'Subscription amount',
}
PRICING_INPUTS = ('plan', 'employee_count', 'billing_period')


def _value(sub, field):
    v = getattr(sub, field)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return f'{v:.2f}'
    return v if v not in ('', None) else None


def _calculated(sub) -> dict | None:
    if not sub.employee_count:
        return None
    c = charge(sub.price_per_employee, sub.gst_rate, sub.gst_inclusive, sub.employee_count, sub.billing_period)
    return {
        'employee_count': sub.employee_count, 'billing_period': sub.billing_period or 'monthly',
        'months': c['months'], 'price_per_employee': f'{sub.price_per_employee:.2f}', 'currency': sub.currency,
        'subtotal': f'{c["subtotal"]:.2f}', 'gst_rate': f'{sub.gst_rate:.2f}', 'gst_inclusive': sub.gst_inclusive,
        'gst_amount': f'{c["gst_amount"]:.2f}', 'total': f'{c["total"]:.2f}',
    }


def _received_pending(sub) -> tuple[Decimal, Decimal]:
    received = pending = Decimal('0')
    for p in SubscriptionPayment.objects.filter(subscription=sub).only('amount', 'status'):
        if p.status == SubscriptionPayment.STATUS_VERIFIED:
            received += p.amount
        elif p.status == SubscriptionPayment.STATUS_RECORDED:
            pending += p.amount
    return received, pending


def _status_for(sub, amount, received) -> str:
    """apps.tenants.billing.derive_payment_status for a not-yet-saved amount."""
    if sub.payment_status == CompanySubscription.PAYMENT_WAIVED or sub.source == CompanySubscription.SOURCE_WEBSITE:
        return sub.payment_status
    if received > 0:
        return (CompanySubscription.PAYMENT_PAID if amount is not None and received >= amount
                else CompanySubscription.PAYMENT_PARTIAL)
    return sub.payment_status


def _outstanding(status, amount, received):
    if status == CompanySubscription.PAYMENT_WAIVED:
        return Decimal('0')
    return None if amount is None else max(amount - received, Decimal('0'))


def _money(amount, currency) -> str:
    return 'not set' if amount is None else f'{amount:,.2f} {currency}'


def _fit(plan: SubscriptionPlan, sub) -> None:
    try:
        validators.employee_count_in_plan(sub.employee_count, plan)
    except ValidationError as exc:
        raise SubscriptionError(str(exc.detail[0])) from None
    if sub.billing_period and plan.billing_periods and sub.billing_period not in plan.billing_periods:
        raise SubscriptionError(f'The {plan.name} plan is billed {" or ".join(plan.billing_periods)} only.')


def _apply(sub, data) -> dict:
    """Apply the edit to `sub` in memory and describe it. Raises SubscriptionError."""
    before = {f: _value(sub, f) for f in LABELS}
    old_amount, old_status, old_modules = sub.amount_due, sub.payment_status, effective_modules(sub)

    plan = data.get('plan')
    plan_changed = plan is not None and plan.pk != sub.plan_id
    if plan_changed:
        _check_plan(plan)
        if sub.provisioning_status == CompanySubscription.PROVISION_PENDING:
            raise SubscriptionError('Company setup is still in progress — change the plan once it has finished.')
        for field, value in snapshot_fields(plan).items():
            setattr(sub, field, value)
    for field in ('employee_count', 'billing_period', 'starts_on', 'ends_on', 'notes'):
        if field in data:
            setattr(sub, field, data[field])
    _check_dates(sub.starts_on, sub.ends_on)
    pricing_changed = plan_changed or any(
        f in data and before[f] != _value(sub, f) for f in ('employee_count', 'billing_period'))
    if plan_changed or pricing_changed:
        _fit(plan if plan_changed else sub.plan, sub)

    # Subscription amount.
    mode = data.get('amount_mode') or (AUTO if pricing_changed else None)
    calculated = _calculated(sub)
    reason = (data.get('amount_reason') or '').strip()
    if mode == AUTO:
        if calculated is None:
            raise SubscriptionError('Enter the employee count so the subscription amount can be calculated '
                                    '(or enter the amount manually).')
        sub.amount_due = Decimal(calculated['total'])
    elif mode == MANUAL:
        amount = data.get('amount_due')
        if amount is None or amount <= 0:
            raise SubscriptionError('Enter a subscription amount above zero (use "Waive payment" for no charge).')
        if not reason:
            raise SubscriptionError('Give a reason for the manual amount — it is kept in the subscription history.')
        sub.amount_due = amount

    changes = [{'field': f, 'label': LABELS[f], 'from': before[f], 'to': _value(sub, f)}
               for f in LABELS if before[f] != _value(sub, f)]
    if not changes:
        raise SubscriptionError('Nothing to change — edit at least one field.')

    received, pending = _received_pending(sub)
    new_status = _status_for(sub, sub.amount_due, received) if sub.amount_due != old_amount else old_status
    new_modules = preview_modules(sub.plan, sub.extra_modules or [], sub.removed_modules or []) \
        if plan_changed else old_modules
    diff = module_diff(old_modules, new_modules)
    out_before = _outstanding(old_status, old_amount, received)
    out_after = _outstanding(new_status, sub.amount_due, received)

    warnings = []
    if diff['removed']:
        warnings.append(f'Switched off on the new plan: {", ".join(diff["removed"])} — the company loses access '
                        'once the plan is applied.')
    if sub.provisioning_status == CompanySubscription.PROVISION_AWAITING_PAYMENT and plan_changed:
        warnings.append('Payment is not settled yet — the new plan\'s modules are applied once it is confirmed '
                        'or waived.')
    if old_status == CompanySubscription.PAYMENT_PAID and new_status == CompanySubscription.PAYMENT_PARTIAL:
        warnings.append(f'Payment status changes from Paid to Partially paid — {_money(out_after, sub.currency)} '
                        'more to collect.')
    if new_status == CompanySubscription.PAYMENT_PAID and old_status != CompanySubscription.PAYMENT_PAID:
        warnings.append('Confirmed payments cover the new amount — the subscription becomes Paid'
                        + (' and its modules are applied.' if sub.provisioning_status
                           == CompanySubscription.PROVISION_AWAITING_PAYMENT else '.'))
    if sub.amount_due is not None and received > sub.amount_due:
        warnings.append(f'Confirmed payments ({_money(received, sub.currency)}) are more than the new amount — '
                        f'{_money(received - sub.amount_due, sub.currency)} will show as overpaid. '
                        'Payments are not changed.')
    if pending:
        warnings.append(f'{_money(pending, sub.currency)} awaiting confirmation is not counted until confirmed.')
    if sub.payment_status == CompanySubscription.PAYMENT_WAIVED and sub.amount_due != old_amount:
        warnings.append('Payment is waived — the amount is recorded, but nothing is outstanding.')
    if sub.source == CompanySubscription.SOURCE_WEBSITE and sub.amount_due != old_amount:
        warnings.append('Website sign-up paid online — its payment status is not recalculated.')

    return {
        'changes': changes, 'plan_changed': plan_changed,
        'amount': {'from': before['amount_due'], 'to': _value(sub, 'amount_due'),
                   'mode': mode or 'unchanged', 'reason': reason if mode == MANUAL else '',
                   'calculated': calculated},
        'payments': {'received': f'{received:.2f}', 'pending': f'{pending:.2f}',
                     'outstanding_before': None if out_before is None else f'{out_before:.2f}',
                     'outstanding_after': None if out_after is None else f'{out_after:.2f}',
                     'overpaid_after': f'{max(received - sub.amount_due, Decimal("0")):.2f}'
                     if sub.amount_due is not None else '0.00'},
        'payment_status': {'from': old_status, 'to': new_status},
        'modules': diff, 'warnings': warnings,
    }


def preview_edit(sub: CompanySubscription, data: dict) -> dict:
    """What `edit_subscription` would do. Saves nothing."""
    copy = CompanySubscription.objects.select_related('plan', 'client').get(pk=sub.pk)
    return _apply(copy, data)


def _note(result, currency) -> str:
    parts = []
    for c in result['changes']:
        if c['field'] == 'notes':
            parts.append('Notes updated')
            continue
        if c['field'] == 'amount_due':
            src = result['amount']
            how = ('calculated: ' + _calc_text(src['calculated'])) if src['mode'] == AUTO else \
                f'manual — {src["reason"]}' if src['mode'] == MANUAL else ''
            parts.append(f'{c["label"]}: {_fmt(c["from"], currency)} → {_fmt(c["to"], currency)}'
                         + (f' ({how})' if how else ''))
            continue
        parts.append(f'{c["label"]}: {c["from"] if c["from"] is not None else "—"} → '
                     f'{c["to"] if c["to"] is not None else "—"}')
    return '; '.join(parts)


def _fmt(v, currency):
    return 'not set' if v is None else f'{Decimal(v):,.2f} {currency}'


def _calc_text(c) -> str:
    if not c:
        return ''
    rate = f'{Decimal(c["gst_rate"]):f}'.rstrip('0').rstrip('.')
    gst = f'GST {rate}% included' if c['gst_inclusive'] else f'+ GST {rate}%'
    return f'{c["employee_count"]} × {c["price_per_employee"]} × {c["months"]} month(s) {gst}'


@transaction.atomic
def edit_subscription(*, sub: CompanySubscription, data: dict, admin=None, note: str = '') -> tuple[CompanySubscription, dict]:
    sub = CompanySubscription.objects.select_for_update().select_related('plan', 'client').get(pk=sub.pk)
    before = summary(sub)
    old_amount = sub.amount_due
    result = _apply(sub, data)
    sub.updated_by = admin
    sub.save()
    text = _note(result, sub.currency) + (f' — {note}' if note else '')
    _history(sub, EVENT_EDITED, before, admin, text[:1000])
    if result['plan_changed'] and sub.provisioning_status != CompanySubscription.PROVISION_AWAITING_PAYMENT:
        apply_subscription(sub.client)
    if sub.amount_due != old_amount and sub.source != CompanySubscription.SOURCE_WEBSITE:
        from apps.tenants import billing
        billing.refresh_payment_status(sub, admin)     # payments untouched; may apply modules when now Paid
    return sub, result
