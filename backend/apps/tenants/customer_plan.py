"""
Company Settings → Plan Details: what the logged-in company has purchased,
which modules are included / enabled, how other public plans compare, and
its payment history. Read-only — built from the existing records:

  * CompanySubscription — the plan snapshot taken at assignment (the actual
    purchased terms, even if the plan was edited later), period, prices,
    payment status;
  * subscriptions.effective_modules — plan modules + dependencies + this
    company's extras − its removals (what the plan entitles);
  * access.visible_modules — what the company's users can actually use now
    (the same answer as the API gate and the login token);
  * billing.payment_totals / SubscriptionPayment — amounts and history;
  * modules.FEATURES — the one feature catalogue (labels, descriptions);
  * pricing.plan_charge — estimates for other plans.

Never shown here: admin notes, provisioning errors, who recorded / confirmed
payments, rejection reasons, receipts, rejected payments, overrides as raw
lists, or whether the plan was edited after assignment.
"""
from __future__ import annotations

from django.utils import timezone

from apps.tenants.access import visible_modules
from apps.tenants.billing import payment_totals
from apps.tenants.models import CompanySubscription, SubscriptionPayment, SubscriptionPlan
from apps.tenants.modules import CORE, COMING_SOON, DISPLAY, FEATURES, FEATURES_BY_KEY, MODULE
from apps.tenants.pricing import MONTHS, plan_charge
from apps.tenants.subscriptions import effective_modules, preview_modules

Sub = CompanySubscription

_ACTIVATION = {
    Sub.PROVISION_SUCCESS: 'active',
    Sub.PROVISION_AWAITING_PAYMENT: 'awaiting_payment',
    Sub.PROVISION_PENDING: 'setting_up',
    Sub.PROVISION_FAILED: 'setting_up',          # the error itself stays internal
}


def _money(d) -> str | None:
    return None if d is None else f'{d:.2f}'


def _labels(keys, kind) -> list[dict]:
    return [{'key': k, 'label': FEATURES_BY_KEY[k]['label'], 'description': FEATURES_BY_KEY[k]['description']}
            for k in keys if k in FEATURES_BY_KEY and FEATURES_BY_KEY[k]['kind'] == kind]


def _module_rows(sub, enabled: set) -> list[dict]:
    """One row per switchable module: how it is included and whether it is on."""
    plan = set(sub.plan_features or []) if sub else set()
    extra = set(sub.extra_modules or []) if sub else set()
    removed = set(sub.removed_modules or []) if sub else set()
    included = set(effective_modules(sub)) if sub else set()
    waiting = bool(sub) and sub.provisioning_status != Sub.PROVISION_SUCCESS
    rows = []
    for f in FEATURES:
        if f['kind'] != MODULE:
            continue
        key = f['key']
        if key in included:
            if key in extra and key not in plan:
                source = 'added'                  # added for this company
            elif key in plan:
                source = 'plan'
            else:
                source = 'dependency'             # needed by another included module
        elif key in plan and key in removed:
            source = 'removed'                    # in the plan, removed for this company
        else:
            source = 'not_included'
        on = key in enabled
        if on:
            access = 'enabled'
        elif key in included and waiting:
            access = 'pending'                    # switches on once payment is confirmed
        else:
            access = 'off'
        required_by = sorted(FEATURES_BY_KEY[m]['label'] for m in included
                             if key in FEATURES_BY_KEY.get(m, {}).get('depends_on', [])) if source == 'dependency' else []
        rows.append({'key': key, 'label': f['label'], 'description': f['description'], 'category': f['category'],
                     'included': key in included, 'enabled': on, 'source': source, 'access': access,
                     'required_by': required_by})
    return rows


