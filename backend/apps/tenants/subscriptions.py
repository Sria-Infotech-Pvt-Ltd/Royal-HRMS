"""
Subscriptions → module access. One path for every way a company gets a plan
(manual assignment by Platform Admin, website registration approval, the
legacy backfill):

  assign_subscription()  snapshot the plan onto the company's subscription,
                         record history, then apply_subscription()
  apply_subscription()   resolve the snapshot (+ approved overrides +
                         dependencies) into Client.enabled_modules — the
                         switches the API gate, scheduled jobs and voice
                         commands already enforce. Saving the Client
                         invalidates its cache (apps.tenants.signals).

Editing a plan never touches existing subscriptions; changing a company's
plan is an explicit change_plan().
"""
from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import connection, transaction

from apps.tenants.models import Client, CompanySubscription, SubscriptionHistory, SubscriptionPlan
from apps.tenants.modules import MODULE_FEATURES, resolve_modules


class SubscriptionError(Exception):
    """Caller-fixable problem (shown to the Platform Admin)."""


def snapshot_fields(plan: SubscriptionPlan) -> dict:
    return {
        'plan': plan, 'plan_name': plan.name, 'price_per_employee': plan.price_per_employee,
        'currency': plan.currency, 'gst_rate': plan.gst_rate, 'gst_inclusive': plan.gst_inclusive,
        'max_employees': plan.max_employees, 'plan_features': list(plan.features or []),
    }


def summary(sub: CompanySubscription | None) -> dict:
    """JSON-safe view of a subscription for history entries."""
    if sub is None:
        return {}
    return {
        'plan_code': sub.plan.code, 'plan_name': sub.plan_name, 'status': sub.status,
        'starts_on': sub.starts_on.isoformat() if sub.starts_on else None,
        'ends_on': sub.ends_on.isoformat() if sub.ends_on else None,
        'employee_count': sub.employee_count, 'billing_period': sub.billing_period or '',
        'price_per_employee': str(sub.price_per_employee),
        'modules': effective_modules(sub),
        'extra_modules': list(sub.extra_modules or []), 'removed_modules': list(sub.removed_modules or []),
        'payment_status': sub.payment_status,
        'amount_due': str(sub.amount_due) if sub.amount_due is not None else None,
        'provisioning_status': sub.provisioning_status,
    }


def effective_modules(sub: CompanySubscription) -> list[str]:
    return resolve_modules(sub.plan_features or [], sub.extra_modules or [], sub.removed_modules or [])


def preview_modules(plan: SubscriptionPlan, extra=(), removed=()) -> list[str]:
    return resolve_modules(plan.features or [], extra, removed)


def module_diff(before: list[str], after: list[str]) -> dict:
    return {'added': sorted(set(after) - set(before)), 'removed': sorted(set(before) - set(after))}


def check_overrides(extra, removed) -> tuple[list[str], list[str]]:
    extra, removed = list(extra or []), list(removed or [])
    if (extra or removed) and not getattr(settings, 'SUBSCRIPTION_ALLOW_OVERRIDES', False):
        raise SubscriptionError('Customer-specific module overrides are not enabled.')
    unknown = sorted((set(extra) | set(removed)) - MODULE_FEATURES)
    if unknown:
        raise SubscriptionError(f'Unknown module(s): {", ".join(unknown)}.')
    return sorted(set(extra)), sorted(set(removed))


def apply_subscription(client: Client) -> list[str]:
    """Write the subscription's modules into Client.enabled_modules. Returns them.

    Uses a queryset update, never client.save(): django-tenants' save()
    creates the schema and runs every migration when an existing company's
    schema doesn't exist yet (pending / failed provisioning) — that must stay
    in the background provisioning task, not happen here. The company cache
    is invalidated explicitly (update() sends no post_save signal), now and
    again after commit so no request re-caches the old modules meanwhile."""
    from django.utils import timezone

    from core.cache_service import TenantClientCacheService

    sub = CompanySubscription.objects.select_related('plan').get(client=client)
    modules = effective_modules(sub)
    if sorted(client.enabled_modules or []) != modules:
        Client.objects.filter(pk=client.pk).update(enabled_modules=modules, updated_at=timezone.now())
        client.enabled_modules = modules
        TenantClientCacheService.invalidate(client.schema_name)
        schema = client.schema_name
        transaction.on_commit(lambda: TenantClientCacheService.invalidate(schema))
    _forget_state(client.schema_name)
    return modules


