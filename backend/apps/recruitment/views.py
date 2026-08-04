import csv
import io
import logging
import secrets
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
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from core.pagination import paginate, paginated_data
from .models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule
from .serializers import (
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


def _has_perm(user, codename):
    if not user:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


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



_DENIED = 'You do not have permission to perform this action.'

# ─── Email helper ─────────────────────────────────────────────────────────────

def _send_candidate_email(candidate, template_slug, actor, extra_context=None):
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    subject      = f'Your application update — {candidate.position_applied}'
    sent_status  = CandidateEmail.STATUS_FAILED

    context = {
        'candidate_name': candidate.name,
        'position':       candidate.position_applied,
        'company_name':   company_name,
    }
    if extra_context:
        context.update(extra_context)

    try:
        send_template_email(
            recipient_email=candidate.email,
            template_name=template_slug,
            context=context,
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


# ─── Referral email helpers ───────────────────────────────────────────────────

def _send_referral_email(candidate, template_slug, recipient_email, context):
    """Send one referral-flow email and write CandidateEmail + CandidateLog records."""
    sent_status = CandidateEmail.STATUS_FAILED
    try:
        send_template_email(
            recipient_email=recipient_email,
            template_name=template_slug,
            context=context,
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
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    branch_name  = candidate.branch.branch_name if candidate.branch else ''
    referrer     = candidate.referral_by
    referrer_name = (referrer.full_name or referrer.email) if referrer else ''
    interview_date_str     = candidate.interview_date.strftime('%d %b %Y') if candidate.interview_date else ''
    interview_mode_display = candidate.get_interview_mode_display()

    # Email A — to the referred candidate
    _send_referral_email(
        candidate=candidate,
        template_slug='referral_interview_scheduled_candidate',
        recipient_email=candidate.email,
        context={
            'candidate_name':        candidate.name,
            'position_applied':      candidate.position_applied,
            'interview_date':        interview_date_str,
            'interview_mode_display': interview_mode_display,
            'branch_name':           branch_name,
            'company_name':          company_name,
        },
    )

    # Email B — to the referring employee
    if referrer and referrer.email:
        _send_referral_email(
            candidate=candidate,
            template_slug='referral_interview_scheduled_referrer',
            recipient_email=referrer.email,
            context={
                'referrer_name':    referrer_name,
                'candidate_name':   candidate.name,
                'position_applied': candidate.position_applied,
                'interview_date':   interview_date_str,
                'company_name':     company_name,
            },
        )


def _send_interview_scheduled_email_general(candidate):
    """Background: notify a non-referred candidate when their interview date is first set."""
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    branch_name  = candidate.branch.branch_name if candidate.branch else ''
    interview_date_str     = candidate.interview_date.strftime('%d %b %Y') if candidate.interview_date else ''
    interview_mode_display = candidate.get_interview_mode_display()

    _send_referral_email(
        candidate=candidate,
        template_slug='interview_scheduled_candidate',
        recipient_email=candidate.email,
        context={
            'candidate_name':         candidate.name,
            'position_applied':       candidate.position_applied,
            'interview_date':         interview_date_str,
            'interview_mode_display': interview_mode_display,
            'branch_name':            branch_name,
            'company_name':           company_name,
        },
    )


def _fire_interview_date_emails_if_needed(candidate, old_interview_date):
    """Queue interview-scheduled emails when interview_date is set or changed."""
    if candidate.interview_date is None:
        return
    if old_interview_date == candidate.interview_date:
        return

    from apps.recruitment.tasks import send_interview_scheduled_emails_task

    def _dispatch(candidate_id=candidate.pk):
        try:
            send_interview_scheduled_emails_task.delay(candidate_id)
        except Exception as exc:
            logger.error(
                'Failed to queue interview-scheduled email for candidate %s: %s',
                candidate_id, exc, exc_info=True,
            )

    transaction.on_commit(_dispatch)


# ─── Candidate List + Create ──────────────────────────────────────────────────

class CandidateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = Candidate.objects.select_related('interviewer', 'referral_by', 'added_by', 'branch').all()

        # Non-admin users are locked to their own branch — the branch query
        # param (used for the admin branch-picker dropdown) is only honoured
        # for settings.edit holders, mirroring leave/expense list scoping.
        is_admin = _has_perm(request.user, 'settings.edit')
        user_branch = (getattr(request.user, 'branch', '') or '').strip()
        if not is_admin and user_branch:
            qs = qs.filter(branch__branch_name__iexact=user_branch)

        if s := request.query_params.get('status'):
            if s in {Candidate.STATUS_PENDING, Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED}:
                qs = qs.filter(status=s)

        if b := request.query_params.get('branch'):
            if is_admin:
                try:
                    qs = qs.filter(branch_id=int(b))
                except (ValueError, TypeError):
                    pass

        if q := request.query_params.get('search'):
            qs = qs.filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(position_applied__icontains=q)
            )

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Candidates retrieved.', data={
            'count':          paginator.count,
            'page':           page_obj.number,
            'page_size':      page_size,
            'total_pages':    paginator.num_pages,
            'status_choices': CandidateStatusView._STATUS_CHOICES,
            'results':        CandidateListSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        if not _has_perm(request.user, 'recruitment.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        serializer = CandidateCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        with transaction.atomic():
            candidate = serializer.save(added_by=request.user)

            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_INFO,
                title='Added to interview list',
                description=f'Added by {request.user.full_name or request.user.email}',
            )
            AuditLog.objects.create(
                user=request.user, action='candidate_created', module='recruitment',
                object_id=str(candidate.pk),
                changes={'name': candidate.name, 'position': candidate.position_applied},
                ip_address=get_client_ip(request),
            )
        _fire_interview_date_emails_if_needed(candidate, old_interview_date=None)
        logger.info('Candidate %s created by %s', candidate.id, request.user.email)
        return success('Candidate added to interview list.', data=CandidateListSerializer(candidate).data,
                  http_status=status.HTTP_201_CREATED)

    def put(self, request):
        return error(
            f'PUT is not supported on {request.path}. '
            'Use PUT /candidates/<id>/ to update a specific candidate.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return error(
            f'PATCH is not supported on {request.path}. '
            'Use PATCH /candidates/<id>/ to partially update a specific candidate.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def delete(self, request):
        """Bulk delete candidates by ID list. Skips converted / portal-credentials-sent candidates."""
        if not _has_perm(request.user, 'recruitment.delete'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get('ids')
        if not ids or not isinstance(ids, list):
            return error('Provide a non-empty list of candidate IDs in "ids".',
                         http_status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = [int(i) for i in ids]
        except (ValueError, TypeError):
            return error('All values in "ids" must be integers.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if len(ids) > 100:
            return error('Cannot delete more than 100 candidates at once.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        qs        = Candidate.objects.filter(pk__in=ids)
        deletable = qs.exclude(status=Candidate.STATUS_CONVERTED).exclude(portal_credentials_sent=True)
        skipped   = qs.count() - deletable.count()

        if deletable.count() == 0:
            return error(
                'No deletable candidates found. Converted candidates and those with '
                'portal credentials already sent cannot be deleted.',
                http_status=status.HTTP_409_CONFLICT,
            )

        for candidate in deletable:
            AuditLog.objects.create(
                user=request.user, action='candidate_deleted', module='recruitment',
                object_id=str(candidate.pk),
                changes={'name': candidate.name},
                ip_address=get_client_ip(request),
            )
        count = deletable.count()
        deletable.delete()

        msg = f'{count} candidate(s) deleted.'
        if skipped:
            msg += f' {skipped} skipped (converted or portal credentials sent).'
        logger.info('%s by %s', msg, request.user.email)
        return success(msg)


# ─── Candidate Detail ─────────────────────────────────────────────────────────

class CandidateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Candidate.objects.select_related(
                'interviewer', 'referral_by', 'added_by', 'branch'
            ).prefetch_related('logs').get(pk=pk)
        except Candidate.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success('Candidate retrieved.', data=CandidateDetailSerializer(candidate).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot edit a candidate who has already been converted to an employee.')

        serializer = CandidateUpdateSerializer(candidate, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        old_interview_date = candidate.interview_date
        try:
            updated = serializer.save()
        except Exception as exc:
            logger.error('CandidateDetailView PUT failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to update candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        AuditLog.objects.create(
            user=request.user, action='candidate_updated', module='recruitment',
            object_id=str(updated.pk),
            changes={k: v for k, v in request.data.items()},
            ip_address=get_client_ip(request),
        )
        _fire_interview_date_emails_if_needed(updated, old_interview_date)
        logger.info('Candidate %s fully updated by %s', pk, request.user.email)
        return success('Candidate updated.', data=CandidateDetailSerializer(updated).data)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot edit a candidate who has already been converted to an employee.')

        serializer = CandidateUpdateSerializer(candidate, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        old_interview_date = candidate.interview_date
        try:
            updated = serializer.save()
        except Exception as exc:
            logger.error('CandidateDetailView PATCH failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to update candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        AuditLog.objects.create(
            user=request.user, action='candidate_updated', module='recruitment',
            object_id=str(updated.pk),
            changes={k: v for k, v in request.data.items()},
            ip_address=get_client_ip(request),
        )
        _fire_interview_date_emails_if_needed(updated, old_interview_date)
        logger.info('Candidate %s partially updated by %s', pk, request.user.email)
        return success('Candidate updated.', data=CandidateDetailSerializer(updated).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'recruitment.delete'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error(
                'Cannot delete a candidate who has been converted to an employee.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if candidate.portal_credentials_sent:
            return error(
                'Cannot delete a candidate whose portal login has already been sent. '
                'Deactivate their portal account first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        name = candidate.name
        try:
            candidate.delete()
        except Exception as exc:
            logger.error('CandidateDetailView DELETE failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to delete candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        AuditLog.objects.create(
            user=request.user, action='candidate_deleted', module='recruitment',
            object_id=str(pk),
            changes={'name': name},
            ip_address=get_client_ip(request),
        )
        logger.info('Candidate "%s" (pk=%s) deleted by %s', name, pk, request.user.email)
        return success(f'Candidate "{name}" deleted successfully.')

    def post(self, request, pk):
        return self.put(request, pk)


# ─── Status choices (no pk needed — same for all candidates) ─────────────────

class CandidateStatusChoicesView(APIView):
    """GET /api/recruitment/candidates/status-choices/
    Returns the list of selectable statuses for the frontend dropdown.
    Call this ONCE on page load — choices never vary per candidate.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success(
            'Status choices retrieved.',
            data=CandidateStatusView._STATUS_CHOICES,
        )


# ─── Mark Selected / Rejected ─────────────────────────────────────────────────

class CandidateStatusView(APIView):
    permission_classes = [IsAuthenticated]

    # Statuses available in the dropdown — excludes system-managed ones
    # (OFFER_SENT is set by portal login flow; CONVERTED is set by onboarding approval)
    _STATUS_CHOICES = [
        {'value': Candidate.STATUS_PENDING,             'label': 'Pending'},
        {'value': Candidate.STATUS_SCREENING,           'label': 'Screening'},
        {'value': Candidate.STATUS_INTERVIEW_SCHEDULED, 'label': 'Interview Scheduled'},
        {'value': Candidate.STATUS_INTERVIEW_DONE,      'label': 'Interview Done'},
        {'value': Candidate.STATUS_SELECTED,            'label': 'Selected'},
        {'value': Candidate.STATUS_REJECTED,            'label': 'Rejected'},
    ]
    _VALID_STATUS_VALUES = frozenset(c['value'] for c in _STATUS_CHOICES)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            candidate = Candidate.objects.select_related('branch').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if new_status not in self._VALID_STATUS_VALUES:
            valid_labels = ', '.join(c['label'] for c in self._STATUS_CHOICES)
            return error(f'Invalid status. Choose from: {valid_labels}.')

        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot change status of a converted candidate.')

        remarks    = request.data.get('remarks', '')
        actor_name = request.user.full_name or request.user.email

        candidate.status = new_status
        candidate.save(update_fields=['status', 'updated_at'])

        CandidateLog.objects.create(
            candidate=candidate,
            log_type=(CandidateLog.TYPE_SUCCESS
                      if new_status not in (Candidate.STATUS_REJECTED,)
                      else CandidateLog.TYPE_ERROR),
            title=f'Status changed to {new_status.replace("_", " ").title()}',
            description=f'By {actor_name}. {remarks}'.strip('. '),
        )

        # Send email only for selected or rejected transitions
        email_sent = False
        if new_status in (Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED):
            default_slug      = 'candidate_selected' if new_status == Candidate.STATUS_SELECTED else 'candidate_rejected'
            raw_template_name = request.data.get('template_name')
            template_slug     = (str(raw_template_name).strip() if raw_template_name else default_slug)
            email_status  = _send_candidate_email(candidate, template_slug, request.user)
            email_sent    = (email_status == CandidateEmail.STATUS_SENT)
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=(CandidateLog.TYPE_SUCCESS if email_sent else CandidateLog.TYPE_WARN),
                title=('Notification email sent'
                       if email_sent
                       else 'Email failed — check SMTP settings'),
                description=f'Template: {template_slug}',
            )

        # Note: referral bonus auto-creation on conversion lives in
        # OnboardingApprovalView (apps/accounts/views.py) — STATUS_CONVERTED
        # is never a reachable value here (excluded from _VALID_STATUS_VALUES
        # above), since candidates are only ever converted via onboarding
        # approval, not through this status-change endpoint.

        AuditLog.objects.create(
            user=request.user, action=f'candidate_{new_status}', module='recruitment',
            object_id=str(candidate.pk),
            changes={'name': candidate.name, 'status': new_status},
            ip_address=get_client_ip(request),
        )

        status_label = new_status.replace('_', ' ').title()
        if email_sent:
            msg = f'{candidate.name} marked as {status_label}. Notification email sent.'
        elif new_status in (Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED):
            msg = f'{candidate.name} marked as {status_label}. Email could not be sent — check SMTP settings.'
        else:
            msg = f'{candidate.name} marked as {status_label}.'

        return success(
            msg,
            data=CandidateListSerializer(candidate).data,
        )

    def get(self, request, pk):
        """Return current status + dropdown choices for the frontend select element."""
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.prefetch_related('logs').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)

        # Status change history from logs, newest first
        history = [
            {
                'title':      log.title,
                'log_type':   log.log_type,
                'description': log.description,
                'created_at': log.created_at,
            }
            for log in candidate.logs.filter(title__icontains='status').order_by('-created_at')[:10]
        ]

        return success('Status retrieved.', data={
            'id':             candidate.pk,
            'name':           candidate.name,
            'current_status': candidate.status,
            'updated_at':     candidate.updated_at,
            'choices':        self._STATUS_CHOICES,   # ready-made for <select> / dropdown
            'history':        history,
        })

    def post(self, request, pk):
        return self.patch(request, pk)

    def put(self, request, pk):
        return self.patch(request, pk)

    def delete(self, request, pk):
        """Reset candidate status back to Pending."""
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot reset status of a converted candidate.')
        if candidate.status == Candidate.STATUS_PENDING:
            return success('Status is already Pending.', data=CandidateListSerializer(candidate).data)
        old_status = candidate.status
        candidate.status = Candidate.STATUS_PENDING
        candidate.save(update_fields=['status', 'updated_at'])
        CandidateLog.objects.create(
            candidate=candidate,
            log_type=CandidateLog.TYPE_INFO,
            title='Status reset to Pending',
            description=f'Reset from {old_status.replace("_", " ").title()} '
                        f'by {request.user.full_name or request.user.email}',
        )
        AuditLog.objects.create(
            user=request.user, action='candidate_status_reset', module='recruitment',
            object_id=str(candidate.pk),
            changes={'from': old_status, 'to': Candidate.STATUS_PENDING},
            ip_address=get_client_ip(request),
        )
        return success(f'{candidate.name} status reset to Pending.',
                       data=CandidateListSerializer(candidate).data)


# ─── HR Decision (Candidate Review) ──────────────────────────────────────────

class CandidateHRDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.approve'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            candidate = Candidate.objects.get(pk=pk, status=Candidate.STATUS_SELECTED)
        except Candidate.DoesNotExist:
            return error('Candidate not found or not selected.', http_status=status.HTTP_404_NOT_FOUND)

        decision = request.data.get('decision')
        if decision not in {'approve', 'reject'}:
            return error('decision must be "approve" or "reject".')

        remarks    = request.data.get('remarks', '')
        actor_name = request.user.full_name or request.user.email

        if decision == 'approve':
            # Template selection: default to welcome_employee if not specified
            template_name = (request.data.get('template_name') or 'welcome_employee').strip()

            # Sanitize extra_context: only string-keyed, identifier-named entries
            raw_extra = request.data.get('extra_context') or {}
            extra_context = {}
            if isinstance(raw_extra, dict):
                for k, v in raw_extra.items():
                    if isinstance(k, str) and k.isidentifier() and len(k) <= 100:
                        extra_context[k] = str(v)[:2000]

            candidate.hr_approved = True
            candidate.save(update_fields=['hr_approved', 'updated_at'])
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_SUCCESS,
                title='HR Approved — Onboarded as Employee',
                description=f'Approved by {actor_name}. {remarks}'.strip('. '),
            )
            email_status = _send_candidate_email(candidate, template_name, request.user, extra_context)
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=(CandidateLog.TYPE_SUCCESS
                          if email_status == CandidateEmail.STATUS_SENT
                          else CandidateLog.TYPE_WARN),
                title=('Onboarding email sent'
                       if email_status == CandidateEmail.STATUS_SENT
                       else 'Onboarding email failed — check SMTP settings'),
                description=f'Using template: {template_name}',
            )

            # Auto-assign default assessments so candidate must complete them
            # before accessing the employment portal
            if candidate.portal_user_id:
                from apps.assessments.models import Assessment, AssessmentItem, CandidateAssignment
                from apps.accounts.models import User as _User
                default_assessments = list(
                    Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
                )
                assigned_assessments = []
                for assessment in default_assessments:
                    max_score = assessment.items.filter(item_type=AssessmentItem.TYPE_QUIZ).count()
                    _, created = CandidateAssignment.objects.get_or_create(
                        candidate=candidate,
                        assessment=assessment,
                        defaults={'assigned_by': request.user, 'max_score': max_score},
                    )
                    if created:
                        assigned_assessments.append(assessment)

                if assigned_assessments:
                    portal_user = candidate.portal_user
                    portal_user.assessment_status = _User.ASSESSMENT_PENDING
                    portal_user.save(update_fields=['assessment_status', 'updated_at'])

                    company      = Company.objects.first()
                    company_name = company.company_name if company else ''
                    portal_url   = (company.portal_url if company else '') or ''
                    for assessment in assigned_assessments:
                        try:
                            send_template_email(
                                recipient_email=candidate.email,
                                template_name='assessment_assigned',
                                context={
                                    'candidate_name':   candidate.name,
                                    'assessment_title': assessment.title,
                                    'company_name':     company_name,
                                    'portal_url':       portal_url,
                                },
                            )
                        except Exception:
                            logger.exception(
                                'Failed to send assessment_assigned email for "%s" to %s',
                                assessment.title, candidate.email,
                            )

            msg = f'{candidate.name} approved and onboarded!'
        else:
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_WARN,
                title='HR requested revision',
                description=f'Remarks: {remarks or "Please recheck documents"}',
            )
            msg = 'Revision requested. Candidate notified.'

        AuditLog.objects.create(
            user=request.user, action=f'candidate_hr_{decision}d', module='recruitment',
            object_id=str(candidate.pk),
            changes={'name': candidate.name, 'decision': decision},
            ip_address=get_client_ip(request),
        )

        return success(msg, data=CandidateDetailSerializer(candidate).data)

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('HR decision status retrieved.', data={
            'id':          candidate.pk,
            'name':        candidate.name,
            'status':      candidate.status,
            'hr_approved': candidate.hr_approved,
            'updated_at':  candidate.updated_at,
        })

    def post(self, request, pk):
        return self.patch(request, pk)

    def put(self, request, pk):
        return self.patch(request, pk)

    def delete(self, request, pk):
        """Reset HR approval — sets hr_approved back to False."""
        if not _has_perm(request.user, 'recruitment.approve'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not candidate.hr_approved:
            return success('HR decision has not been set — nothing to reset.',
                           data={'hr_approved': False})
        candidate.hr_approved = False
        candidate.save(update_fields=['hr_approved', 'updated_at'])
        CandidateLog.objects.create(
            candidate=candidate,
            log_type=CandidateLog.TYPE_WARN,
            title='HR approval reset',
            description=f'Reset by {request.user.full_name or request.user.email}',
        )
        AuditLog.objects.create(
            user=request.user, action='candidate_hr_decision_reset', module='recruitment',
            object_id=str(candidate.pk),
            changes={'hr_approved': False},
            ip_address=get_client_ip(request),
        )
        logger.info('HR approval reset for candidate %s by %s', pk, request.user.email)
        return success('HR approval reset.', data=CandidateDetailSerializer(candidate).data)


# ─── Candidate Review list (selected only, with logs) ─────────────────────────

class CandidateReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (Candidate.objects
              .filter(status=Candidate.STATUS_SELECTED)
              .select_related('interviewer', 'added_by')
              .prefetch_related('logs')
              .order_by('-updated_at'))

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Selected candidates retrieved.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     CandidateDetailSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        return self.get(request)

    def put(self, request):
        return error(
            f'PUT is not supported on {request.path}. '
            'Use PATCH /candidates/<id>/hr-decision/ to submit an HR decision.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return self.put(request)

    def delete(self, request):
        return error(
            f'DELETE is not supported on {request.path}. '
            'Use DELETE /candidates/<id>/hr-decision/ to reset a specific candidate\'s HR decision.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ─── Email Logs ────────────────────────────────────────────────────────────────

class CandidateEmailLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (CandidateEmail.objects
              .select_related('candidate', 'sent_by')
              .order_by('-sent_at'))

        if q := request.query_params.get('search'):
            if len(q) > 100:
                return error('search must be 100 characters or fewer.')
            qs = qs.filter(candidate__name__icontains=q) | qs.filter(to_email__icontains=q)

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 20

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Email logs retrieved.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     CandidateEmailSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        return self.get(request)

    def put(self, request):
        return error(
            f'PUT is not supported on {request.path}. Email logs are read-only records.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return self.put(request)

    def delete(self, request):
        return error(
            f'DELETE is not supported on {request.path}. Email logs are permanent audit records.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ─── Manual Email Send ─────────────────────────────────────────────────────────

class SendCandidateEmailView(APIView):
    """
    POST /candidates/<pk>/send-email/
    HR manually sends any active email template to a specific candidate.

    Body:
        template_name  (str, required) — name of an active EmailTemplate
        extra_context  (dict, optional) — additional variables to merge into the template
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        template_name = request.data.get('template_name', '').strip()
        if not template_name:
            return error('template_name is required.')
        if len(template_name) > 100:
            return error('template_name must be 100 characters or fewer.')

        extra_context = request.data.get('extra_context', {})
        if not isinstance(extra_context, dict):
            return error('extra_context must be an object.')

        # Resolve recipient — Candidate (recruited) or User (direct hire)
        candidate   = None
        direct_user = None

        if str(pk).isdigit():
            try:
                candidate = Candidate.objects.select_related('branch', 'referral_by').get(id=int(pk))
            except Candidate.DoesNotExist:
                return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        else:
            # Try recruited path: Candidate linked to a portal user with this employee_id
            candidate = (
                Candidate.objects
                .select_related('branch', 'referral_by')
                .filter(portal_user__employee_id=pk)
                .first()
            )
            if not candidate:
                # Fallback: direct-hire employee — look up User directly
                try:
                    direct_user = User.objects.select_related('role').get(employee_id=pk)
                except User.DoesNotExist:
                    return error(
                        f'No candidate or employee found with ID "{pk}".',
                        http_status=status.HTTP_404_NOT_FOUND,
                    )

        company      = Company.objects.first()
        company_name = company.company_name if company else ''

        if candidate:
            recipient_email = candidate.email
            context = {
                'candidate_name':         candidate.name,
                'position_applied':       candidate.position_applied,
                'company_name':           company_name,
                'branch_name':            candidate.branch.branch_name if candidate.branch else '',
                'interview_date':         (
                    candidate.interview_date.strftime('%d %b %Y')
                    if candidate.interview_date else ''
                ),
                'interview_mode_display': candidate.get_interview_mode_display(),
                'status_display':         candidate.get_status_display(),
                'referrer_name':          (
                    (direct_ref := candidate.referral_by) and
                    (direct_ref.full_name or direct_ref.email) or ''
                ),
            }
        else:
            # Direct-hire employee — build context from User model
            recipient_email = direct_user.email
            context = {
                'candidate_name':         direct_user.full_name or direct_user.email,
                'position_applied':       direct_user.designation or '',
                'company_name':           company_name,
                'branch_name':            direct_user.branch or '',
                'interview_date':         '',
                'interview_mode_display': '',
                'status_display':         '',
                'referrer_name':          '',
            }

        context.update(extra_context)

        sent_status = CandidateEmail.STATUS_FAILED
        try:
            send_template_email(
                recipient_email=recipient_email,
                template_name=template_name,
                context=context,
            )
            sent_status = CandidateEmail.STATUS_SENT
            logger.info(
                'Manual email "%s" sent to %s by %s',
                template_name, recipient_email, request.user.email,
            )
        except LookupError as exc:
            return error(str(exc), http_status=status.HTTP_404_NOT_FOUND)
        except Exception:
            logger.exception(
                'Manual email "%s" failed for pk=%s', template_name, pk,
            )
            return error('Failed to send email. Check SMTP configuration.')
        finally:
            if candidate:
                CandidateEmail.objects.create(
                    candidate=candidate,
                    template_used=template_name,
                    subject=template_name,
                    to_email=recipient_email,
                    status=sent_status,
                    sent_by=request.user,
                )

        AuditLog.objects.create(
            user=request.user,
            action='manual_email_sent',
            module='recruitment',
            object_id=str(candidate.pk) if candidate else str(pk),
            changes={'template_name': template_name, 'recipient': recipient_email},
            ip_address=get_client_ip(request),
        )
        return success(f'Email sent to {recipient_email}.')


# ─── Stats ─────────────────────────────────────────────────────────────────────

class CandidateStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        total    = Candidate.objects.count()
        pending  = Candidate.objects.filter(status=Candidate.STATUS_PENDING).count()
        selected = Candidate.objects.filter(status=Candidate.STATUS_SELECTED).count()
        rejected = Candidate.objects.filter(status=Candidate.STATUS_REJECTED).count()
        pending_review = Candidate.objects.filter(
            status=Candidate.STATUS_SELECTED, details_filled=True, hr_approved=False
        ).count()

        return success('Recruitment stats retrieved.', data={
            'total': total, 'pending': pending,
            'selected': selected, 'rejected': rejected,
            'pending_review': pending_review,
        })

    def post(self, request):
        return self.get(request)

    def put(self, request):
        return error(
            f'PUT is not supported on {request.path}. Stats are computed — no data to update.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return self.put(request)

    def delete(self, request):
        return error(
            f'DELETE is not supported on {request.path}. Stats are computed — no data to delete.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


# ─── Portal helpers ────────────────────────────────────────────────────────────

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
            candidate = Candidate.objects.select_for_update().get(pk=pk)
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


# ─── Send Portal Login (candidate onboarding invite) ──────────────────────────

class SendPortalLoginView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            candidate = Candidate.objects.select_for_update().get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)

        if candidate.status not in (
            Candidate.STATUS_SELECTED,
            Candidate.STATUS_INTERVIEW_DONE,
        ):
            return error('Candidate must be at least at Interview Done stage before sending portal login.')

        if candidate.portal_credentials_sent and candidate.portal_user_id:
            return error('Portal login already sent. Use resend if you want to issue new credentials.')

        if not candidate.email or not candidate.email.strip():
            return error('Candidate does not have a valid email address.')

        if User.objects.filter(email__iexact=candidate.email).exists():
            return error(
                'A portal account already exists for this email address.',
                http_status=status.HTTP_409_CONFLICT,
            )

        # portal_url: request body overrides company setting
        portal_url_override = (request.data.get('portal_url') or '').strip()
        if portal_url_override and not portal_url_override.startswith(('http://', 'https://')):
            return error('portal_url must start with http:// or https://.')

        # Generate a temporary password
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        # Create portal user account
        portal_user = User.objects.create_user(
            email            = candidate.email,
            password         = temp_password,
            full_name        = candidate.name,
            must_change_password = True,
            onboarding_status    = User.ONBOARDING_PENDING,
        )

        candidate.portal_user             = portal_user
        candidate.portal_credentials_sent = True
        candidate.status                  = Candidate.STATUS_OFFER_SENT
        candidate.save(update_fields=['portal_user', 'portal_credentials_sent', 'status', 'updated_at'])

        # Assessments are assigned after HR approval, not at portal login.
        # Set complete so the candidate goes straight to the onboarding wizard.
        portal_user.assessment_status = User.ASSESSMENT_COMPLETE
        portal_user.save(update_fields=['assessment_status', 'updated_at'])

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = portal_url_override or (company.portal_url if company else '') or ''

        CandidateLog.objects.create(
            candidate=candidate,
            log_type=CandidateLog.TYPE_INFO,
            title='Portal login sent',
            description=f'Account created for {candidate.email}. Sent by {request.user.full_name or request.user.email}.',
        )

        sent_status = CandidateEmail.STATUS_FAILED
        try:
            send_template_email(
                recipient_email=candidate.email,
                template_name='portal_invite',
                context={
                    'candidate_name': candidate.name,
                    'position':       candidate.position_applied,
                    'company_name':   company_name,
                    'login_email':    candidate.email,
                    'temp_password':  temp_password,
                    'portal_url':     portal_url,
                },
            )
            sent_status = CandidateEmail.STATUS_SENT
        except Exception as exc:
            logger.exception('Failed to send portal invite to %s: %s', candidate.email, exc)

        CandidateEmail.objects.create(
            candidate=candidate,
            template_used='portal_invite',
            subject=f'Your Portal Login — {company_name}',
            to_email=candidate.email,
            status=sent_status,
            sent_by=request.user,
        )
        CandidateLog.objects.create(
            candidate=candidate,
            log_type=(CandidateLog.TYPE_SUCCESS
                      if sent_status == CandidateEmail.STATUS_SENT
                      else CandidateLog.TYPE_WARN),
            title=('Portal invite email sent'
                   if sent_status == CandidateEmail.STATUS_SENT
                   else 'Portal invite email failed — check SMTP settings'),
            description=f'To: {candidate.email}',
        )
        AuditLog.objects.create(
            user=request.user, action='portal_login_sent', module='recruitment',
            object_id=str(candidate.pk),
            changes={'email': candidate.email},
            ip_address=get_client_ip(request),
        )
        return success('Portal login sent successfully.', data={'email': candidate.email})

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Portal login status retrieved.', data=_portal_login_status(candidate))

    def put(self, request, pk):
        return self.post(request, pk)

    def patch(self, request, pk):
        return self.post(request, pk)

    def delete(self, request, pk):
        return _revoke_portal_access(request, pk)


# ─── Resend Portal Login ───────────────────────────────────────────────────────

class ResendPortalLoginView(APIView):
   
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            candidate = Candidate.objects.select_for_update().get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)

        if not candidate.portal_credentials_sent or not candidate.portal_user_id:
            return error(
                'Portal login has not been sent yet. Use Send Portal Login first.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        portal_user = candidate.portal_user
        if not portal_user:
            return error('Linked portal user account no longer exists.')

        if portal_user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error('This candidate has already completed onboarding and cannot receive new credentials.')

        # Generate and set a fresh temporary password
        alphabet      = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        portal_user.set_password(temp_password)
        portal_user.must_change_password = True
        portal_user.save(update_fields=['password', 'must_change_password'])

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url_override = (request.data.get('portal_url') or '').strip()
        if portal_url_override and not portal_url_override.startswith(('http://', 'https://')):
            return error('portal_url must start with http:// or https://.')
        portal_url = portal_url_override or (company.portal_url if company else '') or ''

        context = {
            'candidate_name': candidate.name,
            'position':       candidate.position_applied,
            'company_name':   company_name,
            'login_email':    candidate.email,
            'temp_password':  temp_password,
            'portal_url':     portal_url,
        }
        sent_status = CandidateEmail.STATUS_FAILED
        try:
            send_template_email(
                recipient_email=candidate.email,
                template_name='portal_invite',
                context=context,
            )
            sent_status = CandidateEmail.STATUS_SENT
        except Exception as exc:
            logger.exception('Failed to resend portal invite to %s: %s', candidate.email, exc)

        CandidateEmail.objects.create(
            candidate=candidate,
            template_used='portal_invite',
            subject=f'Your Portal Login (Resent) — {company_name}',
            to_email=candidate.email,
            status=sent_status,
            sent_by=request.user,
        )
        CandidateLog.objects.create(
            candidate=candidate,
            log_type=(CandidateLog.TYPE_SUCCESS
                      if sent_status == CandidateEmail.STATUS_SENT
                      else CandidateLog.TYPE_WARN),
            title=('Portal credentials resent'
                   if sent_status == CandidateEmail.STATUS_SENT
                   else 'Portal credentials resend failed — check SMTP settings'),
            description=f'New credentials issued to {candidate.email} by {request.user.full_name or request.user.email}.',
        )
        AuditLog.objects.create(
            user=request.user, action='portal_login_resent', module='recruitment',
            object_id=str(candidate.pk),
            changes={'email': candidate.email},
            ip_address=get_client_ip(request),
        )
        return success('Portal credentials resent successfully.', data={'email': candidate.email})

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Portal login status retrieved.', data=_portal_login_status(candidate))

    def put(self, request, pk):
        return self.post(request, pk)

    def patch(self, request, pk):
        return self.post(request, pk)

    def delete(self, request, pk):
        return _revoke_portal_access(request, pk)



# ─── Referrals ────────────────────────────────────────────────────────────────

class ReferralListCreateView(APIView):
   
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = (
            Candidate.objects
            .select_related('branch', 'interviewer', 'referral_by', 'added_by')
            .filter(referral_by=request.user)
        )
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = CandidateListSerializer(page_obj.object_list, many=True)
        return success('Referrals fetched.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        
        serializer = ReferralSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        candidate = serializer.save(
            referral_by=request.user,
            added_by=request.user,
            status=Candidate.STATUS_PENDING,
        )
        from apps.recruitment.tasks import send_referral_submission_emails_task

        def _dispatch(candidate_id=candidate.pk):
            try:
                send_referral_submission_emails_task.delay(candidate_id)
            except Exception as exc:
                logger.error(
                    'Failed to queue referral-submission email for candidate %s: %s',
                    candidate_id, exc, exc_info=True,
                )

        transaction.on_commit(_dispatch)
        logger.info('Referral submitted by %s for %s', request.user.email, candidate.email)
        return success(
            'Referral submitted successfully.',
            CandidateListSerializer(candidate).data,
            http_status=status.HTTP_201_CREATED,
        )


class ReferralAllView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        _pipeline_statuses = [
            Candidate.STATUS_PENDING,
            Candidate.STATUS_SCREENING,
            Candidate.STATUS_INTERVIEW_SCHEDULED,
            Candidate.STATUS_INTERVIEW_DONE,
            Candidate.STATUS_OFFER_SENT,
        ]

        base_qs = Candidate.objects.filter(referral_by__isnull=False)

        stats = base_qs.aggregate(
            total_referred=Count('id'),
            in_pipeline=Count('id', filter=Q(status__in=_pipeline_statuses)),
            selected=Count('id', filter=Q(status=Candidate.STATUS_SELECTED)),
            converted=Count('id', filter=Q(status=Candidate.STATUS_CONVERTED)),
        )

        queryset = base_qs.select_related('branch', 'interviewer', 'referral_by', 'added_by')
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = CandidateListSerializer(page_obj.object_list, many=True)
        data = paginated_data(paginator, page_obj, serializer.data)
        data['stats'] = {
            'total_referred': stats['total_referred'],
            'in_pipeline':    stats['in_pipeline'],
            'selected':       stats['selected'],
            'converted':      stats['converted'],
        }
        return success('Referrals fetched.', data)


# ─── Referral Rules ───────────────────────────────────────────────────────────

class ReferralRuleListCreateView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rules = ReferralRule.objects.all()
        return success('Rules fetched.', {'results': ReferralRuleSerializer(rules, many=True).data})

    def post(self, request):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = ReferralRuleSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        rule = serializer.save()
        logger.info('ReferralRule "%s" created by %s', rule.title, request.user.email)
        return success('Rule created.', ReferralRuleSerializer(rule).data, http_status=status.HTTP_201_CREATED)


class ReferralRuleDetailView(APIView):
   
    permission_classes = [IsAuthenticated]

    def _get_rule(self, pk):
        try:
            return ReferralRule.objects.get(pk=pk)
        except ReferralRule.DoesNotExist:
            return None

    def patch(self, request, pk):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        rule = self._get_rule(pk)
        if not rule:
            return error('Rule not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = ReferralRuleSerializer(rule, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('ReferralRule "%s" updated by %s', rule.title, request.user.email)
        return success('Rule updated.', ReferralRuleSerializer(rule).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        rule = self._get_rule(pk)
        if not rule:
            return error('Rule not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = rule.title
        rule.delete()
        logger.info('ReferralRule "%s" deleted by %s', title, request.user.email)
        return success('Rule deleted.', None)


# ─── Referral Bonuses ──────────────────────────────────────────────────────────

class ReferralBonusListView(APIView):
   
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get('scope', '')
        has_approve = _has_perm(request.user, 'recruitment.edit')

        if scope == 'my' or not has_approve:
            qs = (
                ReferralBonus.objects
                .select_related('candidate', 'referrer', 'approved_by', 'paid_by')
                .filter(referrer=request.user)
            )
        else:
            qs = (
                ReferralBonus.objects
                .select_related('candidate', 'referrer', 'approved_by', 'paid_by')
                .all()
            )

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        serializer = ReferralBonusSerializer(page_obj.object_list, many=True)
        return success('Referral bonuses retrieved.', paginated_data(paginator, page_obj, serializer.data))


class ReferralBonusDetailView(APIView):
    
    permission_classes = [IsAuthenticated]

    def _get_bonus(self, pk):
        try:
            return ReferralBonus.objects.select_related(
                'candidate', 'referrer', 'approved_by', 'paid_by'
            ).get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return None

    def get(self, request, pk):
        bonus = self._get_bonus(pk)
        if not bonus:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)
        has_approve = _has_perm(request.user, 'recruitment.edit')
        if not has_approve and bonus.referrer_id != request.user.id:
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success('Referral bonus retrieved.', ReferralBonusSerializer(bonus).data)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        bonus = self._get_bonus(pk)
        if not bonus:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)
        if bonus.status == ReferralBonus.STATUS_PAID:
            return error('Cannot edit a bonus that has already been paid.')

        if 'bonus_amount' in request.data:
            try:
                amount = Decimal(str(request.data['bonus_amount']))
                if amount < 0:
                    raise ValueError
            except (TypeError, ValueError, InvalidOperation):
                return error('bonus_amount must be a non-negative number.')
            bonus.bonus_amount = amount

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.save(update_fields=['bonus_amount', 'notes', 'updated_at'])
        logger.info('Referral bonus %s updated by %s', pk, request.user.email)
        return success('Referral bonus updated.', ReferralBonusSerializer(bonus).data)

    def put(self, request, pk):
        return self.patch(request, pk)


class ReferralBonusApproveView(APIView):
   
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone as tz
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            bonus = ReferralBonus.objects.select_related('candidate', 'referrer').get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)

        if bonus.status != ReferralBonus.STATUS_PENDING:
            return error(
                f'Bonus is already {bonus.get_status_display()}. Only pending bonuses can be approved.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if 'bonus_amount' in request.data:
            try:
                amount = Decimal(str(request.data['bonus_amount']))
                if amount < 0:
                    raise ValueError
                bonus.bonus_amount = amount
            except (TypeError, ValueError, InvalidOperation):
                return error('bonus_amount must be a non-negative number.')

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.status      = ReferralBonus.STATUS_APPROVED
        bonus.approved_by = request.user
        bonus.approved_at = tz.now()
        bonus.save(update_fields=['bonus_amount', 'notes', 'status', 'approved_by', 'approved_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='referral_bonus_approved', module='recruitment',
            object_id=str(bonus.pk),
            changes={'referrer': bonus.referrer.employee_id, 'amount': str(bonus.bonus_amount)},
            ip_address=get_client_ip(request),
        )
        logger.info('Referral bonus %s approved by %s (amount: %s)', pk, request.user.email, bonus.bonus_amount)
        return success(
            f'Bonus of ₹{bonus.bonus_amount} approved for {bonus.referrer.full_name}.',
            ReferralBonusSerializer(bonus).data,
        )


class ReferralBonusPayView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone as tz
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            bonus = ReferralBonus.objects.select_related('candidate', 'referrer').get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)

        if bonus.status != ReferralBonus.STATUS_APPROVED:
            return error(
                'Only approved bonuses can be marked as paid.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.status  = ReferralBonus.STATUS_PAID
        bonus.paid_by = request.user
        bonus.paid_at = tz.now()
        bonus.save(update_fields=['notes', 'status', 'paid_by', 'paid_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='referral_bonus_paid', module='recruitment',
            object_id=str(bonus.pk),
            changes={'referrer': bonus.referrer.employee_id, 'amount': str(bonus.bonus_amount)},
            ip_address=get_client_ip(request),
        )
        logger.info('Referral bonus %s marked paid by %s', pk, request.user.email)
        return success(
            f'Bonus of ₹{bonus.bonus_amount} marked as paid for {bonus.referrer.full_name}.',
            ReferralBonusSerializer(bonus).data,
        )


# ── Bulk Candidate Import ─────────────────────────────────────────────────────

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
    'interview date': 'interview_date',    'interview_date': 'interview_date',
    'date': 'interview_date',
    'interview mode': 'interview_mode',    'interview_mode': 'interview_mode',
    'mode': 'interview_mode',
    'notes': 'notes',            'remarks': 'notes',           'comments': 'notes',
}

_MAX_IMPORT_ROWS = 1000
_MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB


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


class CandidateBulkImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser]

    def post(self, request):
        if not _has_perm(request.user, 'recruitment.create'):
            return error(
                'Only HR and System Admin users can import candidates.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        upload = request.FILES.get('file')
        if not upload:
            return error(
                'No file provided. Send file= as multipart/form-data.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > _MAX_IMPORT_BYTES:
            return error(
                'File exceeds the 5 MB limit. Split the file and try again.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        fname = upload.name.lower()
        if fname.endswith('.csv'):
            rows, parse_err = _parse_csv_rows(upload)
        elif fname.endswith('.xlsx') or fname.endswith('.xls'):
            rows, parse_err = _parse_xlsx_rows(upload)
        else:
            return error(
                'Unsupported file type. Upload a .csv or .xlsx file.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        if parse_err:
            return error(parse_err, http_status=status.HTTP_400_BAD_REQUEST)
        if not rows:
            return error(
                'The file contains no data rows.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if len(rows) > _MAX_IMPORT_ROWS:
            return error(
                f'File contains {len(rows)} rows. Maximum allowed per import is '
                f'{_MAX_IMPORT_ROWS}. Split the file and upload in batches.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        # Pre-load branch lookup once for the entire batch.
        from apps.branch.models import Branch
        branch_map: dict = {}
        for b in Branch.objects.only('id', 'branch_name', 'branch_code'):
            branch_map[b.branch_name.strip().lower()] = b
            if b.branch_code:
                branch_map[b.branch_code.strip().lower()] = b

        # Pre-load existing emails + phones for DB-level duplicate detection.
        existing_emails: set = set(Candidate.objects.values_list('email', flat=True))
        existing_phones: set = set(
            Candidate.objects
            .exclude(phone='')
            .exclude(phone__isnull=True)
            .values_list('phone', flat=True)
        )

        # Track values seen in this file for intra-file duplicate detection.
        seen_emails: set = set()
        seen_phones: set = set()

        to_create:      list = []
        to_create_meta: list = []
        row_errors:     list = []
        skipped_rows:   list = []

        for i, raw in enumerate(rows, start=2):  # row 1 is the header
            row = _normalize_import_headers(raw)
            ser = CandidateBulkImportRowSerializer(data=row)

            if not ser.is_valid():
                for field, msgs in ser.errors.items():
                    row_errors.append({
                        'row':     i,
                        'field':   field,
                        'message': msgs[0] if isinstance(msgs, list) else str(msgs),
                    })
                continue

            data  = ser.validated_data
            email = data['email']
            phone = (data.get('phone') or '').strip()

            # Duplicates are skipped silently — not treated as failures.
            if email in existing_emails or email in seen_emails:
                skipped_rows.append({
                    'row':        i,
                    'identifier': email,
                    'reason':     'Already exists',
                })
                continue

            if phone and (phone in existing_phones or phone in seen_phones):
                skipped_rows.append({
                    'row':        i,
                    'identifier': email,
                    'reason':     'Phone number already exists',
                })
                continue

            branch     = None
            branch_raw = (data.get('branch_name') or '').strip()
            if branch_raw:
                branch = branch_map.get(branch_raw.lower())
                if branch is None:
                    row_errors.append({
                        'row':        i,
                        'field':      'branch',
                        'identifier': email,
                        'message':    (
                            f'Branch "{branch_raw}" not found. '
                            'Use an existing branch name or branch code.'
                        ),
                    })
                    continue

            to_create.append(Candidate(
                name             = data['name'],
                email            = email,
                phone            = phone,
                position_applied = data['position_applied'],
                branch           = branch,
                interview_date   = data.get('interview_date'),
                interview_mode   = data.get('interview_mode') or '',
                notes            = data.get('notes') or '',
                status           = 'pending',
                added_by         = request.user,
            ))
            to_create_meta.append({'row': i, 'identifier': email})
            seen_emails.add(email)
            if phone:
                seen_phones.add(phone)

        created_count = 0
        created_rows  = []
        if to_create:
            with transaction.atomic():
                Candidate.objects.bulk_create(to_create)
                created_count = len(to_create)
                created_rows  = to_create_meta

        total         = len(rows)
        skipped_count = len(skipped_rows)
        failed        = len(row_errors)

        AuditLog.objects.create(
            user       = request.user,
            action     = 'bulk_candidate_import',
            module     = 'recruitment',
            changes    = {
                'total_rows': total,
                'created':    created_count,
                'skipped':    skipped_count,
                'failed':     failed,
            },
            ip_address = get_client_ip(request),
        )

        logger.info(
            'Bulk import by %s: %d created, %d skipped, %d failed (total %d)',
            request.user.email, created_count, skipped_count, failed, total,
        )

        return success(
            'Bulk import completed.',
            data={
                'total_rows':   total,
                'created':      created_count,
                'skipped':      skipped_count,
                'failed':       failed,
                'created_rows': created_rows,
                'skipped_rows': skipped_rows,
                'errors':       row_errors,
            },
            http_status=status.HTTP_200_OK if failed == 0 else status.HTTP_207_MULTI_STATUS,
        )


# ─── Candidate Bulk Import — Sample Template ──────────────────────────────────

class CandidateBulkImportSampleView(APIView):
   
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    _HEADERS = [
        'Candidate Name', 'Email', 'Mobile Number', 'Position Applied',
        'Branch', 'Interview Date', 'Interview Mode', 'Notes',
    ]
    _SAMPLE_ROWS = [
        [
            'Rahul Sharma', 'rahul.sharma@email.com', '9876543210',
            'Software Engineer', 'Mumbai HQ', '2026-07-25', 'In-Person', '',
        ],
        [
            'Priya Patel', 'priya.patel@email.com', '9123456789',
            'Product Manager', 'Delhi Branch', '2026-07-26', 'Video Call', 'Strong candidate',
        ],
    ]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(
                'You do not have permission to download the candidate import template.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        from core.file_utils import build_sample_csv, build_sample_xlsx, _CSV_MIME, _XLSX_MIME

        fmt = request.query_params.get('format', 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(self._HEADERS, self._SAMPLE_ROWS, 'Candidate Import')
            filename = 'candidate_import_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(self._HEADERS, self._SAMPLE_ROWS)
            filename = 'candidate_import_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
