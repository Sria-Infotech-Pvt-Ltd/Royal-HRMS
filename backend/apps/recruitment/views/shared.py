import csv
import io
import logging
import secrets
import smtplib
import string
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.date_utils import format_date_display
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from core.pagination import paginate, paginated_data
from core.template_context import candidate_context, candidate_interview_location, company_name, universal_context
from ..models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule
from ..serializers import (
    CandidateBulkImportRowSerializer,
    CandidateCreateSerializer,
    CandidateDetailSerializer,
    CandidateEmailSerializer,
    CandidateListSerializer,
    CandidateUpdateSerializer,
    ReferralBonusSerializer,
    ReferralRuleSerializer,
    ReferralSubmitSerializer,
)

logger = logging.getLogger(__name__)


def _can_access_candidate(user, candidate) -> bool:
    """
    True for org-wide access (settings.edit) or users with no branch set.
    Otherwise the candidate's branch must match the user's own branch —
    a recruitment.edit/view holder should only reach candidates in their own
    branch, not company-wide, mirroring the branch scoping used for leave and
    expense requests.
    """
    if _has_perm(user, 'settings.edit'):
        return True
    user_branch = (getattr(user, 'branch', '') or '').strip()
    if not user_branch:
        return True
    candidate_branch = candidate.branch.branch_name if candidate.branch else ''
    return candidate_branch.strip().lower() == user_branch.lower()


def _scoped_candidate_branch(request, *, required: bool = True):
    """
    Resolves a non-admin caller's own branch and injects it into a mutable
    copy of request.data, overriding whatever branch id the client sent —
    the frontend's own copy of this (matching the JWT's branch name string
    against a separately-fetched, active-only branch list, for a field that's
    locked/read-only in the UI anyway) is a best-effort display convenience
    that can legitimately come up empty or stale; this is the actual source
    of truth. Mirrors the read-side scoping in CandidateListCreateView.get
    and _can_access_candidate.

    Returns (data, None) to proceed, or (None, error_response) to bail out.
    required=True (creating a new candidate — no existing branch to fall
    back on) errors clearly if the caller's own account has no branch set.
    required=False (editing a candidate the caller can already access per
    _can_access_candidate, which treats a branchless non-admin as
    unrestricted) instead leaves the client's data untouched in that edge
    case, matching that same leniency rather than newly blocking the edit.
    """
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    if _has_perm(request.user, 'settings.edit'):
        return data, None

    user_branch = (getattr(request.user, 'branch', '') or '').strip()
    if not user_branch:
        if required:
            return None, error('Your account is not assigned to a Company Code. Contact an administrator.')
        return data, None

    from apps.branch.models import Branch
    branch_obj = Branch.objects.filter(branch_name__iexact=user_branch).first()
    if not branch_obj:
        return None, error('Your assigned Company Code could not be found. Contact an administrator.')
    data['branch'] = branch_obj.id
    return data, None


def _send_candidate_email(candidate, template_slug, actor, extra_context=None):
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    subject      = f'Your application update — {candidate.position_applied}'
    sent_status  = CandidateEmail.STATUS_FAILED

    context = {
        'candidate_name':   candidate.name,
        'position':         candidate.position_applied,
        'position_applied': candidate.position_applied,
        'branch_name':      candidate.branch.branch_name if candidate.branch else '',
        'company_name':     company_name,
    }
    if extra_context:
        context.update(extra_context)

    try:
        send_template_email(
            recipient_email=candidate.email,
            template_name=template_slug,
            context=context,
            module='recruitment',
            triggered_by=actor,
        )
        sent_status = CandidateEmail.STATUS_SENT
        logger.info('Sent %s email to %s for candidate %s', template_slug, candidate.email, candidate.id)
    except Exception as exc:
        logger.exception('Failed to send %s email: %s', template_slug, exc)

    CandidateEmail.objects.create(
        candidate=candidate,
        template_used=template_slug,
        subject=subject,
        to_email=candidate.email,
        status=sent_status,
        sent_by=actor,
    )
    return sent_status


