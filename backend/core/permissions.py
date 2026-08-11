from django.conf import settings
from rest_framework.permissions import BasePermission

_SAFE_METHODS = frozenset(('GET', 'HEAD', 'OPTIONS'))


def has_perm(user, codename: str) -> bool:
    """
    True if user's role carries the given permission codename.

    Single shared implementation — this used to be copy-pasted independently
    across 36 view/serializer files and had drifted into three incompatible
    behaviors: superuser-bypass checked before vs. after the role-null guard
    (so a superuser with no linked Role row passed in some views and was
    denied in others), and some copies missing the superuser bypass
    entirely. Always use this instead of redefining _has_perm locally.
    """
    if not user:
        return False
    # Superuser bypass checked BEFORE the role check — a superuser account
    # with no linked Role row must still pass; otherwise the missing-role
    # guard below would deny it first and this bypass would never run.
    if getattr(user, 'is_superuser', False):
        return True
    if not user.role:
        return False
    # settings.edit is this codebase's universal "sees/does everything"
    # signal — checking it here (permission-based) instead of a hardcoded
    # role name means any role actually granted settings.edit gets the same
    # bypass, and revoking it from system_admin would actually revoke it.
    return user.role.role_permissions.filter(
        permission__codename__in={codename, 'settings.edit'}
    ).exists()


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
    system_admin holds both codenames directly (seeded that way) — no
    role-name special case needed or wanted; a hardcoded bypass here would
    silently stop tracking whatever role actually carries settings.edit.
    """
    message = 'You do not have permission to manage settings.'

    def has_permission(self, request, view) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        # Superuser bypass checked BEFORE the role check — a superuser
        # account with no linked Role row (e.g. created outside the normal
        # create_superuser flow) must still pass; otherwise the missing-role
        # guard below would deny it first and this bypass would never
        # actually run for that account.
        if request.user.is_superuser:
            return True
        if not request.user.role:
            return False
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
        # Superusers and anyone holding employees.view (system_admin, branch_admin,
        # HR — every admin-tier role) are exempt from onboarding: they're never
        # a new hire going through this flow themselves.
        if user.is_superuser or (user.role and user.role.role_permissions.filter(permission__codename='employees.view').exists()):
            return True
        if user.role and getattr(user.role, 'can_manage_team', False):
            return True
        if user.onboarding_status != user.ONBOARDING_COMPLETE:
            return False
        if user.assessment_status == user.ASSESSMENT_PENDING:
            return False
        return True
