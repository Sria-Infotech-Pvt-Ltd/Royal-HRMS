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

from apps.recruitment.views.shared import *  # noqa: F401,F403



# ─── Candidate Review list (selected only, with logs) ─────────────────────────

class CandidateReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = (Candidate.objects
              .filter(status=Candidate.STATUS_SELECTED)
              .select_related('interviewer', 'added_by', 'branch')
              .prefetch_related('logs')
              .order_by('-updated_at'))

        # Same branch scoping as CandidateListCreateView.get — without it, a
        # branch-scoped recruitment.view holder saw every selected candidate
        # company-wide instead of just their own branch.
        is_admin = _has_perm(request.user, 'settings.edit')
        user_branch = (getattr(request.user, 'branch', '') or '').strip()
        if not is_admin and user_branch:
            qs = qs.filter(branch__branch_name__iexact=user_branch)

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
              .select_related('candidate', 'candidate__branch', 'sent_by')
              .order_by('-sent_at'))

        # Same branch scoping as CandidateListCreateView.get — without it, a
        # branch-scoped recruitment.view holder saw every candidate's email
        # correspondence log company-wide instead of just their own branch.
        is_admin = _has_perm(request.user, 'settings.edit')
        user_branch = (getattr(request.user, 'branch', '') or '').strip()
        if not is_admin and user_branch:
            qs = qs.filter(candidate__branch__branch_name__iexact=user_branch)

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
                    format_date_display(candidate.interview_date)
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
                module='recruitment',
                triggered_by=request.user,
            )
            sent_status = CandidateEmail.STATUS_SENT
            logger.info(
                'Manual email "%s" sent to %s by %s',
                template_name, recipient_email, request.user.email,
            )
        except LookupError as exc:
            return error(str(exc), http_status=status.HTTP_404_NOT_FOUND)
        except smtplib.SMTPResponseException as exc:
            logger.exception(
                'Manual email "%s" failed for pk=%s', template_name, pk,
            )
            # 550/452-style responses from the provider mean the sending
            # account hit its own rate/quota limit — a transient capacity
            # issue, not a config problem. Surfacing it distinctly stops HR
            # from chasing SMTP settings that are actually fine.
            if exc.smtp_code in (450, 451, 452, 550) and b'limit' in exc.smtp_error.lower():
                return error(
                    'The sending mailbox has hit its daily email limit. '
                    'Try again later or contact your administrator.'
                )
            return error('Failed to send email. Check SMTP configuration.')
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
            branch=(candidate.branch.branch_name if candidate and candidate.branch else ''),
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
