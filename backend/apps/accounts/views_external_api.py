"""
Read-only APIs for OTHER INTERNAL SYSTEMS (e.g. the Project Budget &
Tracking tool) to pull basic employee info from — see
authentication_external.py's own docstring for why this is a separate
auth path from every other endpoint in this app.

Deliberately a hand-picked, minimal field list — NOT a reuse of
apps.accounts.views.shared._employee_dict(), which is a monolithic dict
that also carries bank account/PAN/Aadhaar/passport data (masked, not
absent). Building this projection from scratch means there's no risk of
a future change to that shared function silently widening what an
external system can see. Compensation/payroll figures (CTC, hourly
rate, etc.) are kept out of this file for the same reason — see
_basic_employee_dict()'s trailing comment.
"""
from __future__ import annotations

from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, get_client_ip, success
from apps.accounts.authentication_external import ExternalAPIKeyAuthentication
from apps.accounts.models import AuditLog, User
from apps.accounts.throttles import ExternalAPIKeyThrottle
from apps.hrms.models import SEP_APPROVED, SeparationRequest


def _exit_date(user: User) -> str | None:
    """Last working day from the employee's most recent approved
    separation, if any — the only place an "exit date" exists in this
    schema (there is no flat exit_date column on User)."""
    last = (
        SeparationRequest.objects
        .filter(employee=user, status=SEP_APPROVED)
        .order_by('-proposed_last_working_day')
        .values_list('proposed_last_working_day', flat=True)
        .first()
    )
    return last.isoformat() if last else None


def _split_name(full_name: str) -> tuple[str, str]:
    """Best-effort first/last split — User only stores a single full_name
    field, so this is a display-time heuristic, not a stored fact. Single-
    word names (e.g. a legal mononym) get last_name='', per the external
    spec's own rule for that case."""
    parts = full_name.strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def _basic_employee_dict(user: User) -> dict:
    first_name, last_name = _split_name(user.full_name)
    is_active = user.is_active
    return {
        'employee_id':                     user.employee_id,
        'full_name':                       user.full_name,
        'first_name':                      first_name,
        'last_name':                       last_name,
        'email':                           user.email,
        'phone':                           user.phone,
        'department':                      user.department,
        'designation':                     user.designation,
        'role':                            user.role.display_name if user.role else '',
        'branch':                          user.branch,
        'reporting_manager_employee_id':   user.reporting_manager.employee_id if user.reporting_manager_id else None,
        'date_of_joining':                 user.date_of_joining.isoformat() if user.date_of_joining else None,
        'employment_type':                 user.employee_type,
        'is_active':                       is_active,
        'exit_date':                       None if is_active else _exit_date(user),
        'updated_at':                      user.updated_at.isoformat(),
    }
    # Deliberately NOT included: hourly_cost_rate/cost_currency. Compensation
    # data (apps.payroll.models_compensation.EmployeeCompensation) is kept
    # out of this codepath on purpose — see this module's docstring. Flagged
    # back to the requesting system as "not available" rather than wired up
    # here; revisit only as an explicit, separate decision.


class ExternalEmployeeBasicListView(APIView):
    """GET /api/external/employees/ — paginated basic employee info for an
    authenticated external system. No bank/PAN/Aadhaar/salary data of any
    kind — see _basic_employee_dict()'s explicit field list above.

    Query params:
      include_inactive=true   — also return exited employees (is_active=False)
      updated_since=<ISO8601> — only employees changed at/after this instant
    """
    authentication_classes = [ExternalAPIKeyAuthentication]
    permission_classes     = [IsAuthenticated]
    throttle_classes       = [ExternalAPIKeyThrottle]

    def get(self, request):
        users = User.objects.select_related('role', 'reporting_manager').order_by('employee_id')

        include_inactive = request.query_params.get('include_inactive', '').lower() == 'true'
        if not include_inactive:
            users = users.filter(is_active=True)

        updated_since_raw = request.query_params.get('updated_since')
        if updated_since_raw:
            updated_since = parse_datetime(updated_since_raw)
            if updated_since is None:
                return error('updated_since must be a valid ISO 8601 timestamp.')
            users = users.filter(updated_at__gte=updated_since)

        page_obj, paginator = paginate(users, request)
        results = [_basic_employee_dict(u) for u in page_obj]

        # Every fetch is logged — there's no real User to attach (this
        # isn't a logged-in person), so `user=None`; the calling system's
        # identity lives in `changes` instead. Mirrors the shape
        # EmployeeRevealSensitiveView already uses for sensitive-field
        # access logging.
        AuditLog.objects.create(
            user=None,
            action='external_employee_list_fetch',
            module='external_api',
            changes={'client': request.auth.name, 'count': len(results), 'page': page_obj.number},
            ip_address=get_client_ip(request),
        )

        return success('Employees retrieved.', paginated_data(paginator, page_obj, results))


class ExternalEmployeeDetailView(APIView):
    """GET /api/external/employees/<employee_id>/ — single employee lookup
    by employee_id, same field list and auth as the list view above."""
    authentication_classes = [ExternalAPIKeyAuthentication]
    permission_classes     = [IsAuthenticated]
    throttle_classes       = [ExternalAPIKeyThrottle]

    def get(self, request, employee_id):
        user = User.objects.select_related('role', 'reporting_manager').filter(employee_id=employee_id).first()
        if user is None:
            return error('No employee found with that employee_id.', http_status=404)

        AuditLog.objects.create(
            user=None,
            action='external_employee_detail_fetch',
            module='external_api',
            changes={'client': request.auth.name, 'employee_id': employee_id},
            ip_address=get_client_ip(request),
        )

        return success('Employee retrieved.', _basic_employee_dict(user))
