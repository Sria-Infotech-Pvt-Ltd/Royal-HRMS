from rest_framework.permissions import BasePermission

_SAFE_METHODS = frozenset(('GET', 'HEAD', 'OPTIONS'))
# Static exempt roles (system-level roles that never go through employee onboarding).
_ONBOARDING_EXEMPT_ROLES = frozenset(('system_admin', 'hr', 'hr_admin'))


class HasSettingsPermission(BasePermission):
    """
    Codename-based gate for settings endpoints.
    Safe methods require settings.view; mutating methods require settings.edit.
    system_admin bypasses both checks.
    """
    message = 'You do not have permission to manage settings.'

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated and request.user.role):
            return False
        if request.user.role.name == 'system_admin':
            return True
        codename = 'settings.view' if request.method in _SAFE_METHODS else 'settings.edit'
        return request.user.role.role_permissions.filter(
            permission__codename=codename
        ).exists()


class HasCompletedOnboarding(BasePermission):
    """
    Blocks employee-portal resources (employee dashboard, leave, etc.) until
    the user has finished onboarding and cleared all assigned assessments.

    This mirrors the redirect gate in the Next.js proxy, so a direct API
    call cannot bypass it. HR and system_admin roles are exempt — they do
    not go through the onboarding/assessment flow themselves.
    """
    message = 'Complete onboarding and your assigned assessments before accessing this resource.'

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        role_name = user.role.name if user.role else ''
        # Static system roles + any role flagged as a team-manager are exempt.
        if role_name in _ONBOARDING_EXEMPT_ROLES or user.is_superuser:
            return True
        if user.role and getattr(user.role, 'can_manage_team', False):
            return True
        if user.onboarding_status != user.ONBOARDING_COMPLETE:
            return False
        if user.assessment_status == user.ASSESSMENT_PENDING:
            return False
        return True
