"""
Phase 5B Task I — read-only "as of a date" employee view and timeline.
Built against what already exists (Placement, Phase 5A's Address/
BankAccount, the new EmployeeRelationship/EmploymentAction) without
waiting on Tasks C/F/G/H, per the prompt's own note that Task I has no
write-path dependency on them.

Honesty note on `employment_status`/`employee_type` "as of": this
codebase has no historical table recording every past value of these two
`User` fields — only `EmploymentAction` rows created THROUGH this
phase's new engine carry a `previous_values['set_employment_status']`
snapshot. So "as of" for status is reconstructed from
`EmploymentAction` history where it exists, and falls back to the
CURRENT value (flagged as such) for any employee whose status changes
all predate this phase's engine, or who was never run through it. This
is not a false "exact" history claim — it's stated as what it is in
`status_as_of_source` on the response.
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone


def get_employee_as_of(employee, as_of=None) -> dict:
    as_of = as_of or timezone.localdate()

    from apps.accounts.models import Placement
    from apps.accounts.models_actions import EmploymentAction
    from apps.accounts.services_relationships import resolve_relationship_as_of

    placement = (
        Placement.objects.filter(employee=employee, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related('position__org_unit', 'position__grade_ref', 'position__designation_ref', 'position__branch')
        .first()
    )

    position_data = None
    if placement is not None:
        position = placement.position
        org_unit = position.org_unit
        org_path = []
        node = org_unit
        while node is not None:
            org_path.append(node.name)
            node = node.parent
        position_data = {
            'position_id': str(position.id),
            'title': position.title,
            'org_unit': org_unit.name,
            'org_unit_path': list(reversed(org_path)),
            'grade': position.grade_ref.code if position.grade_ref_id else position.grade,
            'designation': position.designation_ref.name if position.designation_ref_id else employee.designation,
            'branch': position.branch.branch_name if position.branch_id else employee.branch,
        }

    status_as_of = employee.employment_status
    status_source = 'current_value_no_action_history'
    last_status_action = (
        EmploymentAction.objects.filter(
            employee=employee, effective_date__lte=as_of, status=EmploymentAction.STATUS_APPLIED,
            previous_values__has_key='set_employment_status',
        )
        .order_by('-effective_date', '-applied_at')
        .first()
    )
    if last_status_action is not None:
        status_as_of = last_status_action.action_type.resulting_status or status_as_of
        status_source = f'employment_action:{last_status_action.id}'

    relationships = {}
    for rel_code in ('REPORTING_MANAGER', 'HR_PARTNER', 'APPROVER', 'DOTTED_LINE_MANAGER'):
        try:
            related = resolve_relationship_as_of(employee, rel_code, as_of=as_of)
        except Exception:
            related = None
        if related is not None:
            relationships[rel_code] = {'id': str(related.id), 'full_name': related.full_name, 'email': related.email}

    address_data = _address_as_of(employee, as_of)
    bank_data = _bank_account_as_of(employee, as_of)

    return {
        'employee_id': str(employee.id), 'as_of': as_of.isoformat(),
        'position': position_data,
        'employment_type': employee.employee_type,
        'employment_status': status_as_of, 'status_as_of_source': status_source,
        'relationships': relationships,
        'address': address_data, 'bank_account': bank_data,
    }


def _address_as_of(employee, as_of):
    from django.contrib.contenttypes.models import ContentType

    from apps.accounts.models import Address

    content_type = ContentType.objects.get_for_model(employee)
    address = (
        Address.objects.filter(content_type=content_type, object_id=employee.id, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .order_by('-effective_from')
        .first()
    )
    if address is None:
        return None
    return {
        'type': address.type, 'line1': address.line1, 'city': address.city,
        'postal_code': address.postal_code, 'country': address.country.name if address.country_id else None,
    }


def _bank_account_as_of(employee, as_of):
    from apps.accounts.models import BankAccount

    account = (
        BankAccount.objects.filter(employee=employee, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .order_by('-effective_from')
        .first()
    )
    if account is None:
        return None
    # Masked — never expose the decrypted number in an as-of/timeline view.
    return {
        'bank_name': account.bank_name, 'account_type': account.account_type,
        'masked_account_number': f'***{account.account_number[-4:]}' if account.account_number else '',
    }


def get_employee_timeline(employee, *, limit: int = 50) -> list[dict]:
    """Chronological (newest-first) feed of EmploymentActions and
    EmployeeRelationship changes. Sensitive-effect actions appear with
    their type/date/status only — no payload/previous_values are exposed
    here (Task I.2's "sensitive changes appear as 'changed' without
    values unless permitted" — this pass omits them unconditionally
    rather than building full field-security integration)."""
    from apps.accounts.models_actions import EmploymentAction
    from apps.accounts.models_relationships import EmployeeRelationship

    events = []
    for action in EmploymentAction.objects.filter(employee=employee).select_related('action_type').order_by('-effective_date')[:limit]:
        events.append({
            'kind': 'employment_action', 'date': action.effective_date.isoformat(),
            'action_type': action.action_type.code, 'status': action.status,
            'reason': action.reason,
        })
    for rel in EmployeeRelationship.objects.filter(employee=employee).select_related('relationship_type', 'related_employee').order_by('-effective_from')[:limit]:
        events.append({
            'kind': 'relationship_change', 'date': rel.effective_from.isoformat(),
            'relationship_type': rel.relationship_type.code, 'related_employee_id': str(rel.related_employee_id),
            'source': rel.source,
        })
    events.sort(key=lambda e: e['date'], reverse=True)
    return events[:limit]
