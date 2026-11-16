"""Which announcements a person may see: one rule, shared by the Announcements page, reactions and the dashboard card.

Before this, the page and the reaction endpoint each carried their own copy of the filter, and the dashboard card carried none (it
showed the newest announcement in the whole table to everyone), so the card could show another branch's announcement and hide the
one that was actually posted for the viewer.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.announcements.models import Announcement
from core.permissions import has_perm


def visible_announcements(user) -> 'QuerySet[Announcement]':
    """Announcements `user` may see.

    People who can edit announcements see all of them. Everyone else sees the company-wide ones, the ones for their department (an
    org unit they sit in or under) and the ones for their branch. Ordering is the model's: pinned first, then newest first."""
    if has_perm(user, 'announcements.edit'):
        return Announcement.objects.all()

    from apps.accounts.services_approval import resolve_employee_org_unit_chain

    return Announcement.objects.filter(
        Q(visibility=Announcement.VISIBILITY_ALL)
        | Q(visibility=Announcement.VISIBILITY_DEPARTMENT, target_org_unit_id__in=resolve_employee_org_unit_chain(user))
        | Q(visibility=Announcement.VISIBILITY_BRANCH, target_branch__branch_name=user.branch)
    )
