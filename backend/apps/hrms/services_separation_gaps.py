"""Phase 8B gap-closure — exit interview (confidential), attrition reports, clearance-checklist wiring (reuses the real 8A checklist engine)."""
from django.db import transaction
from django.db.models import Count

from apps.hrms.models import ChecklistTemplate, ExitInterview, SeparationChecklistLink, SeparationRequest


def record_exit_interview(request: SeparationRequest, primary_reason: str, responses: dict, conducted_by) -> ExitInterview:
    from django.utils import timezone
    interview, _ = ExitInterview.objects.update_or_create(
        request=request,
        defaults={'primary_reason': primary_reason, 'responses': responses, 'conducted_by': conducted_by, 'conducted_at': timezone.now()},
    )
    return interview


def exit_interview_reason_trends() -> dict:
    """Aggregate counts by primary_reason — confidential RESPONSES are
    never included, only the reason code, matching the master prompt's
    own "anonymised aggregates" framing for manager-facing trend data."""
    return dict(
        ExitInterview.objects.exclude(primary_reason='')
        .values_list('primary_reason')
        .annotate(count=Count('id'))
    )


def attrition_by_reason():
    return dict(
        SeparationRequest.objects.exclude(reason='')
        .values_list('reason')
        .annotate(count=Count('id'))
    )


@transaction.atomic
def start_clearance_checklist(request: SeparationRequest, checklist_template: ChecklistTemplate) -> SeparationChecklistLink:
    """Idempotent. Reuses the REAL 8A checklist engine
    (services_checklist.create_instance_from_template) — no second
    task-tracking mechanism."""
    existing = getattr(request, 'checklist_link', None)
    if existing is not None:
        return existing

    from apps.hrms.services_checklist import create_instance_from_template
    instance = create_instance_from_template(checklist_template, request.employee, request.proposed_last_working_day)
    return SeparationChecklistLink.objects.create(request=request, checklist_instance=instance)


def clearance_complete(request: SeparationRequest) -> bool:
    link = getattr(request, 'checklist_link', None)
    if link is None:
        return False
    return link.checklist_instance.status == link.checklist_instance.STATUS_COMPLETED
