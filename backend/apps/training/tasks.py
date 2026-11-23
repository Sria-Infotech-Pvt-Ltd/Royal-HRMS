"""Daily: remind employees of training due soon, and tell them once when it is overdue."""
import datetime
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

REMIND_DAYS_BEFORE = 3


def send_deadline_notifications(today=None) -> dict:
    from apps.notifications.signals import _notify
    from apps.training.models import TrainingAssignment
    today = today or timezone.localdate()
    now = timezone.now()
    open_states = (TrainingAssignment.STATUS_ASSIGNED, TrainingAssignment.STATUS_IN_PROGRESS)
    base = TrainingAssignment.objects.filter(status__in=open_states, due_date__isnull=False,
                                             course__archived_at__isnull=True).select_related('course', 'employee')
    reminded = overdue = 0
    for a in base.filter(deadline_reminder_sent_at__isnull=True, due_date__gte=today,
                         due_date__lte=today + datetime.timedelta(days=REMIND_DAYS_BEFORE)):
        days = (a.due_date - today).days
        when = 'today' if days == 0 else f'in {days} day(s) ({a.due_date:%d %b})'
        _notify(a.employee, 'Training Due Soon', f'Your training "{a.course.title}" is due {when}.',
                'training_due', 'training', str(a.pk))
        a.deadline_reminder_sent_at = now
        a.save(update_fields=['deadline_reminder_sent_at', 'updated_at'])
        reminded += 1
    for a in base.filter(overdue_notified_at__isnull=True, due_date__lt=today):
        _notify(a.employee, 'Training Overdue',
                f'Your training "{a.course.title}" was due on {a.due_date:%d %b %Y}. Please complete it.',
                'training_overdue', 'training', str(a.pk))
        a.overdue_notified_at = now
        a.save(update_fields=['overdue_notified_at', 'updated_at'])
        overdue += 1
    return {'reminded': reminded, 'overdue': overdue}


@shared_task(name='apps.training.tasks.training_deadline_notifications')
def training_deadline_notifications():
    from apps.tenants.utils import run_for_all_tenants
    return run_for_all_tenants(send_deadline_notifications, 'training_deadline_notifications',
                               required_module='training')