def _current(sub) -> dict:
    today = timezone.localdate()
    totals = payment_totals(sub)
    ended = bool(sub.ends_on and sub.ends_on < today)
    return {
        'plan_name': sub.plan_name,
        'plan_code': sub.plan.code if sub.plan_id else '',
        'description': sub.plan.description if sub.plan_id else '',
        'billing_period': sub.billing_period,
        'starts_on': sub.starts_on.isoformat() if sub.starts_on else None,
        'ends_on': sub.ends_on.isoformat() if sub.ends_on else None,
        'period_ended': ended,
        'days_left': (sub.ends_on - today).days if sub.ends_on and not ended else None,
        'status': sub.status,
        'activation': _ACTIVATION.get(sub.provisioning_status, 'setting_up'),
        'payment_status': sub.payment_status,
        'employee_count': sub.employee_count,
        'price_per_employee': _money(sub.price_per_employee),
        'currency': sub.currency,
        'gst_rate': _money(sub.gst_rate),
        'gst_inclusive': sub.gst_inclusive,
        'total_amount': _money(sub.amount_due),
        'amount_paid': _money(totals['received']),
        'amount_pending_confirmation': _money(totals['pending']),
        'amount_outstanding': _money(totals['outstanding']),
        'features': _labels(sub.plan_features or [], DISPLAY),
    }


def _payments(sub) -> list[dict]:
    shown = {SubscriptionPayment.STATUS_VERIFIED: 'confirmed', SubscriptionPayment.STATUS_RECORDED: 'awaiting_confirmation'}
    return [{'paid_on': p.paid_on.isoformat(), 'amount': _money(p.amount), 'currency': p.currency,
             'method': p.get_method_display(), 'reference': p.reference, 'status': shown[p.status]}
            for p in sorted(sub.payments.all(), key=lambda p: (p.paid_on, p.created_at), reverse=True)
            if p.status in shown]


def _other_plans(sub, current_modules: set, employee_count) -> list[dict]:
    plans = (SubscriptionPlan.objects.filter(status=SubscriptionPlan.STATUS_ACTIVE, is_public=True, is_legacy=False)
             .order_by('display_order', 'price_per_employee'))
    if sub and sub.plan_id:
        plans = plans.exclude(pk=sub.plan_id)
    out = []
    for plan in plans:
        modules = set(preview_modules(plan))
        estimates = []
        fits = True
        if employee_count:
            if (plan.min_employees and employee_count < plan.min_employees) or (
                    plan.max_employees and employee_count > plan.max_employees):
                fits = False
            for period in plan.billing_periods or ['monthly']:
                if period in MONTHS:
                    c = plan_charge(plan, employee_count, period)
                    estimates.append({'billing_period': period, 'total': _money(c['total']),
                                      'subtotal': _money(c['subtotal']), 'gst_amount': _money(c['gst_amount'])})
        out.append({
            'name': plan.name, 'code': plan.code, 'description': plan.description,
            'price_per_employee': _money(plan.price_per_employee), 'currency': plan.currency,
            'gst_rate': _money(plan.gst_rate), 'gst_inclusive': plan.gst_inclusive,
            'billing_periods': plan.billing_periods or [], 'min_employees': plan.min_employees,
            'max_employees': plan.max_employees,
            'modules': sorted(modules),
            'additional_modules': sorted(modules - current_modules),
            'modules_not_included': sorted(current_modules - modules),
            'features': _labels(plan.features or [], DISPLAY),
            'estimate_employee_count': employee_count, 'fits_employee_count': fits, 'estimates': estimates,
        })
    return out


def plan_details(client) -> dict:
    sub = (Sub.objects.filter(client=client).select_related('plan').prefetch_related('payments').first())
    enabled = set(visible_modules(client))
    current_modules = set(effective_modules(sub)) if sub else enabled
    employee_count = (sub.employee_count if sub and sub.employee_count else None) or client.expected_employee_count
    return {
        'has_plan': sub is not None,
        'current': _current(sub) if sub else None,
        'modules': _module_rows(sub, enabled),
        'enabled_modules': sorted(enabled),
        'always_included': _labels([f['key'] for f in FEATURES], CORE),
        'coming_soon': _labels([f['key'] for f in FEATURES], COMING_SOON),
        'payments': _payments(sub) if sub else [],
        'other_plans': _other_plans(sub, current_modules, employee_count),
    }