def _forget_state(schema: str) -> None:
    """Drop the cached "subscription applied" flag (apps.tenants.access), now and after commit."""
    from apps.tenants.access import invalidate_subscription_state
    invalidate_subscription_state(schema)
    transaction.on_commit(lambda: invalidate_subscription_state(schema))


def _history(sub, event, before, admin, note=''):
    SubscriptionHistory.objects.create(subscription=sub, event=event, before=before, after=summary(sub),
                                       admin=admin, note=note)
    _forget_state(Client.objects.filter(pk=sub.client_id).values_list('schema_name', flat=True).first() or '')


def _check_dates(starts_on: date, ends_on: date | None):
    if ends_on is not None and ends_on < starts_on:
        raise SubscriptionError('End date cannot be before the start date.')


def _check_plan(plan: SubscriptionPlan, *, allow_legacy=False):
    if plan.status != SubscriptionPlan.STATUS_ACTIVE and not (allow_legacy and plan.is_legacy):
        raise SubscriptionError('Only active plans can be assigned.')


@transaction.atomic
def assign_subscription(*, client: Client, plan: SubscriptionPlan, starts_on: date, ends_on: date | None,
                        employee_count: int | None, billing_period: str = '', source: str,
                        admin=None, notes: str = '', extra_modules=(), removed_modules=(),
                        apply: bool = True) -> CompanySubscription:
    """Create the company's subscription (one per company)."""
    # A paid website registration keeps the plan it paid for even if the plan
    # was deactivated before approval; manual assignment needs an active plan.
    if source != CompanySubscription.SOURCE_WEBSITE:
        _check_plan(plan, allow_legacy=(source == CompanySubscription.SOURCE_LEGACY))
    _check_dates(starts_on, ends_on)
    if source != CompanySubscription.SOURCE_LEGACY:
        extra_modules, removed_modules = check_overrides(extra_modules, removed_modules)
    Client.objects.select_for_update().filter(pk=client.pk).first()
    if CompanySubscription.objects.filter(client=client).exists():
        raise SubscriptionError('This company already has a subscription — change its plan instead.')
    sub = CompanySubscription.objects.create(
        client=client, source=source, starts_on=starts_on, ends_on=ends_on, employee_count=employee_count,
        billing_period=billing_period, notes=notes, updated_by=admin,
        extra_modules=sorted(set(extra_modules)), removed_modules=sorted(set(removed_modules)),
        **snapshot_fields(plan),
    )
    _history(sub, SubscriptionHistory.EVENT_ASSIGNED, {'modules_before': sorted(client.enabled_modules or [])},
             admin, note=f'source: {source}')
    if apply:
        apply_subscription(client)
        from django.utils import timezone
        sub.provisioning_status = CompanySubscription.PROVISION_SUCCESS
        sub.provisioned_at = timezone.now()
        sub.save(update_fields=['provisioning_status', 'provisioned_at', 'updated_at'])
    return sub


