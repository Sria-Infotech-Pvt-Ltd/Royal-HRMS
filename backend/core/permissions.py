from django.conf import settings
from rest_framework.permissions import BasePermission

_SAFE_METHODS = frozenset(('GET', 'HEAD', 'OPTIONS'))


class RequiresSecureTransport(BasePermission):
    """
    Rejects any request not carrying request.is_secure() == True — for
    endpoints where EVERY request inherently carries a raw biometric face
    descriptor (face registration submit/HR-register; punch verification's
    own embedding leg is conditional per-request, so it checks this itself
    inside FaceVerificationService rather than using this blanket permission).

    Exempt in local/test environments (settings.IS_LOCAL_OR_TEST_ENV — NOT
    settings.DEBUG itself, which Django's test runner force-overrides to
    False for every test run; see that setting's own comment in
    config/settings.py), mirroring the project's own
    `secure=not settings.DEBUG` cookie convention — local development runs
    over plain HTTP and must keep working; SECURE_SSL_REDIRECT already forces
    HTTPS site-wide in a real deployment (config/settings.py), so this is a
    second, explicit, per-endpoint guard rather than the only line of defense.
    """
    message = 'This action requires a secure (HTTPS) connection.'

    def has_permission(self, request, view) -> bool:
        return request.is_secure() or settings.IS_LOCAL_OR_TEST_ENV

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
        if request.user.is_superuser or (request.user.role and request.user.role.name == 'system_admin'):
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
        # Superusers and users with employees.view permission (e.g. system_admin) are exempt from onboarding.
        if user.is_superuser or (user.role and (user.role.name == 'system_admin' or user.role.role_permissions.filter(permission__codename='employees.view').exists())):
            return True
        if user.role and getattr(user.role, 'can_manage_team', False):
            return True
        if user.onboarding_status != user.ONBOARDING_COMPLETE:
            return False
        if user.assessment_status == user.ASSESSMENT_PENDING:
            return False
        return True
