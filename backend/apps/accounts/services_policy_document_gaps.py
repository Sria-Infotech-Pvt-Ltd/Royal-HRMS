"""Phase 8B gap-closure — compliance report export, new-joiner pending-acknowledgement checklist task."""
import csv
import io

from apps.accounts.models import PolicyDocumentVersion
from apps.accounts.services_policy_document_v2 import compliance_counts


def compliance_report_csv(version: PolicyDocumentVersion, audience_employee_ids, employee_lookup: dict) -> str:
    """`employee_lookup`: {employee_id: {"name": ..., "org_unit": ..., "location": ...}} —
    supplied by the caller so this function stays a pure formatter, not a
    second query layer over User/OrgUnit."""
    counts = compliance_counts(version, audience_employee_ids)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Employee', 'Org Unit', 'Location', 'Status'])
    for employee_id in audience_employee_ids:
        info = employee_lookup.get(employee_id, {})
        status = 'Pending' if employee_id in counts['pending_employee_ids'] else 'Acknowledged'
        writer.writerow([info.get('name', employee_id), info.get('org_unit', ''), info.get('location', ''), status])
    return buffer.getvalue()


def create_onboarding_acknowledgement_task(checklist_instance, version: PolicyDocumentVersion, task_template):
    """Adds a pending-acknowledgement task to a new joiner's 8A onboarding
    ChecklistInstance — reuses the real ChecklistTaskInstance model
    directly rather than inventing a parallel "pending items" list."""
    from apps.hrms.models import ChecklistTaskInstance
    return ChecklistTaskInstance.objects.create(
        checklist=checklist_instance, task_template=task_template,
        assignee=checklist_instance.employee, due_date=checklist_instance.anchor_date,
    )
