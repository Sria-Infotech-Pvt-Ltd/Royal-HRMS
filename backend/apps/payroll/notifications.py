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

    def _send():
        try:
            from apps.accounts.utils import send_template_email
            send_template_email(
                recipient_email=user.email,
                template_name=template_name,
                context={**context, 'company_name': _company_name()},
            )
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
