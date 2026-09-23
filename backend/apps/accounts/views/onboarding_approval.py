
from __future__ import annotations

import csv
import io
import logging
import os
import re
import secrets
import string
from collections import defaultdict
from datetime import date, datetime, timedelta

import requests as http_req

PHONE_RE = re.compile(r'^(?:\+?91)?\d{10}$')
_PHONE_FORMAT_CHARS_RE = re.compile(r'[\s\-()./]')
NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:[ '\-][A-Za-z0-9]+)*$")
EMAIL_RE = re.compile(
    r'^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?'
    r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$'
)


def _is_valid_phone(raw: str) -> bool:
    """True if raw is a 10-digit number, with formatting (spaces/-/()/. /) and
    an optional +91/91 prefix stripped out first."""
    return bool(PHONE_RE.match(_PHONE_FORMAT_CHARS_RE.sub('', raw)))

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Exists, F, Max, OuterRef, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from core.file_validation import validate_file_content as _validate_file_content
from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission, has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success
from core.template_context import (
    candidate_context as _candidate_template_context,
    expense_context as _expense_template_context,
    leave_request_context as _leave_request_template_context,
    universal_context as _universal_template_context,
)
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication   


from apps.accounts.models import (
    ApprovalWorkflowRule,
    AuditLog,
    Company,
    CompanyDirector,
    CompanyGSTRegistration,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeApprovalOverride,
    EmployeeCodeSettings,
    HireAction,
    JobTemplate,
    OnboardingFieldConfig,
    OnboardingSection,
    OrgUnit,
    OTPVerification,
    PasswordResetToken,
    Permission,
    Placement,
    Position,
    PromotionRecord,
    Role,
    RolePermission,
    SMTPSettings,
    User,
)
from apps.accounts.serializers import (
    ApprovalWorkflowRuleUpdateSerializer,
    AuditLogSerializer,
    ChangePasswordSerializer,
    CompanyDirectorSerializer,
    CompanyGSTRegistrationSerializer,
    CompanySerializer,
    DocumentSerializer,
    EmailTemplateAttachmentSerializer,
    EmailTemplateCategorySerializer,
    EmailTemplatePreviewSerializer,
    EmailTemplateSerializer,
    EmployeeBulkImportRowSerializer,
    EmployeeCodeSettingsSerializer,
    ForgotPasswordSerializer,
    JobTemplateSerializer,
    LoginSerializer,
    OrgUnitSerializer,
    PermissionSerializer,
    PlacementSerializer,
    PositionSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    SMTPSettingsSerializer,
    SMTPTestSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.services_placement import assign_position, sync_from_position
from apps.accounts.throttles import ForgotPasswordRateThrottle, LoginRateThrottle, OTPVerifyRateThrottle, ResetPasswordRateThrottle
from apps.accounts.tokens import FreshClaimsTokenRefreshSerializer, RoleBasedRefreshToken
from apps.accounts.utils import send_otp_email, send_template_email, send_test_email

logger = logging.getLogger(__name__)

from apps.accounts.views.shared import *  # noqa: F401,F403

# ─── Onboarding — HR management (pipeline + approvals queue + approve/reject) ──


class OnboardingApprovalView(APIView):
    """
    Unified HR onboarding management endpoint.

    /onboarding/approvals/           GET → approvals queue (submitted, awaiting action)
                                         ?view=pipeline → full pipeline (pending+draft+submitted)
    /onboarding/approvals/<user_id>/ GET  → specific employee's full onboarding details
                                     POST → approve or reject
                                           body: {decision: 'approve'|'reject', remarks: ''}
    """
    permission_classes = [IsAuthenticated]

    # ── GET ───────────────────────────────────────────────────────────────────

    def get(self, request, user_id=None):
        if not _has_perm(request.user, 'onboarding.approve'):
            return error('You do not have permission to view onboarding approvals.',
                         http_status=status.HTTP_403_FORBIDDEN)

        if user_id is not None:
            return self._get_user_detail(request, user_id)

        view = request.query_params.get('view', 'approvals').strip().lower()
        return self._get_pipeline(request) if view == 'pipeline' else self._get_approvals_list(request)

    # ── POST — approve or reject a specific employee ──────────────────────────

    @transaction.atomic
    def post(self, request, user_id=None):
        if user_id is None:
            return error(
                'User ID is required. Use POST /onboarding/approvals/<user_id>/ to approve or reject.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if not _has_perm(request.user, 'onboarding.approve'):
            return error('You do not have permission to approve onboarding.',
                         http_status=status.HTTP_403_FORBIDDEN)

        try:
            target = User.objects.select_related('role').get(pk=user_id)
        except User.DoesNotExist:
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if _employee_out_of_branch_scope(request.user, target):
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if target.onboarding_status != User.ONBOARDING_SUBMITTED:
            return error('This user has not submitted their onboarding form.')

        if not _has_perm(request.user, 'settings.edit') and _has_perm(target, 'employees.view'):
            return error('HR admin can only approve employee onboarding.',
                         http_status=status.HTTP_403_FORBIDDEN)

        decision           = request.data.get('decision')
        remarks            = request.data.get('remarks', '')
        # Department/designation are always derived from the Position on
        # approval — see req_position_obj below.
        req_position_id    = (request.data.get('position')           or '').strip()
        # assessment_ids (list) is the current contract; assessment_id (single)
        # is accepted too for any older caller still sending one value.
        req_assessment_ids = request.data.get('assessment_ids')
        if not isinstance(req_assessment_ids, list):
            single = request.data.get('assessment_id')
            req_assessment_ids = [single] if single else []
        req_assessment_ids     = [str(a) for a in req_assessment_ids if a]
        req_manager_id         = request.data.get('reporting_manager_id')
        annual_ctc_raw         = (request.data.get('annual_ctc')          or '').strip()
        req_uan_number         = (request.data.get('uan_number')          or '').strip()
        req_name_as_per_aadhar = (request.data.get('name_as_per_aadhar')  or '').strip()
        req_pan_number         = (request.data.get('pan_number')          or '').strip()
        if decision not in ('approve', 'reject'):
            return error('decision must be "approve" or "reject".')
        req_position_obj = None
        if decision == 'approve':
            if not req_position_id:
                return error('A position is required to approve onboarding.', data={'position': 'Position is required.'})
            try:
                req_position_obj = Position.objects.select_related(
                    'org_unit', 'job_template',
                ).get(pk=req_position_id, is_active=True)
            except (Position.DoesNotExist, ValueError, ValidationError):
                return error('Select a valid, active position.', data={'position': 'Position not found.'})

            if req_pan_number:
                # Validated before any state changes below — an invalid/duplicate
                # PAN must reject the whole approval, not just skip saving it.
                from apps.accounts.models import find_conflicting_pan_profile, normalize_and_validate_pan
                try:
                    req_pan_number = normalize_and_validate_pan(req_pan_number)
                except ValueError as exc:
                    return error(str(exc))
                existing_profile = getattr(target, 'profile', None)
                conflict = find_conflicting_pan_profile(
                    req_pan_number,
                    exclude_profile_pk=existing_profile.pk if existing_profile else None,
                )
                if conflict:
                    return error(
                        f'This PAN is already registered to {conflict.user.full_name} '
                        f'({conflict.user.employee_id or conflict.user.email}).'
                    )

        company      = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''

        if decision == 'approve':
            from apps.recruitment.models import Candidate
            try:
                linked_candidate = Candidate.objects.select_related('branch').get(portal_user=target)
            except Candidate.DoesNotExist:
                linked_candidate = None

            needs_conversion = not target.role and not target.employee_id
            if needs_conversion:
                try:
                    employee_role = Role.objects.get(name='employee')
                except Role.DoesNotExist:
                    return error('Role "employee" not found. Create it in Roles settings first.')
                target.role = employee_role
                if not target.date_of_joining:
                    from django.utils import timezone as tz
                    target.date_of_joining = tz.now().date()
                _name_parts = (target.full_name or '').split(' ', 1)
                target.employee_id = EmployeeCodeSettings.generate_employee_id(
                    first_name=_name_parts[0] if _name_parts else '',
                    last_name=_name_parts[1] if len(_name_parts) > 1 else '',
                    date_of_joining=target.date_of_joining,
                )

                if linked_candidate and not target.branch and linked_candidate.branch:
                    target.branch = linked_candidate.branch.branch_name

            # designation/department are derived from the Position — sync
            # them (and create the Placement) before _auto_assign_managers
            # below, so its org-unit-chief lookup for reporting_manager can
            # actually resolve one, and before the final save so nothing
            # overwrites the synced values with stale in-memory strings.
            if req_position_obj is not None:
                assign_position(
                    target, req_position_obj,
                    effective_from=target.date_of_joining or timezone.localdate(),
                    created_by=request.user,
                )
                target.refresh_from_db(fields=[
                    'designation', 'department',
                    'designation_synced_from_position', 'department_synced_from_position',
                ])

            # Explicit reporting manager override — set before _auto_assign_managers so auto-assign skips it
            if req_manager_id:
                try:
                    manager_user = User.objects.get(pk=req_manager_id, is_active=True)
                    target.reporting_manager = manager_user
                    target.reporting_manager_from_org_chart = False
                except User.DoesNotExist:
                    return error('Reporting manager not found or is inactive.')

            target.onboarding_status    = User.ONBOARDING_COMPLETE
            target.must_change_password = False
            auto_fields = _auto_assign_managers(target)
            target.save(update_fields=list(dict.fromkeys([
                'onboarding_status', 'must_change_password',
                'role', 'employee_id', 'date_of_joining',
                'designation', 'department', 'branch',
                'reporting_manager', 'reporting_manager_from_org_chart', 'hr',
                *auto_fields,
            ])))

            # Save UAN / Aadhar name / PAN provided by HR at approval time.
            if req_uan_number or req_name_as_per_aadhar or req_pan_number:
                from apps.accounts.models import EmployeeProfile as _Profile
                profile, _ = _Profile.objects.get_or_create(user=target)
                profile_fields = []
                if req_uan_number:
                    profile.uan_number = req_uan_number
                    profile_fields.append('uan_number')
                if req_name_as_per_aadhar:
                    profile.name_as_per_aadhar = req_name_as_per_aadhar
                    profile_fields.append('name_as_per_aadhar')
                if req_pan_number:
                    profile.pan_number = req_pan_number
                    profile_fields.append('pan_number')
                if profile_fields:
                    profile_fields.append('updated_at')
                    profile.save(update_fields=profile_fields)

            if needs_conversion:
                # Auto-allocate leave balances after candidate→employee conversion
                from apps.hrms.views.leave import _allocate_leaves_for_employee
                _allocate_leaves_for_employee(target, target.date_of_joining)

            # Create initial salary config if CTC was provided at approval time
            if annual_ctc_raw:
                from decimal import Decimal as _Decimal
                from django.utils import timezone as _tz
                from apps.payroll.models import EmployeeSalaryConfig as _SalaryConfig
                try:
                    _annual_ctc = _Decimal(annual_ctc_raw)
                    _SalaryConfig.objects.filter(employee=target, is_active=True).update(is_active=False)
                    _SalaryConfig.objects.create(
                        employee=target,
                        annual_ctc=_annual_ctc,
                        effective_from=target.date_of_joining or _tz.now().date(),
                        is_active=True,
                    )
                    logger.info('EmployeeSalaryConfig created for %s via onboarding approval', target.email)
                except Exception:
                    logger.exception('Failed to create salary config for %s during onboarding approval', target.email)

            if linked_candidate:
                linked_candidate.status      = Candidate.STATUS_CONVERTED
                linked_candidate.hr_approved = True
                linked_candidate.save(update_fields=['status', 'hr_approved', 'updated_at'])

                # Auto-create the referral bonus record on conversion so referrers
                # are never missed. (A duplicate auto-creation existed in
                # CandidateStatusView.patch() in the recruitment app, but that
                # view's own status whitelist excludes STATUS_CONVERTED, so it
                # was dead code — this is the only place a candidate is ever
                # actually marked converted.)
                if linked_candidate.referral_by_id:
                    from apps.recruitment.models import ReferralBonus
                    _, _bonus_created = ReferralBonus.objects.get_or_create(
                        candidate=linked_candidate,
                        defaults={'referrer': linked_candidate.referral_by, 'bonus_amount': 0},
                    )
                    if _bonus_created:
                        logger.info(
                            'Referral bonus record created for referrer %s (candidate %s)',
                            linked_candidate.referral_by_id, linked_candidate.pk,
                        )

            # Auto-assign default assessments — employee must complete these to unlock full portal.
            # Works for both recruited candidates (candidate FK) and direct hires (employee FK).
            from apps.assessments.models import Assessment, AssessmentItem, CandidateAssignment
            from django.db.models import Q as _Q
            assigned_assessments = []
            assessments_to_assign = list(
                Assessment.objects.filter(is_active=True, is_default=True).prefetch_related('items')
            )
            # HR may pick one or more specific (possibly non-default) assessments
            # in the approval confirmation dialog — honor that choice, not just
            # the global defaults. A branch/role can have several relevant
            # tests, so this is a list, not a single value.
            if req_assessment_ids:
                already_ids = {str(a.id) for a in assessments_to_assign}
                new_ids = [aid for aid in req_assessment_ids if aid not in already_ids]
                if new_ids:
                    selected_assessments = Assessment.objects.filter(
                        pk__in=new_ids, is_active=True,
                    ).prefetch_related('items')
                    assessments_to_assign.extend(selected_assessments)
            for assessment in assessments_to_assign:
                max_score = assessment.items.filter(item_type=AssessmentItem.TYPE_QUIZ).count()
                if linked_candidate:
                    _, created = CandidateAssignment.objects.get_or_create(
                        candidate=linked_candidate,
                        assessment=assessment,
                        defaults={'assigned_by': request.user, 'max_score': max_score},
                    )
                else:
                    _, created = CandidateAssignment.objects.get_or_create(
                        employee=target,
                        assessment=assessment,
                        defaults={'assigned_by': request.user, 'max_score': max_score},
                    )
                if created:
                    assigned_assessments.append(assessment)

            # Set status PENDING if any assignment (new or pre-existing from recruitment step) is pending
            pending_filter = (
                _Q(candidate=linked_candidate) if linked_candidate else _Q(employee=target)
            )
            has_pending = CandidateAssignment.objects.filter(
                pending_filter,
                status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS],
            ).exists()
            if has_pending and target.assessment_status != User.ASSESSMENT_PENDING:
                target.assessment_status = User.ASSESSMENT_PENDING
                target.save(update_fields=['assessment_status', 'updated_at'])

            AuditLog.objects.create(
                user=request.user, action='onboarding_approved', module='accounts',
                object_id=str(target.pk),
                changes={'target': target.email, 'remarks': remarks},
                branch=target.branch,
                ip_address=get_client_ip(request),
            )
            logger.info('Onboarding approved for %s by %s', target.email, request.user.email)

            # Dispatch via Celery so 1-3 sequential SMTP round-trips never sit in
            # this request's response path — see send_onboarding_submitted_notification_task's
            # dispatch (onboarding wizard submission, above) for the same rationale.
            from apps.accounts.tasks import send_onboarding_approved_notification_task

            def _queue_approval_notification(
                user_id=target.pk,
                assessment_ids=[a.id for a in assigned_assessments],
                has_pending_=has_pending,
            ):
                try:
                    send_onboarding_approved_notification_task.apply_async(
                        args=[user_id, assessment_ids, has_pending_], retry=False, ignore_result=True,
                    )
                except Exception as exc:
                    logger.error(
                        'Failed to queue onboarding_approved notification for user %s: %s',
                        user_id, exc, exc_info=True,
                    )

            transaction.on_commit(_queue_approval_notification)

            return success(f'{target.full_name} onboarding approved.')

        else:
            target.onboarding_status = User.ONBOARDING_REJECTED
            target.save(update_fields=['onboarding_status'])
            AuditLog.objects.create(
                user=request.user, action='onboarding_rejected', module='accounts',
                object_id=str(target.pk),
                changes={'target': target.email, 'remarks': remarks},
                branch=target.branch,
                ip_address=get_client_ip(request),
            )
            logger.info('Onboarding rejected for %s by %s', target.email, request.user.email)

            try:
                send_template_email(
                    recipient_email=target.email,
                    template_name='onboarding_rejected',
                    context={
                        'employee_name': target.full_name,
                        'company_name':  company_name,
                        'remarks':       remarks or 'Please contact HR for details.',
                        'portal_url':    portal_url,
                    },
                    module='accounts',
                    triggered_by=request.user,
                )
            except Exception:
                logger.exception('Failed to send onboarding rejection email to %s', target.email)

            return success(f'Onboarding sent back to {target.full_name} for corrections.')

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_pipeline(self, request):
        from apps.accounts.serializers import OnboardingPipelineSerializer
        from apps.recruitment.models import Candidate

        base_qs = (
            User.objects
            .filter(
                onboarding_status__in=[
                    User.ONBOARDING_PENDING,
                    User.ONBOARDING_DRAFT,
                    User.ONBOARDING_SUBMITTED,
                ],
                candidate_portal__isnull=False,
            )
            .select_related('role')
            .distinct()
            .order_by('-date_joined')
        )
        if not _has_perm(request.user, 'settings.edit'):
            base_qs = base_qs.exclude(role__role_permissions__permission__codename='settings.edit')

        stats = {
            'pending':   base_qs.filter(onboarding_status=User.ONBOARDING_PENDING).count(),
            'draft':     base_qs.filter(onboarding_status=User.ONBOARDING_DRAFT).count(),
            'submitted': base_qs.filter(onboarding_status=User.ONBOARDING_SUBMITTED).count(),
        }

        status_param = request.query_params.get('status', '').strip()
        if status_param:
            allowed = {User.ONBOARDING_PENDING, User.ONBOARDING_DRAFT, User.ONBOARDING_SUBMITTED}
            if status_param not in allowed:
                return error(f'status must be one of: {", ".join(sorted(allowed))}.')
            base_qs = base_qs.filter(onboarding_status=status_param)

        page_obj, paginator = paginate(base_qs, request, default_page_size=20)
        user_ids = [u.pk for u in page_obj.object_list]
        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.filter(portal_user_id__in=user_ids)
        }
        data = paginated_data(
            paginator, page_obj,
            OnboardingPipelineSerializer(
                page_obj.object_list, many=True,
                context={'candidates_by_user': candidates_by_user},
            ).data,
        )
        data['stats'] = stats
        return success('Onboarding pipeline retrieved.', data=data)

    def _get_approvals_list(self, request):
        from apps.accounts.serializers import OnboardingApprovalSerializer
        from apps.recruitment.models import Candidate

        qs = (
            User.objects
            .filter(onboarding_status__in=[User.ONBOARDING_SUBMITTED, User.ONBOARDING_REJECTED])
            .select_related('role', 'profile')
            .prefetch_related('employee_documents')
            .prefetch_related('custom_field_files')
            .order_by('date_joined')
        )
        role = request.user.role
        if not _has_perm(request.user, 'settings.edit'):
            qs = qs.exclude(role__role_permissions__permission__codename='settings.edit')
            # Same scoping as EmployeeListCreateView.get(): managers only see
            # their direct reports; everyone else is scoped to their own branch.
            if role and role.can_manage_team:
                qs = qs.filter(reporting_manager=request.user)
            elif request.user.branch:
                # A submitted candidate who hasn't been approved yet has no
                # User.branch (that's only copied over from the linked
                # Candidate at approval time) — fall back to the source
                # candidate's branch so HR still sees their own branch's
                # pending submissions.
                qs = qs.filter(
                    Q(branch=request.user.branch) |
                    Q(branch='', candidate_portal__branch__branch_name=request.user.branch)
                ).distinct()

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        user_ids = [u.pk for u in page_obj.object_list]
        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.select_related('branch').filter(portal_user_id__in=user_ids)
        }
        return success('Onboarding approvals retrieved.', data=paginated_data(
            paginator, page_obj,
            OnboardingApprovalSerializer(
                page_obj.object_list, many=True,
                context={
                    'request': request,
                    'candidates_by_user': candidates_by_user,
                    'use_direct_url': True,
                },
            ).data,
        ))

    def _get_user_detail(self, request, user_id):
        from apps.accounts.serializers import OnboardingApprovalSerializer
        from apps.recruitment.models import Candidate

        try:
            target = (
                User.objects
                .select_related('role', 'profile')
                .prefetch_related('employee_documents')
                .prefetch_related('custom_field_files')
                .get(pk=user_id)
            )
        except User.DoesNotExist:
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        if _employee_out_of_branch_scope(request.user, target):
            return error('User not found.', http_status=status.HTTP_404_NOT_FOUND)

        candidates_by_user = {
            c.portal_user_id: c
            for c in Candidate.objects.select_related('branch').filter(portal_user=target)
        }
        return success(
            'Onboarding details retrieved.',
            data=OnboardingApprovalSerializer(
                target,
                context={
                    'request': request,
                    'candidates_by_user': candidates_by_user,
                    'use_direct_url': True,
                },
            ).data,
        )


