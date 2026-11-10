"""
Company-side (tenant) subscription views — read-only. The company is always
the logged-in one (the active schema), never a request parameter, so one
company can never read another's subscription.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, success
from apps.tenants.access import current_tenant
from apps.tenants.customer_plan import plan_details


class PlanDetailsView(APIView):
    """GET /api/settings/company/plan/ — Company Settings → Plan Details.
    Company-wide administrators only (settings.edit: System Admin, HR Admin)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'settings.edit'):
            return error('Only company administrators can view plan details.', http_status=403)
        client = current_tenant()
        if client is None:
            return error('Plan details are available inside a company account.', http_status=400)
        return success('Plan details retrieved.', plan_details(client))
