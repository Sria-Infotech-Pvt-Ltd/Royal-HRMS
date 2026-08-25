"""
HRMS Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db.models.functions import ExtractDay, ExtractMonth
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def reset_annual_leave_balances(self):
    """
    Annual task: runs on 1st Jan at 00:01 IST.

    For every active employee:
    - Checks each active LeavePolicy for eligibility (branch, dept, designation, service period).
    - Carries forward unused days from the previous year (capped by max_carry_forward_days).
    - Creates a new LeaveBalance for the new year.

    Idempotent: get_or_create — safe to re-run if the task fires twice.
    """
    from decimal import Decimal
    from apps.accounts.models import User
    from apps.hrms.models import CARRY_FORWARD_MANUAL, CARRY_FORWARD_UNLIMITED, LeaveBalance, LeavePolicy

    try:
        today    = timezone.localdate()
        new_year = today.year
        prev_year = new_year - 1

        active_employees = list(
            User.objects.filter(is_active=True, role__isnull=False, employee_id__isnull=False)
        )
        # Automatic task only runs policies set to automatic carry-forward mode
        policies = list(LeavePolicy.objects.filter(is_active=True).exclude(carry_forward_mode=CARRY_FORWARD_MANUAL))

        created_total = 0
        skipped_total = 0

        for employee in active_employees:
            doj           = getattr(employee, 'date_of_joining', None)
            months_served = 0
            if doj:
                months_served = (today.year - doj.year) * 12 + (today.month - doj.month)

            for policy in policies:
                if policy.minimum_service_period > 0 and months_served < policy.minimum_service_period:
                    continue

                if policy.applicable_branches and (
                    not employee.branch or employee.branch not in policy.applicable_branches
                ):
                    continue

                if policy.applicable_departments and (
                    not employee.department or employee.department not in policy.applicable_departments
                ):
                    continue

                if policy.applicable_designations and (
                    not employee.designation or employee.designation not in policy.applicable_designations
                ):
                    continue

                carry_forward = Decimal('0')
                expiry_date   = None
                if policy.can_carry_forward:
                    prev = LeaveBalance.objects.filter(
                        employee=employee, leave_type=policy.leave_type, year=prev_year,
                    ).first()
                    if prev:
                        unused = prev.total_days - prev.used_days
                        if unused > 0:
                            if policy.carry_forward_type == CARRY_FORWARD_UNLIMITED:
                                carry_forward = unused
                            elif policy.max_carry_forward_days > 0:
                                carry_forward = min(unused, Decimal(str(policy.max_carry_forward_days)))

                            if carry_forward > 0 and policy.carry_forward_expiry_days > 0:
                                expiry_date = today + timedelta(days=policy.carry_forward_expiry_days)

                _, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=policy.leave_type,
                    year=new_year,
                    defaults={
                        'total_days':               policy.annual_days + carry_forward,
                        'carried_forward':          carry_forward,
                        'carry_forward_expiry_date': expiry_date,
                    },
                )
                if created:
                    created_total += 1
                else:
                    skipped_total += 1

        result = {'year': new_year, 'created': created_total, 'skipped': skipped_total}
        logger.info('reset_annual_leave_balances completed: %s', result)
        return result
    except Exception as exc:
        logger.error('reset_annual_leave_balances error: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_birthday_wishes(self):
    """
    Daily task: for every active employee whose birthday (month + day)
    matches today —
      - send a birthday wish email (template 'birthday_wish', admin-editable
        in Settings -> Email Templates)
      - create an in-app Notification for the employee, their teammates
        (same reporting manager), and their reporting manager
      - record an AuditLog row (module='birthday') for delivery visibility
        in Settings -> Audit Logs

    Runs at 00:05 IST (configured in CELERY_BEAT_SCHEDULE).
    Gated by BirthdaySettings.is_enabled — the whole feature is a no-op
    when disabled.
    Idempotent — skips employees whose birthday_wish_sent_year already
    equals the current year, so retries and duplicate runs are safe. That
    same guard also prevents duplicate notifications/audit rows on retry.
    """
    from apps.accounts.models import BirthdaySettings, Company, EmployeeProfile
    from apps.accounts.utils import send_template_email
    from apps.hrms.birthday_utils import get_peers
    from apps.notifications.signals import _notify

    try:
        birthday_settings = BirthdaySettings.get()
        if not birthday_settings.is_enabled:
            logger.info('send_birthday_wishes skipped: feature disabled in BirthdaySettings.')
            return {'skipped_reason': 'disabled'}

        today        = timezone.localdate()
        company      = Company.objects.first()
        company_name = company.company_name if company else ''

        profiles = (
            EmployeeProfile.objects
            .select_related('user')
            .filter(
                date_of_birth__isnull=False,
                user__is_active=True,
            )
            .annotate(
                birth_month=ExtractMonth('date_of_birth'),
                birth_day=ExtractDay('date_of_birth'),
            )
            .filter(birth_month=today.month, birth_day=today.day)
        )

        sent_count    = 0
        skipped_count = 0
        failed_count  = 0

        for profile in profiles:
            if profile.birthday_wish_sent_year == today.year:
                skipped_count += 1
                continue

            employee   = profile.user
            email_addr = employee.email
            name       = employee.full_name or employee.email

            try:
                send_template_email(
                    recipient_email=email_addr,
                    template_name='birthday_wish',
                    context={
                        'employee_name': name,
                        'company_name':  company_name,
                    },
                )
                profile.birthday_wish_sent_year = today.year
                profile.save(update_fields=['birthday_wish_sent_year'])
                sent_count += 1
                logger.info('Birthday wish sent to %s (%s)', name, email_addr)
                _record_birthday_delivery(employee, 'birthday_email_sent', {'email': email_addr})
            except Exception as exc:
                failed_count += 1
                logger.exception('Failed to send birthday wish to %s (%s)', name, email_addr)
                _record_birthday_delivery(
                    employee, 'birthday_email_failed', {'email': email_addr, 'error': str(exc)},
                )
                continue

            _notify(
                employee, '🎉 Happy Birthday!',
                birthday_settings.employee_notification_template,
                'birthday', 'birthday', str(employee.id), employee,
            )

            for peer in get_peers(employee):
                _notify(
                    peer, '🎂 Team Birthday Today',
                    birthday_settings.team_notification_template.format(employee_name=name),
                    'birthday', 'birthday', str(employee.id),
                )

            if employee.reporting_manager_id:
                _notify(
                    employee.reporting_manager, '🎂 Team Birthday Today',
                    birthday_settings.manager_notification_template.format(employee_name=name),
                    'birthday', 'birthday', str(employee.id),
                )

        result = {
            'date':    today.isoformat(),
            'sent':    sent_count,
            'skipped': skipped_count,
            'failed':  failed_count,
        }
        logger.info('send_birthday_wishes completed: %s', result)
        return result
    except Exception as exc:
        logger.error('send_birthday_wishes task error: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


def _record_birthday_delivery(employee, action: str, changes: dict) -> None:
    """Log a birthday email delivery attempt to the shared AuditLog table so
    it surfaces in the existing System Admin -> Audit Logs page (?module=birthday)
    without needing a dedicated log model/UI."""
    try:
        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=employee, action=action, module='birthday',
            object_id=str(employee.id), changes=changes,
        )
    except Exception:
        logger.exception('Failed to record birthday delivery audit log for %s', employee.id)
