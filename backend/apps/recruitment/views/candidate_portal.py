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

from apps.recruitment.services_candidate_onboarding import send_onboarding_link
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
            candidate = Candidate.objects.select_related('branch').select_for_update(of=('self',)).get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        if candidate.status != Candidate.STATUS_SELECTED:
            return error('Only a candidate who has been marked Selected can be sent the onboarding link.')
        if candidate.portal_credentials_sent and candidate.portal_user_id:
            return error('The onboarding link was already sent. Use Resend to send a new one.')
        if not candidate.email or not candidate.email.strip():
            return error('Candidate does not have a valid email address.')
        if User.objects.filter(email__iexact=candidate.email).exists():
            return error('An account already exists for this email address.', http_status=status.HTTP_409_CONFLICT)

        # A record to hold the onboarding form: no usable password, no employee ID, not activated, not an active employee.
        portal_user = User.objects.create_user(
            email=candidate.email, password=None, full_name=candidate.name, must_change_password=False,
            onboarding_status=User.ONBOARDING_PENDING, requires_self_service_onboarding=True,
        )
        portal_user.assessment_status = User.ASSESSMENT_COMPLETE
        portal_user.save(update_fields=['assessment_status', 'updated_at'])
        candidate.portal_user = portal_user
        candidate.portal_credentials_sent = True
        candidate.status = Candidate.STATUS_OFFER_SENT
        candidate.save(update_fields=['portal_user', 'portal_credentials_sent', 'status', 'updated_at'])

        delivered = send_onboarding_link(candidate, portal_user, request.user, ip_address=get_client_ip(request))
        message = ('Onboarding link sent.' if delivered
                   else 'Onboarding link created, but the email could not be sent. Check SMTP settings, then use Resend.')
        return success(message, data={'email': candidate.email, 'delivered': delivered})

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
            candidate = Candidate.objects.select_related('branch').select_for_update(of=('self',)).get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        if not candidate.portal_credentials_sent or not candidate.portal_user_id:
            return error('The onboarding link has not been sent yet. Use Send onboarding link first.')
        portal_user = candidate.portal_user
        if portal_user.onboarding_status == User.ONBOARDING_COMPLETE:
            return error("This candidate's onboarding is already approved. Resend the activation link from their onboarding history instead.")

        delivered = send_onboarding_link(candidate, portal_user, request.user, ip_address=get_client_ip(request), resend=True)
        message = ('A new onboarding link was sent. The previous link no longer works.' if delivered
                   else 'A new link was created, but the email could not be sent. Check SMTP settings and try again.')
        return success(message, data={'email': candidate.email, 'delivered': delivered})

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
