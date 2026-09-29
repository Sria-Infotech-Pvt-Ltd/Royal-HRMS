
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
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


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

# ─── Role management ──────────────────────────────────────────────────────────

class RoleListCreateView(APIView):
    # GET is open to any authenticated user (needed for role-selector dropdowns
    # on the employee profile page). POST/mutating actions still require CanManageRoles.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Role.objects
            .prefetch_related('role_permissions__permission')
            .annotate(active_user_count=Count('users', filter=Q(users__is_active=True)))
            .order_by('id')
        )
        if (is_active_param := request.query_params.get('is_active', '').strip().lower()) in ('true', 'false'):
            qs = qs.filter(is_active=(is_active_param == 'true'))

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success('Roles retrieved successfully.', data=paginated_data(
            paginator, page_obj,
            RoleSerializer(page_obj.object_list, many=True).data,
        ))

    def post(self, request):
        if not CanManageRoles().has_permission(request, self):
            return error('You do not have permission to create roles.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = RoleSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_created', module='accounts',
            object_id=str(role.id),
            changes={'name': role.name, 'display_name': role.display_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" created by %s', role.name, request.user.email)
        return success(
            'Role created successfully.',
            data=RoleSerializer(role).data,
            http_status=status.HTTP_201_CREATED,
        )


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_role(self, pk: int) -> Role | None:
        try:
            return (
                Role.objects
                .prefetch_related('role_permissions__permission')
                .annotate(active_user_count=Count('users', filter=Q(users__is_active=True)))
                .get(pk=pk)
            )
        except Role.DoesNotExist:
            return None

    def get(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Role retrieved successfully.', data=RoleSerializer(role).data)

    @staticmethod
    def _check_conflict(role: Role, expected_updated_at: str | None):
        """
        Optimistic-concurrency guard for permission edits.

        Permission saves do a full delete-then-recreate of the role's
        permission set (see RoleSerializer._sync_permissions) — with no
        version check, a second save based on stale data silently wins and
        reverts an earlier save (e.g. two admins/tabs editing the same role
        around the same time). When the client sends back the updated_at it
        loaded the role at, reject the write if the role has changed since.
        Optional — a request without expected_updated_at skips the check
        (used by the is_active-only PATCH, which never touches permissions).
        """
        if not expected_updated_at:
            return None
        from django.utils.dateparse import parse_datetime
        expected_dt = parse_datetime(expected_updated_at)
        if expected_dt and expected_dt != role.updated_at:
            return error(
                'This role was changed by someone else since you loaded it. '
                'Reload the page and try again.',
                http_status=status.HTTP_409_CONFLICT,
            )
        return None

    def put(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        conflict = self._check_conflict(role, request.data.get('expected_updated_at'))
        if conflict:
            return conflict

        serializer = RoleSerializer(role, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated_role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data['name']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        # Permissions are baked into the access/refresh token at login and
        # (per FreshClaimsTokenRefreshSerializer's own docstring) deliberately
        # NOT re-derived on the silent 15-min refresh — that comment assumes
        # "a role/permission change already forces re-login", but nothing
        # actually enforced that until now. Without this, anyone already
        # logged in under this role keeps acting on the OLD permission set
        # for up to the refresh token's full 7-day lifetime after an admin
        # changes what the role can do — backend has_perm() checks would
        # already reflect the new permissions (those hit the DB fresh every
        # request), but the JWT claim and the UI gates reading it would not.
        # Blacklisting every outstanding token for this role's active users
        # forces their next request to 401 and their next login to pick up
        # the real, current permission set — same mechanism
        # EmployeePasswordResetView already uses for a single user.
        affected_user_ids = list(
            User.objects.filter(role=updated_role, is_active=True).values_list('id', flat=True)
        )
        if affected_user_ids:
            for outstanding in OutstandingToken.objects.filter(user_id__in=affected_user_ids):
                BlacklistedToken.objects.get_or_create(token=outstanding)

        AuditLog.objects.create(
            user=request.user, action='role_updated', module='accounts',
            object_id=str(updated_role.id),
            changes={'name': updated_role.name, 'display_name': updated_role.display_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" updated by %s', updated_role.name, request.user.email)
        return success('Role updated successfully.', data=RoleSerializer(updated_role).data)

    def patch(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        # Deactivating strips every user currently assigned this role of its
        # permissions immediately — same real-world effect as deleting it for
        # anyone still assigned, so a system role (provisioned at setup, e.g.
        # system_admin) gets the same protection DELETE already has. A
        # non-system role can still be deactivated; the frontend warns with
        # the exact active-user count first (role.active_user_count, already
        # annotated/serialized) rather than blocking it outright, since
        # deactivation — unlike delete — is reversible.
        if 'is_active' in request.data and not request.data['is_active'] and role.is_system_role:
            return error(
                f'Role "{role.display_name}" is a system role and cannot be deactivated.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RoleSerializer(role, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated_role = serializer.save()
        except IntegrityError:
            return error(
                f"Role '{serializer.validated_data.get('name', role.name)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_updated', module='accounts',
            object_id=str(updated_role.id),
            changes={k: v for k, v in request.data.items() if not hasattr(v, 'read')},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" partially updated by %s', updated_role.name, request.user.email)
        return success('Role updated successfully.', data=RoleSerializer(updated_role).data)

    def delete(self, request, pk):
        role = self._get_role(pk)
        if not role:
            return error('Role not found.', http_status=status.HTTP_404_NOT_FOUND)

        # A real flag, not a hardcoded name set — role names can be (and have
        # been) renamed from Settings, which would silently defeat a
        # name-based check. is_system_role is set once, at provisioning, and
        # survives any later rename.
        if role.is_system_role:
            return error(
                f'Role "{role.display_name}" is a system role and cannot be deleted.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        active_users = role.users.filter(is_active=True).count()
        if active_users:
            return error(
                f'Cannot delete role "{role.display_name}" — '
                f'{active_users} active user(s) are assigned to it. '
                f'Reassign them first.',
                http_status=status.HTTP_409_CONFLICT,
            )

        role_name = role.name
        try:
            role.delete()
        except ProtectedError:
            return error(
                f'Cannot delete role "{role_name}" — it is referenced by other records.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='role_deleted', module='accounts',
            object_id=str(pk),
            changes={'name': role_name},
            ip_address=get_client_ip(request),
        )
        logger.info('Role "%s" deleted by %s', role_name, request.user.email)
        return success(f'Role "{role_name}" deleted successfully.')

    def post(self, request, pk):
        return self.put(request, pk)


# ─── Permission CRUD ──────────────────────────────────────────────────────────

class PermissionListView(APIView):
    # GET is open to any authenticated user — same reasoning as
    # RoleListCreateView.get() above: viewing the permission catalog is what
    # lets the Roles & Permissions page render at all (it fetches roles and
    # permissions together), and read-only visibility into what a role *can*
    # be granted isn't itself a privilege. POST (creating a new permission
    # codename) still requires CanManageRoles, checked explicitly below.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Permission.objects.all().order_by('module', 'action')
        page_obj, paginator = paginate(qs, request, default_page_size=100)
        serialized = PermissionSerializer(page_obj.object_list, many=True).data
        grouped: dict[str, list] = defaultdict(list)
        for perm in serialized:
            grouped[perm['module']].append(perm)
        return success('Permissions retrieved successfully.', data=paginated_data(paginator, page_obj, dict(grouped)))

    def post(self, request):
        if not CanManageRoles().has_permission(request, self):
            return error('You do not have permission to create permissions.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = PermissionSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            permission = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data['codename']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_created', module='accounts',
            object_id=str(permission.id),
            changes={'codename': permission.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" created by %s', permission.codename, request.user.email)
        return success(
            'Permission created successfully.',
            data=PermissionSerializer(permission).data,
            http_status=status.HTTP_201_CREATED,
        )


class PermissionDetailView(APIView):
    permission_classes = [IsAuthenticated, CanManageRoles]

    def _get_permission(self, pk: int) -> Permission | None:
        try:
            return Permission.objects.get(pk=pk)
        except Permission.DoesNotExist:
            return None

    def get(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Permission retrieved successfully.', data=PermissionSerializer(perm).data)

    def put(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = PermissionSerializer(perm, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data['codename']}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_updated', module='accounts',
            object_id=str(updated.id),
            changes={'codename': updated.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" updated by %s', updated.codename, request.user.email)
        return success('Permission updated successfully.', data=PermissionSerializer(updated).data)

    def patch(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = PermissionSerializer(perm, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Permission '{serializer.validated_data.get('codename', perm.codename)}' already exists.",
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_updated', module='accounts',
            object_id=str(updated.id),
            changes={'codename': updated.codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" partially updated by %s', updated.codename, request.user.email)
        return success('Permission updated successfully.', data=PermissionSerializer(updated).data)

    def delete(self, request, pk):
        perm = self._get_permission(pk)
        if not perm:
            return error('Permission not found.', http_status=status.HTTP_404_NOT_FOUND)

        codename = perm.codename
        try:
            perm.delete()
        except ProtectedError:
            return error(
                f'Cannot delete permission "{codename}" — it is assigned to one or more roles. '
                'Remove it from all roles first.',
                http_status=status.HTTP_409_CONFLICT,
            )

        AuditLog.objects.create(
            user=request.user, action='permission_deleted', module='accounts',
            changes={'codename': codename},
            ip_address=get_client_ip(request),
        )
        logger.info('Permission "%s" deleted by %s', codename, request.user.email)
        return success(f'Permission "{codename}" deleted successfully.')

    def post(self, request, pk):
        return self.put(request, pk)


