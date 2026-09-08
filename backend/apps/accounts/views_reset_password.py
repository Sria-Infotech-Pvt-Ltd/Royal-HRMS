"""
HR/Admin-triggered employee password reset — distinct from the two existing
self-service flows (forced change-password on first login; forgot-password/
OTP). Neither of those lets HR/Admin act on ANOTHER user's password; this
does, gated on the new `employees.reset_password` permission.

Deliberately its own file, not views.py (already far past the 300-line
convention, 6800+ lines) — mirrors the split pattern used for
views_profile_photo.py / views_email_log.py.
"""
from __future__ import annotations

import logging
import secrets
import string

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from core.permissions import has_perm
from core.responses import error, get_client_ip, success

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from apps.accounts.views import _employee_out_of_branch_scope

logger = logging.getLogger(__name__)


class EmployeePasswordResetView(APIView):
    """
    POST /employees/<uuid:pk>/reset-password/ — generates a fresh temporary
    password for the employee, forces them to change it at next login, and
    invalidates their existing sessions.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        if not has_perm(request.user, 'employees.reset_password'):
            return error(
                'You do not have permission to reset employee passwords.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        try:
            target = User.objects.get(pk=pk, is_active=True)
        except (User.DoesNotExist, ValueError):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        if target.pk == request.user.pk:
            return error(
                'Use your own Change Password option instead.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if _employee_out_of_branch_scope(request.user, target):
            return error(
                "You do not have permission to reset this employee's password.",
                http_status=status.HTTP_403_FORBIDDEN,
            )

        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        target.set_password(temp_password)
        target.must_change_password = True
        target.save(update_fields=['password', 'must_change_password', 'updated_at'])

        # must_change_password is not a volatile JWT claim (see tokens.py),
        # so it wouldn't take effect on an already-active session until that
        # session's tokens naturally expire — blacklist every outstanding
        # token for the target so the new temp password is required
        # immediately, not just on their next fresh login.
        for outstanding in OutstandingToken.objects.filter(user=target):
            BlacklistedToken.objects.get_or_create(token=outstanding)

        try:
            company = Company.objects.first()
            send_template_email(
                recipient_email=target.email,
                template_name='password_reset_by_admin',
                context={
                    'employee_name': target.full_name or target.email,
                    'temp_password': temp_password,
                    'company_name': company.company_name if company else '',
                },
                module='accounts',
                triggered_by=request.user,
            )
            email_sent = True
        except Exception:
            logger.exception('Failed to send password-reset email to %s', target.email)
            email_sent = False

        try:
            AuditLog.objects.create(
                user=request.user, action='employee_password_reset', module='accounts',
                object_id=str(target.pk), changes={'employee': target.email},
                branch=target.branch, ip_address=get_client_ip(request),
            )
        except Exception:
            logger.warning('AuditLog write failed for employee_password_reset target=%s', target.pk)

        logger.info('Password reset for employee %s by %s', target.email, request.user.email)
        return success(
            'Password reset. A new temporary password has been emailed to the employee.'
            if email_sent else
            'Password reset, but the notification email failed to send — check Email Logs.',
        )
