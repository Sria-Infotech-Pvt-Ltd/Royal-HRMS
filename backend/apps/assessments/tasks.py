"""
Assessment Celery tasks.

send_assessment_assignment_emails_task is dispatched on-demand from
AssignAssessmentView.post() (via transaction.on_commit, see
apps.assessments.views.admin._queue_assignment_emails) — a one-off
delivery for the assignment(s) just created.

send_assessment_deadline_reminders is the one periodic task in this
module, registered in CELERY_BEAT_SCHEDULE (config/settings.py) — an
assignee who never opens the portal previously got no nudge at all as
their deadline approached.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# How far ahead of an assignment's deadline to send the one-time reminder.
REMINDER_WINDOW_HOURS = 24


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_assessment_assignment_emails_task(self, schema_name: str, assignment_ids: list, template_name: str = 'assessment_assigned'):
    """
    Background delivery for "assessment assigned" notification emails.
    `schema_name` is the dispatching company's schema (see
    apps.tenants.utils.run_in_tenant).

    Takes only CandidateAssignment ids (not serialized objects) and
    re-fetches them fresh in the worker, per this project's task convention.
    Retries (up to 3, 5 min apart) only cover the setup phase — fetching the
    assignments and company branding — because nothing has been sent yet at
    that point. Once the send loop starts, each recipient is delivered via
    the existing _send_assessment_email() helper, which already logs and
    swallows its own failures — so one bad recipient never aborts the rest,
    and a task retry can never re-send to a recipient who already got their
    email (there is nothing left to raise/retry once the loop has started).
    """
    from apps.accounts.models import Company
    from apps.assessments.models import CandidateAssignment
    from apps.assessments.views.admin import _send_assessment_email
    from apps.tenants.utils import run_in_tenant

    def _do():
        assignments = list(
            CandidateAssignment.objects
            .select_related('candidate', 'employee', 'assessment')
            .filter(pk__in=assignment_ids)
        )
        if not assignments:
            logger.info(
                'send_assessment_assignment_emails_task: none of %s exist anymore — skipping.',
                assignment_ids,
            )
            return {'requested': len(assignment_ids), 'status': 'no_assignments'}

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''

        attempted = 0
        skipped   = 0

        for assignment in assignments:
            if assignment.employee_id:
                recipient_email = assignment.employee.email
                candidate_name  = assignment.employee.full_name or assignment.employee.email
            elif assignment.candidate_id:
                recipient_email = assignment.candidate.email
                candidate_name  = assignment.candidate.name
            else:
                skipped += 1
                continue

            if not recipient_email:
                skipped += 1
                continue

            _send_assessment_email(recipient_email, {
                'candidate_name':   candidate_name,
                'assessment_title': assignment.assessment.title,
                'company_name':     company_name,
                'portal_url':       portal_url,
                'deadline':         str(assignment.deadline) if assignment.deadline else '',
            }, template_name)
            attempted += 1

        result = {
            'requested': len(assignment_ids),
            'attempted': attempted,
            'skipped':   skipped,
        }
        logger.info('send_assessment_assignment_emails_task completed: %s', result)
        return result

    try:
        return run_in_tenant(schema_name, _do)
    except Exception as exc:
        logger.error(
            'send_assessment_assignment_emails_task setup failed for %s: %s',
            assignment_ids, exc, exc_info=True,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_assessment_deadline_reminders(self):
    """
    Daily task: find CandidateAssignments whose deadline falls within the
    next REMINDER_WINDOW_HOURS, aren't yet complete, and haven't already
    been reminded — send one reminder email each and stamp
    deadline_reminder_sent_at so it never repeats for the same assignment
    (unlike apps.payroll.tasks.send_payroll_approval_reminders, which is
    deliberately an ongoing daily nag — a deadline reminder is a single
    "heads up" notice, not a recurring one). Runs once per active company
    with the assessments module enabled (see apps.tenants.utils.
    run_for_all_tenants — this task has no single tenant of its own).
    """
    from apps.tenants.models import MODULE_ASSESSMENTS
    from apps.tenants.utils import run_for_all_tenants

    def _run_for_one_tenant():
        from datetime import timedelta

        from django.db.models import Q
        from django.utils import timezone

        from apps.accounts.models import Company
        from apps.assessments.models import CandidateAssignment
        from apps.assessments.views.admin import _send_assessment_email

        now     = timezone.now()
        cutoff  = now + timedelta(hours=REMINDER_WINDOW_HOURS)
        pending = (
            CandidateAssignment.objects
            .filter(
                deadline__isnull=False,
                deadline__gt=now,
                deadline__lte=cutoff,
                deadline_reminder_sent_at__isnull=True,
            )
            .exclude(status=CandidateAssignment.STATUS_COMPLETE)
            .filter(Q(employee__isnull=False) | Q(candidate__isnull=False))
            .select_related('employee', 'candidate', 'assessment')
        )

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''

        reminded_ids = []
        for assignment in pending:
            if assignment.employee_id:
                recipient_email = assignment.employee.email
                recipient_name  = assignment.employee.full_name or assignment.employee.email
            else:
                recipient_email = assignment.candidate.email
                recipient_name  = assignment.candidate.name

            if not recipient_email:
                continue

            _send_assessment_email(recipient_email, {
                'candidate_name':   recipient_name,
                'assessment_title': assignment.assessment.title,
                'company_name':     company_name,
                'portal_url':       portal_url,
                'deadline':         str(assignment.deadline),
            }, 'assessment_deadline_reminder')
            reminded_ids.append(assignment.pk)

        if reminded_ids:
            CandidateAssignment.objects.filter(pk__in=reminded_ids).update(
                deadline_reminder_sent_at=now,
            )

        result = {'reminded': len(reminded_ids)}
        logger.info('send_assessment_deadline_reminders completed: %s', result)
        return result

    try:
        return run_for_all_tenants(
            _run_for_one_tenant,
            task_name='send_assessment_deadline_reminders',
            required_module=MODULE_ASSESSMENTS,
        )
    except Exception as exc:
        logger.error('send_assessment_deadline_reminders failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
