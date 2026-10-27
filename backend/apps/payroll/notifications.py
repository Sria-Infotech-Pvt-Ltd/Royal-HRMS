"""
Payroll approval notifications — bell + email fired at the two key
gate transitions: cycle creation (notify L1 managers) and all-L1-complete
(notify HR / L2 approvers).
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _company_name() -> str:
    try:
        from apps.accounts.models import Company
        company = Company.objects.first()
        return company.company_name if company else ''
    except Exception:
        return ''


def _notify(user, title: str, message: str, ref_id: str = '') -> None:
    if not user:
        return
    try:
        from apps.notifications.models import Notification
        from apps.notifications.signals import _category_enabled, _push_live
        if not _category_enabled(user, 'payroll'):
            return
        notification = Notification.objects.create(
            user=user, title=title, message=message,
            notification_type='payroll_approval', module='payroll',
            reference_id=ref_id,
        )
        _push_live(notification)
    except Exception:
        logger.exception('Failed to create payroll notification for user %s', getattr(user, 'id', None))


def _send_email(user, template_name: str, context: dict) -> None:
    if not user or not getattr(user, 'email', ''):
        return

    # Django DB connections are thread-local — the spawned thread below gets
    # its own connection, defaulting to the public schema, completely
    # independent of whatever tenant is active on the calling thread. Capture
    # the schema now (still on the calling thread) and re-activate it inside
    # the new thread, same reasoning as apps.tenants.utils.run_in_tenant
    # (Celery tasks have exactly the same problem, one process boundary up).
    from django.db import connection
    schema_name = connection.schema_name

    def _send():
        try:
            from apps.accounts.utils import send_template_email
            from apps.tenants.utils import run_in_tenant
            run_in_tenant(schema_name, lambda: send_template_email(
                recipient_email=user.email,
                template_name=template_name,
                context={**context, 'company_name': _company_name()},
            ))
        except Exception:
            logger.exception('Failed to send payroll email "%s" to %s', template_name, user.email)

    threading.Thread(target=_send, daemon=True).start()


def notify_l1_approval_required(cycle) -> None:
    """
    Notify all branch managers that their attendance sign-off is needed.
    Called immediately when a payroll cycle is created.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    manager_qs = User.objects.filter(
        is_active=True, role__can_manage_team=True,
    ).select_related('role')
    if cycle.branch:
        manager_qs = manager_qs.filter(branch=cycle.branch.branch_name)

    month_label = cycle.cycle_start.strftime('%B %Y')
    ref_id = str(cycle.id)

    for manager in manager_qs:
        _notify(
            manager,
            'Payroll Approval Required',
            f'Attendance sign-off needed for {month_label} payroll. Please review and approve your team\'s attendance.',
            ref_id,
        )
        _send_email(manager, 'payroll_l1_approval_required', {
            'manager_name': manager.full_name or manager.email,
            'month':        month_label,
            'cycle_start':  cycle.cycle_start.strftime('%d %b %Y'),
            'cycle_end':    cycle.cycle_end.strftime('%d %b %Y'),
            'pay_date':     cycle.pay_date.strftime('%d %b %Y'),
        })


def notify_l2_approval_required(cycle) -> None:
    """
    Notify all payroll.edit holders in the branch that all L1 managers have
    approved and the cycle is ready for HR sign-off.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    hr_qs = User.objects.filter(
        is_active=True,
        role__role_permissions__permission__codename='payroll.edit',
    ).distinct()
    if cycle.branch:
        hr_qs = hr_qs.filter(branch=cycle.branch.branch_name)

    month_label = cycle.cycle_start.strftime('%B %Y')
    ref_id = str(cycle.id)

    for hr_user in hr_qs:
        _notify(
            hr_user,
            'Payroll Ready for HR Sign-off',
            f'All managers have approved attendance for {month_label}. The cycle is ready for your L2 sign-off.',
            ref_id,
        )
        _send_email(hr_user, 'payroll_l2_approval_required', {
            'hr_name':     hr_user.full_name or hr_user.email,
            'month':       month_label,
            'cycle_start': cycle.cycle_start.strftime('%d %b %Y'),
            'cycle_end':   cycle.cycle_end.strftime('%d %b %Y'),
            'pay_date':    cycle.pay_date.strftime('%d %b %Y'),
        })


# ── Payslip queries ──────────────────────────────────────────────────────────

def query_recipients(payslip):
    """
    Who is told about a new payslip query: active payroll.edit holders who can
    resolve it — the cycle's branch staff, plus org-wide admins (settings.edit);
    every payroll.edit holder when the cycle has no branch. Same scope as the
    query list / resolve endpoints. Never the employee who raised it.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()

    qs = User.objects.filter(
        is_active=True,
        role__role_permissions__permission__codename='payroll.edit',
    ).exclude(pk=payslip.employee_id)
    branch = payslip.cycle.branch
    if branch is not None:
        admins = User.objects.filter(role__role_permissions__permission__codename='settings.edit')
        qs = qs.filter(Q(branch=branch.branch_name) | Q(pk__in=admins.values('pk')))
    return qs.distinct()


def notify_query_raised(query) -> None:
    """Bell notification to the HR recipients above. Never raises."""
    from apps.notifications.signals import _notify as _notify_user
    try:
        payslip = query.payslip
        employee = payslip.employee
        month = payslip.cycle.cycle_start.strftime('%B %Y')
        who = f'{employee.full_name} ({employee.employee_id})' if employee.employee_id else employee.full_name
        for hr_user in query_recipients(payslip):
            _notify_user(hr_user, 'Payslip Query Raised',
                         f'{who} raised a query on their {month} payslip. Review it in Payroll → Payslip Queries.',
                         'payslip_query_raised', 'payroll', str(query.id))
    except Exception:
        logger.exception('Failed to notify HR about payslip query %s', getattr(query, 'id', None))


def notify_query_resolved(query) -> None:
    """Bell notification to the employee who raised the query. Never raises."""
    from apps.notifications.signals import _notify as _notify_user
    try:
        month = query.payslip.cycle.cycle_start.strftime('%B %Y')
        _notify_user(query.raised_by, 'Payslip Query Resolved',
                     f'HR has responded to your query on the {month} payslip. See My Payslips for the resolution.',
                     'payslip_query_resolved', 'payroll', str(query.id))
    except Exception:
        logger.exception('Failed to notify employee about resolved payslip query %s', getattr(query, 'id', None))
