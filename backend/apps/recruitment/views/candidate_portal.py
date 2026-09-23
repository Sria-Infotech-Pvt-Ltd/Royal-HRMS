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



# ─── Portal helpers ────────────────────────────────────────────────────────────





# ─── Send Portal Login (candidate onboarding invite) ──────────────────────────

class SendPortalLoginView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        try:
            candidate = Candidate.objects.select_related('branch').select_for_update().get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

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
                module='recruitment',
                triggered_by=request.user,
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
            branch=candidate.branch.branch_name if candidate.branch else '',
            ip_address=get_client_ip(request),
        )
        return success('Portal login sent successfully.', data={'email': candidate.email})

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.select_related('branch').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
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
            candidate = Candidate.objects.select_related('branch').select_for_update().get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

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
                module='recruitment',
                triggered_by=request.user,
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
            branch=candidate.branch.branch_name if candidate.branch else '',
            ip_address=get_client_ip(request),
        )
        return success('Portal credentials resent successfully.', data={'email': candidate.email})

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.select_related('branch').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success('Portal login status retrieved.', data=_portal_login_status(candidate))

    def put(self, request, pk):
        return self.post(request, pk)

    def patch(self, request, pk):
        return self.post(request, pk)

    def delete(self, request, pk):
        return _revoke_portal_access(request, pk)
