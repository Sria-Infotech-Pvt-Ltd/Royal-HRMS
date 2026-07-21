"""
HRMS Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging

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
    try:
        from decimal import Decimal
        from apps.accounts.models import User
        from apps.hrms.models import LeaveBalance, LeavePolicy

        today    = timezone.localdate()
        new_year = today.year
        prev_year = new_year - 1

        active_employees = list(
            User.objects.filter(is_active=True, role__isnull=False, employee_id__isnull=False)
        )
        policies = list(LeavePolicy.objects.filter(is_active=True))

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
                if policy.can_carry_forward and policy.max_carry_forward_days > 0:
                    prev = LeaveBalance.objects.filter(
                        employee=employee, leave_type=policy.leave_type, year=prev_year,
                    ).first()
                    if prev:
                        unused = prev.total_days - prev.used_days
                        if unused > 0:
                            carry_forward = min(unused, Decimal(str(policy.max_carry_forward_days)))

                _, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=policy.leave_type,
                    year=new_year,
                    defaults={
                        'total_days':      policy.annual_days + carry_forward,
                        'carried_forward': carry_forward,
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
    Daily task: send a birthday wish email to every active employee
    whose birthday (month + day) matches today.

    Runs at 9:00 AM IST (configured in CELERY_BEAT_SCHEDULE).
    Idempotent — skips employees whose birthday_wish_sent_year already
    equals the current year, so retries and duplicate runs are safe.
    """
    try:
        from apps.accounts.models import Company, EmployeeProfile
        from apps.accounts.utils import send_template_email

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
            except Exception:
                failed_count += 1
                logger.exception('Failed to send birthday wish to %s (%s)', name, email_addr)

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
