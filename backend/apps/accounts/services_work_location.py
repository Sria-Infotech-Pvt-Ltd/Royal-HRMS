"""
Work location is no longer typed in: it comes from the employee's Company Code (the Branch), so the same fact is never asked twice.

Existing records keep the value they already have. A new hire gets the Company Code's address; when HR moves someone to another
Company Code, their work location follows only if it was still the old Company Code's address (or blank), so a location someone
typed by hand earlier is never overwritten silently.
"""
from __future__ import annotations


def work_location_for_branch(branch_name: str) -> str:
    """The Company Code's address ('' when the name matches no Company Code)."""
    from apps.branch.models import Branch

    name = (branch_name or '').strip()
    if not name:
        return ''
    branch = Branch.objects.filter(branch_name__iexact=name).only('address').first()
    return (branch.address or '').strip() if branch else ''


def follow_branch_change(current_work_location: str, old_branch_name: str, new_branch_name: str) -> str:
    """The work location after a Company Code change: the new address if the current value was derived (or blank), else unchanged."""
    current = (current_work_location or '').strip()
    if current and current != work_location_for_branch(old_branch_name):
        return current
    return work_location_for_branch(new_branch_name) or current
