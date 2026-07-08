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
