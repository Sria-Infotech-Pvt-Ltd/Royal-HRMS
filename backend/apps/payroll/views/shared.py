import logging

from django.utils import timezone
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, get_client_ip
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from apps.payroll.models import (
    PayrollSettings,
    ManagerAttendanceApproval,
    SalaryTransferBatch,
)
from apps.payroll.serializers import (
    PayrollCycleSerializer,
    ManagerAttendanceApprovalSerializer,
)
from apps.accounts.models import AuditLog
from apps.branch.models import Branch

# Phase 7A Task A — the actual calculation (_compute_employee_payslip,
# process_payroll_cycle, _run_payroll_processing, eligibility, ESI/LWF
# helpers, the PF defaults, and the bulk_update field list) now lives in
# apps.payroll.engine.legacy, moved verbatim with zero behavior change.
# Re-imported and re-exported here (via __all__ below) so every existing
# `from apps.payroll.views.shared import ...` — including the wildcard
# imports in process_actions.py/cycle_list_detail.py/
# cycle_attendance_approval.py — keeps resolving these names exactly as
# before; nothing outside apps.payroll.engine computes a payslip now.
from apps.payroll.engine.legacy import (  # noqa: F401
    PayrollAlreadyProcessing,
    _PF_DEFAULT_RATE,
    _PF_DEFAULT_CEILING,
    _PAYSLIP_FIELDS,
    _esi_contribution_period,
    _lwf_due_this_cycle,
    _compute_employee_payslip,
    process_payroll_cycle,
    _eligible_employees_qs,
    _run_payroll_processing,
)

logger = logging.getLogger(__name__)


def _can_l1_approve(user):
    """True for any user whose role has can_manage_team, plus HR/sysadmin as fallback."""
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return bool(user.role.can_manage_team) or _has_perm(user, 'payroll.edit')


def _can_l2_approve(user):
    """True for users with payroll.edit (HR/sysadmin)."""
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return _has_perm(user, 'payroll.edit')


def _is_admin(user) -> bool:
    """Settings-level admin: unrestricted access across all branches."""
    return getattr(user, 'is_superuser', False) or _has_perm(user, 'settings.edit')


def _resolve_user_branch(user):
    """Return the Branch object for an HR user's assigned branch, or None."""
    if not user.branch:
        return None
    return Branch.objects.filter(branch_name=user.branch, status=Branch.STATUS_ACTIVE).first()


__all__ = [
    'PayrollAlreadyProcessing',
    '_esi_contribution_period',
    '_lwf_due_this_cycle',
    '_compute_employee_payslip',
    'process_payroll_cycle',
    '_eligible_employees_qs',
    '_run_payroll_processing',
    '_can_l1_approve',
    '_can_l2_approve',
    '_is_admin',
    '_resolve_user_branch',
    '_PF_DEFAULT_RATE',
    '_PF_DEFAULT_CEILING',
    '_PAYSLIP_FIELDS',
]
