
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

# ─── Company ──────────────────────────────────────────────────────────────────

class CompanyRetrieveUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        from core.cache_service import CompanyCacheService
        company = CompanyCacheService.get()
        if not company:
            return success('No company info found.', data={})
        serializer = CompanySerializer(company, context={'request': request})
        return success('Company info retrieved.', data=serializer.data)

    def put(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error(
                'You do not have permission to update company info.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        company = Company.objects.first()
        is_new  = company is None

        with transaction.atomic():
            serializer = CompanySerializer(
                company,
                data=request.data,
                partial=not is_new,
                context={'request': request},
            )
            if not serializer.is_valid():
                return error(first_error(serializer.errors), data=serializer.errors)

            # Replace old logo file when a new one is uploaded
            if not is_new and 'logo' in request.FILES and company.logo:
                company.logo.delete(save=False)

            instance = serializer.save(updated_by=request.user)

            # Handle explicit logo removal
            remove_logo = str(request.data.get('remove_logo', '')).lower() == 'true'
            if remove_logo and instance.logo:
                instance.logo.delete(save=False)
                instance.logo = None
                instance.save(update_fields=['logo'])

        # CompanyCacheService.get() caches the model instance itself — without
        # this, a save here would leave every reader (including the very next
        # GET on this endpoint) looking at the pre-edit instance until the
        # cache TTL expires.
        from core.cache_service import CompanyCacheService, FinancialYearCacheService
        CompanyCacheService.invalidate()
        # financial_year_start_month now saves through this endpoint too
        # (merged into the main form) — Payroll/Reports read the FY config
        # from FinancialYearCacheService, which CompanyFinancialYearView.put()
        # already kept in sync for its own save path; this endpoint needs the
        # same invalidation so a change here isn't served stale elsewhere.
        FinancialYearCacheService.invalidate()

        AuditLog.objects.create(
            user=request.user,
            action='create' if is_new else 'update',
            module='company',
            object_id=str(instance.pk),
            ip_address=get_client_ip(request),
        )
        logger.info('Company info %s by %s', 'created' if is_new else 'updated', request.user.email)
        return success(
            'Company info saved successfully.',
            data=CompanySerializer(instance, context={'request': request}).data,
        )

    def patch(self, request):
        return self.put(request)


# ─── Company Financial Year ───────────────────────────────────────────────────

class CompanyFinancialYearView(APIView):
    """
    GET  /api/settings/company/financial-year/
        Any authenticated user. Returns the configured start month plus
        dynamically computed previous, current, and next FY labels.

    PUT  /api/settings/company/financial-year/
        system_admin only. Accepts { "financial_year_start_month": "April" }.
        Persists the change, busts the FY cache, and writes an audit log.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.utils import get_company_financial_year_config
        data = get_company_financial_year_config()
        return success('Financial year configuration retrieved.', data)

    def put(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error(
                'Only system administrators can update the financial year configuration.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        new_month = str(request.data.get('financial_year_start_month', '')).strip()
        valid_months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December',
        ]
        if new_month not in valid_months:
            return error(
                f'Invalid month "{new_month}". Must be one of: {", ".join(valid_months)}.'
            )

        company = Company.objects.first()
        if not company:
            return error('Company record not found. Set up company info first.', http_status=404)

        old_month = company.financial_year_start_month

        if old_month != new_month:
            with transaction.atomic():
                company.financial_year_start_month = new_month
                company.updated_by = request.user
                company.save(update_fields=['financial_year_start_month', 'updated_by', 'updated_at'])

            AuditLog.objects.create(
                user=request.user,
                action='update',
                module='company_financial_year',
                object_id=str(company.pk),
                ip_address=get_client_ip(request),
                changes={
                    'financial_year_start_month': {'old': old_month, 'new': new_month},
                },
            )
            logger.info(
                'Financial year start month changed from %s to %s by %s',
                old_month, new_month, request.user.email,
            )

        from apps.accounts.utils import get_financial_years
        from core.cache_service import FinancialYearCacheService
        from datetime import date as _date
        today = _date.today()
        data = {
            'financial_year_start_month': new_month,
            **get_financial_years(today, new_month),
        }
        FinancialYearCacheService.set(data)

        return success('Financial year configuration updated.', data)


# ─── Company GST Registrations ────────────────────────────────────────────────

class CompanyGSTRegistrationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to view company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        qs = CompanyGSTRegistration.objects.select_related('company').all()
        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success(
            'GST registrations retrieved.',
            data=paginated_data(
                paginator, page_obj,
                CompanyGSTRegistrationSerializer(page_obj.object_list, many=True).data,
            ),
        )

    def post(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        company = Company.objects.first()
        if not company:
            return error('Company record not found. Set up company info first.', http_status=404)

        serializer = CompanyGSTRegistrationSerializer(data=request.data, context={'company': company})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            instance = serializer.save(company=company)
        except IntegrityError:
            return error('A GST registration with this GSTIN already exists.', http_status=status.HTTP_409_CONFLICT)

        AuditLog.objects.create(
            user=request.user, action='create', module='company_gst_registration',
            object_id=str(instance.pk), ip_address=get_client_ip(request),
        )
        return success('GST registration added.', data=CompanyGSTRegistrationSerializer(instance).data)


class CompanyGSTRegistrationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk) -> CompanyGSTRegistration | None:
        try:
            return CompanyGSTRegistration.objects.select_related('company').get(pk=pk)
        except CompanyGSTRegistration.DoesNotExist:
            return None

    def put(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        reg = self._get(pk)
        if not reg:
            return error('GST registration not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = CompanyGSTRegistrationSerializer(
            reg, data=request.data, partial=True, context={'company': reg.company},
        )
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            instance = serializer.save()
        except IntegrityError:
            return error('A GST registration with this GSTIN already exists.', http_status=status.HTTP_409_CONFLICT)

        AuditLog.objects.create(
            user=request.user, action='update', module='company_gst_registration',
            object_id=str(instance.pk), ip_address=get_client_ip(request),
        )
        return success('GST registration updated.', data=CompanyGSTRegistrationSerializer(instance).data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        reg = self._get(pk)
        if not reg:
            return error('GST registration not found.', http_status=status.HTTP_404_NOT_FOUND)
        reg_id = str(reg.pk)
        reg.delete()
        AuditLog.objects.create(
            user=request.user, action='delete', module='company_gst_registration',
            object_id=reg_id, ip_address=get_client_ip(request),
        )
        return success('GST registration removed.', data={})


# ─── Company Directors ─────────────────────────────────────────────────────────

class CompanyDirectorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to view company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        qs = CompanyDirector.objects.select_related('company').all()
        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success(
            'Directors retrieved.',
            data=paginated_data(
                paginator, page_obj,
                CompanyDirectorSerializer(page_obj.object_list, many=True).data,
            ),
        )

    def post(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        company = Company.objects.first()
        if not company:
            return error('Company record not found. Set up company info first.', http_status=404)

        serializer = CompanyDirectorSerializer(data=request.data, context={'company': company})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            instance = serializer.save(company=company)
        except IntegrityError:
            return error('A director with this DIN already exists.', http_status=status.HTTP_409_CONFLICT)

        AuditLog.objects.create(
            user=request.user, action='create', module='company_director',
            object_id=str(instance.pk), ip_address=get_client_ip(request),
        )
        return success('Director added.', data=CompanyDirectorSerializer(instance).data)


class CompanyDirectorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk) -> CompanyDirector | None:
        try:
            return CompanyDirector.objects.select_related('company').get(pk=pk)
        except CompanyDirector.DoesNotExist:
            return None

    def put(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        director = self._get(pk)
        if not director:
            return error('Director not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = CompanyDirectorSerializer(director, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            instance = serializer.save()
        except IntegrityError:
            return error('A director with this DIN already exists.', http_status=status.HTTP_409_CONFLICT)

        AuditLog.objects.create(
            user=request.user, action='update', module='company_director',
            object_id=str(instance.pk), ip_address=get_client_ip(request),
        )
        return success('Director updated.', data=CompanyDirectorSerializer(instance).data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to update company info.',
                         http_status=status.HTTP_403_FORBIDDEN)
        director = self._get(pk)
        if not director:
            return error('Director not found.', http_status=status.HTTP_404_NOT_FOUND)
        director_id = str(director.pk)
        director.delete()
        AuditLog.objects.create(
            user=request.user, action='delete', module='company_director',
            object_id=director_id, ip_address=get_client_ip(request),
        )
        return success('Director removed.', data={})


