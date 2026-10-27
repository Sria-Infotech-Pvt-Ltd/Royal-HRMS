import logging
import uuid

from django.core.cache import cache
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication as _JWTAuthentication

logger = logging.getLogger(__name__)

VIEW_AS_HEADER = 'HTTP_X_VIEW_AS_EMPLOYEE'
VIEW_AS_PERMISSION = 'employees.view_workspace'
_SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
# One audit entry per (viewer, employee) in this window, not one per request.
_VIEW_AS_AUDIT_WINDOW_SECONDS = 30 * 60


class CookieJWTAuthentication(_JWTAuthentication):
    """
    Authenticates via two sources in priority order:
    1. httpOnly cookie 'royal_access_token' — web browsers
    2. Authorization: Bearer <token> header — Flutter mobile

    A request may also carry `X-View-As-Employee: <employee uuid>`. For a signed-in person who holds
    `employees.view_workspace` (a superuser always does) the request then runs as that employee, READ-ONLY, so the
    workspace shows exactly what the employee sees. Any write is refused, and each (viewer, employee) pair is
    audit-logged.
    """

    def authenticate(self, request):
        # 1. Cookie (web browsers — token is never readable by JS)
        raw_token = request.COOKIES.get('royal_access_token')

        # 2. Authorization header (Flutter mobile — no cookie support)
        if not raw_token:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                raw_token = auth_header[len('Bearer '):]

        if not raw_token:
            return None

        try:
            validated = self.get_validated_token(raw_token.encode())
            user = self.get_user(validated)
        except Exception:
            return None

        target_id = request.META.get(VIEW_AS_HEADER, '').strip()
        if target_id:
            user = self._view_as(request, user, target_id)
        return user, validated

    def _view_as(self, request, viewer, target_id):
        """The employee `viewer` is allowed to look at, or a refusal. Never widens a write."""
        from core.permissions import has_perm

        if request.method not in _SAFE_METHODS:
            raise exceptions.PermissionDenied('Viewing as another employee is read-only.')
        if not has_perm(viewer, VIEW_AS_PERMISSION):
            raise exceptions.PermissionDenied('You do not have permission to view another employee\'s workspace.')
        from apps.accounts.models import User

        # The employee's id, or their employee code (what the profile page address carries).
        try:
            lookup = {'pk': uuid.UUID(target_id)}
        except ValueError:
            lookup = {'employee_id': target_id}
        target = User.objects.filter(is_active=True, **lookup).first()
        if target is None:
            raise exceptions.PermissionDenied('Unknown employee.')
        if target.pk == viewer.pk:
            return viewer

        self._audit_view_as(request, viewer, target)
        target.viewed_by = viewer  # lets views tell "the employee" from the person looking
        return target

    @staticmethod
    def _audit_view_as(request, viewer, target):
        from apps.accounts.models import AuditLog
        from core.responses import get_client_ip

        if not cache.add(f'view-as:{viewer.pk}:{target.pk}', 1, _VIEW_AS_AUDIT_WINDOW_SECONDS):
            return
        AuditLog.objects.create(
            user=viewer, action='view_employee_workspace', module='employees', object_id=str(target.pk),
            branch=target.branch, ip_address=get_client_ip(request),
            changes={'employee_id': target.employee_id, 'viewed_by': viewer.employee_id},
        )
        logger.info('%s opened the workspace of %s (read-only)', viewer.employee_id, target.employee_id)