def _send_referral_email(candidate, template_slug, recipient_email, context, extra_attachments=None):
    """Send one referral-flow email and write CandidateEmail + CandidateLog records."""
    sent_status = CandidateEmail.STATUS_FAILED
    try:
        send_template_email(
            recipient_email=recipient_email,
            template_name=template_slug,
            context=context,
            extra_attachments=extra_attachments,
            module='recruitment',
        )
        sent_status = CandidateEmail.STATUS_SENT
        logger.info('Sent %s to %s for candidate %s', template_slug, recipient_email, candidate.id)
    except Exception:
        logger.exception('Failed to send %s to %s', template_slug, recipient_email)
        CandidateLog.objects.create(
            candidate=candidate,
            log_type=CandidateLog.TYPE_ERROR,
            title=f'Email failed: {template_slug}',
            description=f'Could not deliver {template_slug} to {recipient_email}',
        )
    CandidateEmail.objects.create(
        candidate=candidate,
        template_used=template_slug,
        subject=template_slug,
        to_email=recipient_email,
        status=sent_status,
    )


def _send_referral_submission_emails(candidate):
    """Background: notify referrer + candidate when a referral is first submitted."""
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    branch_name  = candidate.branch.branch_name if candidate.branch else ''
    referrer     = candidate.referral_by
    referrer_name = (referrer.full_name or referrer.email) if referrer else ''

    # Email A — to the referring employee
    if referrer and referrer.email:
        _send_referral_email(
            candidate=candidate,
            template_slug='referral_submitted_referrer',
            recipient_email=referrer.email,
            context={
                'referrer_name':    referrer_name,
                'candidate_name':   candidate.name,
                'position_applied': candidate.position_applied,
                'branch_name':      branch_name,
                'company_name':     company_name,
            },
        )

    # Email B — to the referred candidate
    _send_referral_email(
        candidate=candidate,
        template_slug='referral_submitted_candidate',
        recipient_email=candidate.email,
        context={
            'candidate_name':   candidate.name,
            'referrer_name':    referrer_name,
            'position_applied': candidate.position_applied,
            'company_name':     company_name,
        },
    )


def _send_interview_scheduled_emails(candidate):
    """Background: notify referred candidate + referrer when interview_date is first set."""
    context = {**universal_context(), **candidate_context(candidate)}
    referrer     = candidate.referral_by
    referrer_name = (referrer.full_name or referrer.email) if referrer else ''
    ics = _build_interview_ics(candidate)

    # Email A — to the referred candidate
    _send_referral_email(
        candidate=candidate,
        template_slug='referral_interview_scheduled_candidate',
        recipient_email=candidate.email,
        context=context,
        extra_attachments=[ics] if ics else None,
    )

    # Email B — to the referring employee (no calendar invite — it's not their interview)
    if referrer and referrer.email:
        _send_referral_email(
            candidate=candidate,
            template_slug='referral_interview_scheduled_referrer',
            recipient_email=referrer.email,
            context={**context, 'referrer_name': referrer_name},
        )


def _send_interview_scheduled_email_general(candidate):
    """Background: notify a non-referred candidate when their interview date is first set."""
    context = {**universal_context(), **candidate_context(candidate)}
    ics = _build_interview_ics(candidate)

    _send_referral_email(
        candidate=candidate,
        template_slug='interview_scheduled_candidate',
        recipient_email=candidate.email,
        context=context,
        extra_attachments=[ics] if ics else None,
    )


