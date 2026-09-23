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
            branch=candidate.branch.branch_name if candidate.branch else '',
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
            candidate = Candidate.objects.select_related('branch').prefetch_related('logs').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

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
            branch=candidate.branch.branch_name if candidate.branch else '',
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

        # candidate.status never changes on this endpoint (stays
        # STATUS_SELECTED — only hr_approved flips), so without this guard a
        # retry after a partial failure below (e.g. the assessment-assignment
        # step raising) re-matches the same query and repeats every
        # candidate-facing side effect: a second "you're approved" email, a
        # duplicate CandidateLog entry, etc. Reject doesn't need the same
        # guard — CandidateHRDecisionView has no "undo an approval" concept,
        # so re-rejecting an already-approved candidate is a no-op either way
        # (just another log entry), not a repeat of a real action.
        if decision == 'approve' and candidate.hr_approved:
            return error('This candidate has already been approved.', http_status=status.HTTP_409_CONFLICT)

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

            # Everything below is one all-or-nothing unit — previously
            # `candidate.hr_approved=True` and the "HR Approved" log entry
            # committed independently of the assessment-assignment step
            # further down, which had no try/except at all: a DB hiccup or a
            # bad Assessment/AssessmentItem row there would 500 the request
            # *after* the approval had already been saved, with nothing to
            # roll it back. `_send_candidate_email`/the assessment
            # notification loop already swallow their own exceptions (can't
            # raise), so including them here changes nothing about how long
            # this transaction is realistically held open in practice.
            with transaction.atomic():
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
                                    module='recruitment',
                                    triggered_by=request.user,
                                )
                            except Exception:
                                logger.exception(
                                    'Failed to send assessment_assigned email for "%s" to %s',
                                    assessment.title, candidate.email,
                                )

            msg = f'{candidate.name} approved and onboarded!'
        else:
            revision_remarks = remarks or 'Please recheck documents'
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_WARN,
                title='HR requested revision',
                description=f'Remarks: {revision_remarks}',
            )
            email_status = _send_candidate_email(
                candidate, 'candidate_revision_requested', request.user,
                {'remarks': revision_remarks},
            )
            CandidateLog.objects.create(
                candidate=candidate,
                log_type=(CandidateLog.TYPE_SUCCESS
                          if email_status == CandidateEmail.STATUS_SENT
                          else CandidateLog.TYPE_WARN),
                title=('Revision request email sent'
                       if email_status == CandidateEmail.STATUS_SENT
                       else 'Revision request email failed — check SMTP settings'),
                description='Using template: candidate_revision_requested',
            )
            msg = 'Revision requested.'

        AuditLog.objects.create(
            user=request.user, action=f'candidate_hr_{decision}d', module='recruitment',
            object_id=str(candidate.pk),
            changes={'name': candidate.name, 'decision': decision},
            branch=candidate.branch.branch_name if candidate.branch else '',
            ip_address=get_client_ip(request),
        )

        return success(msg, data=CandidateDetailSerializer(candidate).data)

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            candidate = Candidate.objects.select_related('branch').get(pk=pk)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
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
            branch=candidate.branch.branch_name if candidate.branch else '',
            ip_address=get_client_ip(request),
        )
        logger.info('HR approval reset for candidate %s by %s', pk, request.user.email)
        return success('HR approval reset.', data=CandidateDetailSerializer(candidate).data)
