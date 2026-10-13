"""Phase 8B Task D — migrate visibility/target_org_unit/target_branch to an equivalent AnnouncementAudienceRule, proven to resolve the SAME recipients."""
from django.db import transaction

from apps.announcements.models import Announcement, AnnouncementAcknowledgement, AnnouncementAudienceRule


@transaction.atomic
def migrate_visibility_to_rule(announcement: Announcement) -> AnnouncementAudienceRule:
    """Idempotent. Visibility -> rule mapping:
    - 'all' -> {} (no filter — everyone)
    - 'branch' -> {"branch_ids": [target_branch_id]}
    - 'department' -> {"org_unit_ids": [target_org_unit_id]} (the real FK
      is to OrgUnit despite the "department" wording — see models.py)."""
    existing = getattr(announcement, 'audience_rule', None)
    if existing is not None:
        return existing

    if announcement.visibility == 'branch' and announcement.target_branch_id:
        rule = {'branch_ids': [str(announcement.target_branch_id)]}
    elif announcement.visibility == 'department' and announcement.target_org_unit_id:
        rule = {'org_unit_ids': [str(announcement.target_org_unit_id)]}
    else:
        rule = {}

    return AnnouncementAudienceRule.objects.create(announcement=announcement, rule=rule)


def resolve_recipients_legacy(announcement: Announcement):
    """The EXACT existing recipient-resolution logic (visibility/
    target_org_unit/target_branch), for parity comparison against
    resolve_recipients_from_rule()."""
    from apps.accounts.models import User
    qs = User.objects.filter(is_active=True)
    if announcement.visibility == 'branch' and announcement.target_branch_id:
        qs = qs.filter(branch=announcement.target_branch.branch_name)
    elif announcement.visibility == 'department' and announcement.target_org_unit_id:
        qs = qs.filter(department=announcement.target_org_unit.name)
    return set(qs.values_list('id', flat=True))


def resolve_recipients_from_rule(rule: AnnouncementAudienceRule):
    from apps.accounts.models import OrgUnit, User
    from apps.branch.models import Branch
    qs = User.objects.filter(is_active=True)
    branch_ids = rule.rule.get('branch_ids') or []
    org_unit_ids = rule.rule.get('org_unit_ids') or []
    if branch_ids:
        branch_names = Branch.objects.filter(id__in=branch_ids).values_list('branch_name', flat=True)
        qs = qs.filter(branch__in=list(branch_names))
    if org_unit_ids:
        org_unit_names = OrgUnit.objects.filter(id__in=org_unit_ids).values_list('name', flat=True)
        qs = qs.filter(department__in=list(org_unit_names))
    return set(qs.values_list('id', flat=True))


def record_acknowledgement(announcement: Announcement, employee) -> AnnouncementAcknowledgement:
    acknowledgement, _ = AnnouncementAcknowledgement.objects.get_or_create(announcement=announcement, employee=employee)
    return acknowledgement


def pending_acknowledgers(announcement: Announcement):
    rule = getattr(announcement, 'audience_rule', None)
    if rule is None:
        return set()
    recipients = resolve_recipients_from_rule(rule)
    acknowledged = set(announcement.acknowledgements.values_list('employee_id', flat=True))
    return recipients - acknowledged