def _build_interview_ics(candidate):
    """
    Build a minimal .ics calendar invite for the candidate's interview, so it
    lands directly on their calendar instead of relying on them to remember
    the email. Returns None when there's no interview_date to build from.

    interview_date/interview_time are naive values in the company's operating
    timezone (IST — matching apps/attendance's own convention elsewhere in
    this codebase); converted to UTC for DTSTART/DTEND so every calendar
    client reads them correctly without an embedded VTIMEZONE block.
    """
    if not candidate.interview_date:
        return None

    from datetime import datetime, time as dt_time, timedelta
    from zoneinfo import ZoneInfo

    IST = ZoneInfo('Asia/Kolkata')
    UTC = ZoneInfo('UTC')
    start_time = candidate.interview_time or dt_time(hour=10)
    start_dt = datetime.combine(candidate.interview_date, start_time, tzinfo=IST)
    end_dt   = start_dt + timedelta(minutes=30)

    def _fmt(dt):
        return dt.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')

    location    = candidate_interview_location(candidate).translate(_ICS_ESCAPE)
    summary     = f'Interview — {candidate.position_applied}'.translate(_ICS_ESCAPE)
    description = f'Interview for {candidate.position_applied} at {company_name()}.'.translate(_ICS_ESCAPE)

    ics_text = '\r\n'.join([
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Aira HRMS//Interview Scheduling//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:interview-{candidate.id}@airahrms',
        f'DTSTAMP:{_fmt(datetime.now(UTC))}',
        f'DTSTART:{_fmt(start_dt)}',
        f'DTEND:{_fmt(end_dt)}',
        f'SUMMARY:{summary}',
        f'DESCRIPTION:{description}',
        f'LOCATION:{location}',
        'END:VEVENT',
        'END:VCALENDAR',
        '',
    ])
    return ('interview_invite.ics', ics_text.encode('utf-8'), 'text/calendar')


def _advance_status_on_interview_scheduled(candidate):
    """
    Move a still-pending candidate to "Interview Scheduled" once an
    interview_date is set. Nothing else in the app does this — without it,
    a candidate can receive the interview-scheduled email while the pipeline
    still shows them as "Pending". Only advances from pending; never
    overwrites a later pipeline stage (e.g. rescheduling someone already
    "selected" shouldn't regress their status).
    """
    if candidate.interview_date and candidate.status == Candidate.STATUS_PENDING:
        candidate.status = Candidate.STATUS_INTERVIEW_SCHEDULED
        candidate.save(update_fields=['status'])


def _fire_interview_date_emails_if_needed(candidate, old_interview_date, old_interview_time=None, old_meeting_link=None):
    """
    Fire interview scheduled emails when interview_date, interview_time, or
    meeting_link changes — a candidate needs to be re-notified if the time
    shifts or a video link gets added/changed, even when the date itself
    stays the same.
    """
    if candidate.interview_date is None:
        return
    unchanged = (
        old_interview_date == candidate.interview_date
        and old_interview_time == candidate.interview_time
        and old_meeting_link == candidate.meeting_link
    )
    if unchanged:
        return

    from apps.recruitment.tasks import send_interview_scheduled_emails_task

    def _dispatch(candidate_id=candidate.pk):
        try:
            # retry=False + ignore_result=True — see the referral-submission
            # dispatch above for why: apply_async() otherwise subscribes to
            # a Redis pub/sub result channel nothing here reads, retrying up
            # to 20 times against the result backend if Redis is unreachable.
            send_interview_scheduled_emails_task.apply_async(
                args=[candidate_id], retry=False, ignore_result=True,
            )
        except Exception as exc:
            logger.error(
                'Failed to queue interview-scheduled email for candidate %s: %s',
                candidate_id, exc, exc_info=True,
            )

    transaction.on_commit(_dispatch)


def _portal_login_status(candidate):
    return {
        'id':                      candidate.pk,
        'name':                    candidate.name,
        'email':                   candidate.email,
        'portal_credentials_sent': candidate.portal_credentials_sent,
        'has_portal_account':      candidate.portal_user_id is not None,
        'candidate_status':        candidate.status,
    }


