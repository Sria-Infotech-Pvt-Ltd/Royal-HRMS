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
external system can see.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import get_client_ip, success
from apps.accounts.authentication_external import ExternalAPIKeyAuthentication
from apps.accounts.models import AuditLog, User
from apps.accounts.throttles import ExternalAPIKeyThrottle


def _basic_employee_dict(user: User) -> dict:
    return {
        'employee_id': user.employee_id,
        'full_name':   user.full_name,
        'email':       user.email,
        'department':  user.department,
        'designation': user.designation,
        'role':        user.role.display_name if user.role else '',
        'branch':      user.branch,
        'is_active':   user.is_active,
    }


class ExternalEmployeeBasicListView(APIView):
    """GET /api/external/employees/ — paginated basic employee info for an
    authenticated external system. No bank/PAN/Aadhaar/salary data of any
    kind — see _basic_employee_dict()'s explicit field list above."""
    authentication_classes = [ExternalAPIKeyAuthentication]
    permission_classes     = [IsAuthenticated]
    throttle_classes       = [ExternalAPIKeyThrottle]

    def get(self, request):
        users = User.objects.filter(is_active=True).select_related('role').order_by('employee_id')
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
