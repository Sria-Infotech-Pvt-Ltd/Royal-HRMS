"""
System-wide Email Log — view, and resend-a-failed-email.

Deliberately its own file, not views.py (already far past the 300-line
convention, 6800+ lines) — mirrors the split pattern used for
views_profile_photo.py.

EmailLog rows are written automatically by apps.accounts.utils.
send_template_email() on every send it makes (see that function) — nothing
here writes a row directly except the resend path, via
apps.accounts.utils.resend_logged_email().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm
from core.responses import error, success

from apps.accounts.models import EmailLog
from apps.accounts.serializers_email_log import EmailLogDetailSerializer, EmailLogSerializer
from apps.accounts.utils import resend_logged_email

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to view email logs.'
_RESEND_DENIED = 'You do not have permission to resend emails.'
_RESEND_COOLDOWN_SECONDS = 15


class EmailLogListView(APIView):
    """GET /api/settings/email-logs/ — paginated, filterable system-wide log."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not has_perm(request.user, 'email_logs.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = EmailLog.objects.select_related('triggered_by', 'smtp_settings')

        status_param = request.query_params.get('status', '').strip()
        if status_param:
            qs = qs.filter(status=status_param)

        module = request.query_params.get('module', '').strip()
        if module:
            qs = qs.filter(module=module)

        template_name = request.query_params.get('template_name', '').strip()
        if template_name:
            qs = qs.filter(template_name__icontains=template_name)

        triggered_by = request.query_params.get('triggered_by', '').strip()
        if triggered_by:
            qs = qs.filter(triggered_by_id=triggered_by)

        search = request.query_params.get('search', '').strip()
        if search:
            if len(search) > 100:
                return error('search must be 100 characters or fewer.')
            qs = qs.filter(recipient_email__icontains=search) | qs.filter(subject__icontains=search)

        date_from = request.query_params.get('date_from', '').strip()
        if date_from:
            try:
                datetime.strptime(date_from, '%Y-%m-%d')
                qs = qs.filter(created_at__date__gte=date_from)
            except ValueError:
                return error('date_from must be in YYYY-MM-DD format.')

        date_to = request.query_params.get('date_to', '').strip()
        if date_to:
            try:
                datetime.strptime(date_to, '%Y-%m-%d')
                qs = qs.filter(created_at__date__lte=date_to)
            except ValueError:
                return error('date_to must be in YYYY-MM-DD format.')

        page_obj, paginator = paginate(qs, request)
        results = EmailLogSerializer(page_obj.object_list, many=True).data
        return success('Email logs retrieved.', data=paginated_data(paginator, page_obj, results))


class EmailLogDetailView(APIView):
    """GET /api/settings/email-logs/<uuid:pk>/ — full content, for a "view before resend" screen."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        if not has_perm(request.user, 'email_logs.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            log = EmailLog.objects.select_related('triggered_by', 'smtp_settings').get(pk=pk)
        except EmailLog.DoesNotExist:
            return error('Email log not found.', http_status=status.HTTP_404_NOT_FOUND)

        return success('Email log retrieved.', data=EmailLogDetailSerializer(log).data)


class EmailLogResendView(APIView):
    """POST /api/settings/email-logs/<uuid:pk>/resend/ — replay a failed email verbatim."""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        if not has_perm(request.user, 'email_logs.resend'):
            return error(_RESEND_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            log = EmailLog.objects.get(pk=pk)
        except EmailLog.DoesNotExist:
            return error('Email log not found.', http_status=status.HTTP_404_NOT_FOUND)

        if log.status != EmailLog.STATUS_FAILED:
            return error('Only failed emails can be resent.', http_status=status.HTTP_409_CONFLICT)

        if log.has_sensitive_context:
            return error(
                'This email contained a one-time credential and cannot be resent generically '
                'for security reasons. Use the dedicated resend action in its originating module '
                '(e.g. Recruitment → Candidate → Resend Portal Invite), which issues a fresh credential.',
                http_status=status.HTTP_409_CONFLICT,
            )

        cooldown_cutoff = timezone.now() - timedelta(seconds=_RESEND_COOLDOWN_SECONDS)
        recent_resend = EmailLog.objects.filter(resend_of=log, created_at__gte=cooldown_cutoff).exists()
        if recent_resend:
            return error(
                'A resend for this email was just triggered. Please wait a moment and try again.',
                http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            new_log = resend_logged_email(log, triggered_by=request.user)
        except Exception as exc:
            failed_log = EmailLog.objects.filter(resend_of=log).order_by('-created_at').first()
            data = EmailLogSerializer(failed_log).data if failed_log else None
            return error(f'Resend failed: {exc}', data=data, http_status=status.HTTP_502_BAD_GATEWAY)

        data = EmailLogSerializer(new_log).data
        if log.had_attachments:
            data['warning'] = 'Attachments from the original email are not reproduced on resend.'
        return success('Email resent successfully.', data=data)