def _revoke_portal_access(request, pk):
    """Deactivate portal user account and clear credentials flag on candidate."""
    if not _has_perm(request.user, 'recruitment.edit'):
        return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
    try:
        with transaction.atomic():
            candidate = Candidate.objects.select_related('branch').select_for_update().get(pk=pk)
            if not _can_access_candidate(request.user, candidate):
                return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
            if not candidate.portal_credentials_sent or not candidate.portal_user_id:
                return error(
                    'No active portal account found for this candidate.',
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            portal_user = candidate.portal_user
            if portal_user:
                portal_user.is_active = False
                portal_user.save(update_fields=['is_active', 'updated_at'])
            candidate.portal_credentials_sent = False
            candidate.save(update_fields=['portal_credentials_sent', 'updated_at'])
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_WARN,
                title='Portal access revoked',
                description=f'Revoked by {request.user.full_name or request.user.email}',
            )
            AuditLog.objects.create(
                user=request.user, action='portal_access_revoked', module='recruitment',
                object_id=str(candidate.pk),
                changes={'email': candidate.email},
                branch=candidate.branch.branch_name if candidate.branch else '',
                ip_address=get_client_ip(request),
            )
    except Candidate.DoesNotExist:
        return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
    except Exception as exc:
        logger.error('_revoke_portal_access failed pk=%s: %s', pk, exc, exc_info=True)
        return error('Failed to revoke portal access. Please try again.',
                     http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    logger.info('Portal access revoked for candidate %s by %s', pk, request.user.email)
    return success('Portal access revoked successfully.')


_IMPORT_COL_MAP = {
    'full name': 'name',         'full_name': 'name',
    'candidate name': 'name',    'candidate_name': 'name',     'name': 'name',
    'email': 'email',            'email address': 'email',     'email_address': 'email',
    'phone': 'phone',            'mobile': 'phone',            'phone number': 'phone',
    'mobile number': 'phone',    'phone_number': 'phone',
    'position': 'position_applied',        'position applied': 'position_applied',
    'position_applied': 'position_applied', 'job title': 'position_applied',
    'role': 'position_applied',
    'branch': 'branch_name',     'branch name': 'branch_name', 'branch_name': 'branch_name',
    'company code': 'branch_name', 'company_code': 'branch_name', 'company code name': 'branch_name',
    'interview date': 'interview_date',    'interview_date': 'interview_date',
    'date': 'interview_date',
    'interview mode': 'interview_mode',    'interview_mode': 'interview_mode',
    'mode': 'interview_mode',
    'notes': 'notes',            'remarks': 'notes',           'comments': 'notes',
}


def _normalize_import_headers(row_dict: dict) -> dict:
    """Map raw CSV/XLSX column names to the serializer's expected field names."""
    result = {}
    for key, value in row_dict.items():
        mapped = _IMPORT_COL_MAP.get((key or '').strip().lower(), key)
        if mapped not in result:
            result[mapped] = value.strip() if isinstance(value, str) else (value or '')
    return result


def _parse_csv_rows(file) -> tuple:
    """Return (list_of_row_dicts, error_message_or_None)."""
    try:
        content = file.read().decode('utf-8-sig')
        reader  = csv.DictReader(io.StringIO(content))
        return [dict(row) for row in reader], None
    except Exception as exc:
        return [], f'Failed to read CSV file: {exc}'


def _xlsx_cell_to_str(value) -> str:
   
    import datetime as _dt
    if isinstance(value, _dt.datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, _dt.date):
        return value.strftime('%Y-%m-%d')
    return str(value).strip() if value is not None else ''


def _parse_xlsx_rows(file) -> tuple:
    """Return (list_of_row_dicts, error_message_or_None)."""
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError:
        return [], 'Excel support is unavailable on this server. Upload a .csv file instead.'
    try:
        wb       = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws       = wb.active
        row_iter = ws.iter_rows(values_only=True)
        headers  = [str(h).strip() if h is not None else '' for h in next(row_iter, [])]
        if not any(headers):
            wb.close()
            return [], 'The Excel file has no header row.'
        rows = []
        for row_values in row_iter:
            if all(v is None for v in row_values):
                continue
            rows.append({
                headers[i]: _xlsx_cell_to_str(v)
                for i, v in enumerate(row_values)
                if i < len(headers)
            })
        wb.close()
        return rows, None
    except Exception as exc:
        return [], f'Failed to read Excel file: {exc}'


__all__ = [
    '_IMPORT_COL_MAP',
    '_can_access_candidate',
    '_scoped_candidate_branch',
    '_send_candidate_email',
    '_send_referral_email',
    '_send_referral_submission_emails',
    '_send_interview_scheduled_emails',
    '_send_interview_scheduled_email_general',
    '_build_interview_ics',
    '_advance_status_on_interview_scheduled',
    '_fire_interview_date_emails_if_needed',
    '_portal_login_status',
    '_revoke_portal_access',
    '_normalize_import_headers',
    '_parse_csv_rows',
    '_xlsx_cell_to_str',
    '_parse_xlsx_rows',
]