@transaction.atomic
def change_plan(*, sub: CompanySubscription, plan: SubscriptionPlan, admin=None, note: str = '',
                employee_count: int | None = None) -> CompanySubscription:
    _check_plan(plan)
    sub = CompanySubscription.objects.select_for_update().select_related('plan', 'client').get(pk=sub.pk)
    before = summary(sub)
    for field, value in snapshot_fields(plan).items():
        setattr(sub, field, value)
    if employee_count is not None:
        sub.employee_count = employee_count
    # The amount due follows the new plan's price (the snapshot just taken),
    # the subscription's employee count and billing period, and GST.
    old_due = sub.amount_due
    if sub.employee_count:
        from apps.tenants.pricing import charge
        sub.amount_due = charge(sub.price_per_employee, sub.gst_rate, sub.gst_inclusive,
                                sub.employee_count, sub.billing_period)['total']
    sub.updated_by = admin
    sub.save()
    _history(sub, SubscriptionHistory.EVENT_PLAN_CHANGED, before, admin, note)
    if sub.amount_due != old_due:
        _history(sub, SubscriptionHistory.EVENT_AMOUNT_DUE_CHANGED,
                 {'amount_due': str(old_due) if old_due is not None else None}, admin,
                 f'Recalculated for {before["plan_name"]} → {sub.plan_name}: '
                 f'{old_due if old_due is not None else "not set"} → {sub.amount_due} {sub.currency}')
        if sub.source != CompanySubscription.SOURCE_WEBSITE:
            # Paid / partially paid are re-derived against the new amount.
            # (Website sign-ups were paid through the gateway — not tracked here.)
            from apps.tenants import billing
            billing.refresh_payment_status(sub, admin)
    # Not paid yet: the new plan's modules are applied when payment is settled.
    if sub.provisioning_status != CompanySubscription.PROVISION_AWAITING_PAYMENT:
        apply_subscription(sub.client)
    return sub


@transaction.atomic
def update_period(*, sub: CompanySubscription, ends_on: date | None, admin=None, note: str = '') -> CompanySubscription:
    sub = CompanySubscription.objects.select_for_update().select_related('plan').get(pk=sub.pk)
    _check_dates(sub.starts_on, ends_on)
    before = summary(sub)
    sub.ends_on = ends_on
    sub.updated_by = admin
    sub.save(update_fields=['ends_on', 'updated_by', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_EXTENDED, before, admin, note)
    return sub


@transaction.atomic
def set_status(*, sub: CompanySubscription, active: bool, admin=None, note: str = '') -> CompanySubscription:
    sub = CompanySubscription.objects.select_for_update().select_related('plan').get(pk=sub.pk)
    new = CompanySubscription.STATUS_ACTIVE if active else CompanySubscription.STATUS_INACTIVE
    if sub.status == new:
        return sub
    before = summary(sub)
    sub.status = new
    sub.updated_by = admin
    sub.save(update_fields=['status', 'updated_by', 'updated_at'])
    _history(sub, SubscriptionHistory.EVENT_ACTIVATED if active else SubscriptionHistory.EVENT_DEACTIVATED,
             before, admin, note)
    return sub


def visible_modules(enabled, client=None) -> list[str]:
    """Modules the company's users see (and the API allows) — see
    apps.tenants.access: documents / assets / wfh follow the plan exactly once
    the company's subscription is applied (or enforcement is 'on'); a company
    not yet on a plan keeps them, so it loses no menus before its backfill."""
    from apps.tenants.access import visible_modules as _visible
    return _visible(client, enabled or [])


# ─── Limits (enforced only when SUBSCRIPTION_ENFORCEMENT == 'on') ───────────

def current_subscription():
    """The active company's subscription, or None (public schema / none assigned)."""
    tenant = getattr(connection, 'tenant', None)
    pk = getattr(tenant, 'pk', None)
    if pk is None or getattr(tenant, 'schema_name', 'public') == 'public':
        return None
    return CompanySubscription.objects.filter(client_id=pk).first()


def employee_limit_problem(adding: int = 1) -> str | None:
    """A message when adding `adding` active employees would exceed the
    plan's employee limit, else None. Never deactivates anyone."""
    mode = getattr(settings, 'SUBSCRIPTION_ENFORCEMENT', 'off')
    if mode != 'on':
        return None
    sub = current_subscription()
    if sub is None or not sub.max_employees:
        return None
    from apps.accounts.models import User
    active = User.objects.filter(is_active=True).count()
    if active + adding > sub.max_employees:
        return (f'Your {sub.plan_name} plan allows up to {sub.max_employees} active employees '
                f'({active} now). Contact Royal HRMS to upgrade.')
    return None
