from rest_framework.permissions import BasePermission

from apps.tenants.models import PlatformAdmin


class IsPlatformAdmin(BasePermission):
    """Only a request authenticated via PlatformAdminAuthentication may pass."""
    message = 'Platform admin access required.'

    def has_permission(self, request, view) -> bool:
        return isinstance(request.user, PlatformAdmin)
