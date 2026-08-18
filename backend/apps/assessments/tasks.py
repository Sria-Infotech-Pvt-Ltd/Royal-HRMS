"""
Assessment Celery tasks.

Dispatched on-demand from AssignAssessmentView.post() (via
transaction.on_commit, see apps.assessments.views.admin._queue_assignment_emails)
— not part of CELERY_BEAT_SCHEDULE, since there is nothing periodic here:
each assign action enqueues its own one-off notification delivery for the
assignment(s) it just created.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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
