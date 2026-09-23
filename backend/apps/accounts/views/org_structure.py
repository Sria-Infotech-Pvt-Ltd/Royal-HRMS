
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

# ─── Org Structure (units, positions, job templates) ──────────────────────────
# Replaces the old computed-from-User.department org chart above (removed —
# see TEAMCONTEXT.md for what it used to do) with a real, admin-editable
# hierarchy. Read access reuses org_chart.view (already granted to every
# role by migration 0086); writes need org_structure.create/edit/delete
# (migration 0101, granted to whichever roles already hold departments.edit).
# Deliberately independent of User.department/reporting_manager — those keep
# driving real approval routing exactly as before; Position.holder and the
# derived "reports_to" here are a separate, purely structural view.

class JobTemplateListCreateView(APIView):
    """Seeded once via migration 0101, now also manageable from the UI
    (Org Chart → "Manage job templates") like OrgUnit/Position. Returns both
    active and inactive templates — pickers that should only offer active
    ones (Add Position, Leave Policy eligibility) filter client-side."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view this.', http_status=status.HTTP_403_FORBIDDEN)
        qs = JobTemplate.objects.all()
        return success('Job templates retrieved.', data=JobTemplateSerializer(qs, many=True).data)

    def post(self, request):
        if not _has_perm(request.user, 'org_structure.create'):
            return error('You do not have permission to create job templates.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = JobTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        AuditLog.objects.create(
            user=request.user, action='create', module='org_structure',
            object_id=str(instance.pk), changes={'name': instance.name},
            ip_address=get_client_ip(request),
        )
        return success('Job template created.', data=JobTemplateSerializer(instance).data)


class JobTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return JobTemplate.objects.get(pk=pk)
        except JobTemplate.DoesNotExist:
            return None

    def put(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit job templates.', http_status=status.HTTP_403_FORBIDDEN)
        template = self._get(pk)
        if not template:
            return error('Job template not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = JobTemplateSerializer(template, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(instance.pk), changes={'name': instance.name},
            ip_address=get_client_ip(request),
        )
        return success('Job template updated.', data=JobTemplateSerializer(instance).data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'org_structure.delete'):
            return error('You do not have permission to delete job templates.', http_status=status.HTTP_403_FORBIDDEN)
        template = self._get(pk)
        if not template:
            return error('Job template not found.', http_status=status.HTTP_404_NOT_FOUND)
        in_use = template.positions.count()
        if in_use:
            return error(
                f'Cannot delete "{template.name}" — still referenced by {in_use} position(s). Deactivate it instead.',
                http_status=status.HTTP_409_CONFLICT,
            )
        name = template.name
        template_id = str(template.pk)
        template.delete()
        AuditLog.objects.create(
            user=request.user, action='delete', module='org_structure',
            object_id=template_id, changes={'name': name},
            ip_address=get_client_ip(request),
        )
        return success(f'"{name}" deleted.', data={})


class OrgUnitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)
        # Annotated so OrgUnitSerializer's position_count/child_count don't
        # each run their own obj.positions.count()/obj.children.count() query
        # per row — with 44 units that was 88 sequential queries for one
        # list call (measured ~9s locally). distinct=True on both Count()s
        # is required here, not optional — annotating two independent
        # reverse relations (positions and children) in the same query joins
        # both, and without distinct=True each count would be inflated by
        # the other relation's row multiplication.
        # Explicit order_by (Meta.ordering alone stops counting as "ordered"
        # once an aggregate annotation forces a GROUP BY, which trips
        # paginate()'s UnorderedObjectListWarning even though the underlying
        # Meta.ordering = ['name'] is unchanged).
        qs = OrgUnit.objects.annotate(
            _position_count_annotated=Count('positions', distinct=True),
            _child_count_annotated=Count('children', distinct=True),
        ).order_by('name')
        # The frontend fetches the whole tree in one shot (?page_size=200) to
        # build parent/child relationships client-side — paginate()'s default
        # max_page_size=100 was silently clamping that below what a real org
        # chart needs, so it must be raised here too, not just default_page_size.
        page_obj, paginator = paginate(qs, request, default_page_size=200, max_page_size=1000)
        return success('Org units retrieved.', data=paginated_data(
            paginator, page_obj, OrgUnitSerializer(page_obj.object_list, many=True).data,
        ))

    def post(self, request):
        if not _has_perm(request.user, 'org_structure.create'):
            return error('You do not have permission to create org units.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = OrgUnitSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        AuditLog.objects.create(
            user=request.user, action='create', module='org_structure',
            object_id=str(instance.pk), changes={'name': instance.name},
            ip_address=get_client_ip(request),
        )
        return success('Org unit created.', data=OrgUnitSerializer(instance).data)


class OrgUnitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return OrgUnit.objects.select_related('parent').get(pk=pk)
        except OrgUnit.DoesNotExist:
            return None

    def put(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit org units.', http_status=status.HTTP_403_FORBIDDEN)
        unit = self._get(pk)
        if not unit:
            return error('Org unit not found.', http_status=status.HTTP_404_NOT_FOUND)

        # Turning off is_department_level can silently change Leave Policy
        # eligibility for anyone currently resolving their department
        # through this unit — warn (via a 409 the frontend confirms
        # through) rather than let that go unnoticed, unless the caller
        # has already confirmed it via confirm_department_change.
        turning_off_department = (
            unit.is_department_level
            and 'is_department_level' in request.data
            and str(request.data.get('is_department_level')).strip().lower() in ('false', '0')
            and str(request.data.get('confirm_department_change', '')).strip().lower() not in ('true', '1')
        )
        if turning_off_department:
            from apps.accounts.services_approval import employees_depending_on_department_flag
            affected = employees_depending_on_department_flag(unit)
            if affected:
                shown = ', '.join(affected[:5])
                more = f', and {len(affected) - 5} more' if len(affected) > 5 else ''
                return error(
                    f'"{unit.name}" is currently the resolved department for '
                    f'{len(affected)} employee(s) ({shown}{more}) — turning this off '
                    f'changes their Leave Policy eligibility. Confirm to proceed anyway.',
                    http_status=status.HTTP_409_CONFLICT,
                    data={'affected_count': len(affected), 'affected_names': affected},
                )

        serializer = OrgUnitSerializer(unit, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(instance.pk), changes={'name': instance.name},
            ip_address=get_client_ip(request),
        )
        return success('Org unit updated.', data=OrgUnitSerializer(instance).data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'org_structure.delete'):
            return error('You do not have permission to delete org units.', http_status=status.HTTP_403_FORBIDDEN)
        unit = self._get(pk)
        if not unit:
            return error('Org unit not found.', http_status=status.HTTP_404_NOT_FOUND)
        if unit.children.exists():
            return error(
                f'Cannot delete "{unit.name}" — it has sub-units. Remove or move those first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        # A position with a CURRENT holder obviously has placement history,
        # so checking "any placement ever" (not just "any position at all")
        # covers both "someone is assigned right now" and "someone held
        # this seat before and it's vacant again" — either way that's real
        # history Placement.position's PROTECT would refuse to cascade
        # through anyway. Only truly untouched positions (never placed,
        # ever) make the whole unit safe to hard-delete.
        if unit.positions.filter(placements__isnull=False).exists():
            return error(
                f'Cannot delete "{unit.name}" — one or more of its positions has been held by '
                f'someone, now or in the past. Deactivate the unit instead to preserve that history.',
                http_status=status.HTTP_409_CONFLICT,
            )
        name = unit.name
        unit_id = str(unit.pk)
        unit.delete()
        AuditLog.objects.create(
            user=request.user, action='delete', module='org_structure',
            object_id=unit_id, changes={'name': name},
            ip_address=get_client_ip(request),
        )
        return success(f'"{name}" deleted.', data={})


class OrgUnitDeactivateView(APIView):
    """Alternative to hard-delete once a unit has real history under it —
    deleting history is a compliance problem, per this feature's spec."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit org units.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            unit = OrgUnit.objects.get(pk=pk)
        except OrgUnit.DoesNotExist:
            return error('Org unit not found.', http_status=status.HTTP_404_NOT_FOUND)
        unit.is_active = False
        unit.save(update_fields=['is_active', 'updated_at'])
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(unit.pk), changes={'name': unit.name, 'is_active': False},
            ip_address=get_client_ip(request),
        )
        return success(f'"{unit.name}" deactivated.', data=OrgUnitSerializer(unit).data)


class OrgOverviewView(APIView):
    """Read-only summary for the Organization landing page — KPI counts, a
    per-unit overview table, and location list. Every number here is a real
    query against OrgUnit/Position/Placement/Branch/CompanyGSTRegistration,
    never hardcoded — this view exists purely to pre-aggregate what the
    org-chart tree page (org-structure/units/, /positions/) already exposes
    row-by-row, into the small set of figures a landing dashboard needs."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)

        from apps.branch.models import Branch

        today = timezone.localdate()
        current_placement_qs = Placement.objects.filter(
            position=OuterRef('pk'), effective_from__lte=today,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))

        positions = Position.objects.filter(is_active=True).annotate(
            _has_holder=Exists(current_placement_qs),
        )
        vacant_positions = positions.filter(_has_holder=False)

        active_units = OrgUnit.objects.filter(is_active=True)
        active_branches = Branch.objects.filter(status=Branch.STATUS_ACTIVE)

        legal_entities_count = CompanyGSTRegistration.objects.count()
        org_units_count = active_units.count()
        departments_count = active_units.filter(is_department_level=True).count()
        locations_count = active_branches.count()
        open_positions_count = vacant_positions.count()
        manager_vacancy_count = vacant_positions.filter(is_chief=True).count()

        # One row per active unit, top-level units first then their direct
        # children (grouped right under their parent) — matches how the
        # tree itself reads, one level deep, without needing a full
        # recursive walk for what's meant to be a quick-glance summary.
        units = list(
            active_units.select_related('parent')
            .annotate(_child_count=Count('children', filter=Q(children__is_active=True), distinct=True))
            .order_by('name')
        )
        by_parent: dict[str | None, list] = {}
        for u in units:
            by_parent.setdefault(str(u.parent_id) if u.parent_id else None, []).append(u)

        rows = []
        for unit in by_parent.get(None, []):
            rows.append(unit)
            rows.extend(by_parent.get(str(unit.pk), []))

        unit_ids = [u.pk for u in rows]
        unit_positions = list(
            positions.filter(org_unit_id__in=unit_ids).values('org_unit_id', 'is_chief', '_has_holder')
        )
        per_unit: dict[str, dict] = {}
        for p in unit_positions:
            bucket = per_unit.setdefault(str(p['org_unit_id']), {'headcount': 0, 'vacant': 0, 'vacant_chief': 0})
            if p['_has_holder']:
                bucket['headcount'] += 1
            else:
                bucket['vacant'] += 1
                if p['is_chief']:
                    bucket['vacant_chief'] += 1

        overview = []
        for unit in rows:
            stats = per_unit.get(str(unit.pk), {'headcount': 0, 'vacant': 0, 'vacant_chief': 0})
            if stats['vacant_chief']:
                status_kind, status_label = 'manager_vacancy', f"{stats['vacant_chief']} manager vacancy"
            elif stats['vacant']:
                status_kind, status_label = 'open_positions', f"{stats['vacant']} open positions"
            else:
                status_kind, status_label = 'headcount', f"{stats['headcount']} employees"

            if unit.parent_id:
                context_label = unit.parent.name
            elif unit._child_count:
                context_label = f"{unit._child_count} departments"
            else:
                context_label = unit.cost_center or '—'

            overview.append({
                'id': str(unit.pk),
                'name': unit.name,
                'context_label': context_label,
                'status_kind': status_kind,
                'status_label': status_label,
            })

        return success('Organization overview retrieved.', data={
            'legal_entities': {'count': legal_entities_count},
            'org_units': {'count': org_units_count},
            'departments': {'count': departments_count, 'locations_count': locations_count},
            'open_positions': {'count': open_positions_count, 'manager_vacancy_count': manager_vacancy_count},
            'locations': list(active_branches.order_by('branch_name').values_list('branch_name', flat=True)),
            'overview_rows': overview,
            'headcount_by_unit': [
                {'name': u.name, 'headcount': per_unit.get(str(u.pk), {}).get('headcount', 0)}
                for u in by_parent.get(None, [])
            ],
        })




_POSITION_PREFETCH = ('placements__employee',)
_POSITION_SELECT = ('org_unit', 'org_unit__parent', 'job_template', 'branch')


class PositionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)
        as_of, err = _parse_as_of(request)
        if err:
            return err
        qs = Position.objects.select_related(*_POSITION_SELECT).prefetch_related(*_POSITION_PREFETCH)
        if branch_id := request.query_params.get('branch'):
            try:
                branch_id = int(branch_id)
            except (TypeError, ValueError):
                return error('branch filter must be a valid integer ID.')
            qs = qs.filter(branch_id=branch_id)
        # See the matching comment on OrgUnitListCreateView.get() — same
        # max_page_size clamp was truncating any org chart bigger than 100
        # positions (e.g. 223 positions -> only the first 100 ever returned).
        page_obj, paginator = paginate(qs, request, default_page_size=200, max_page_size=1000)
        # One query for every chief position in the system (there's exactly
        # one per org unit, so this is small regardless of how many
        # positions are on the page) instead of PositionSerializer.
        # get_reports_to() running its own query per row — see that
        # method's docstring for why this matters now.
        chief_by_unit = {
            p.org_unit_id: p
            for p in Position.objects.filter(is_chief=True)
                .select_related('org_unit').prefetch_related('placements__employee')
        }
        return success('Positions retrieved.', data=paginated_data(
            paginator, page_obj,
            PositionSerializer(
                page_obj.object_list, many=True,
                context={'as_of': as_of, 'chief_by_unit': chief_by_unit},
            ).data,
        ))

    def post(self, request):
        if not _has_perm(request.user, 'org_structure.create'):
            return error('You do not have permission to create positions.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = PositionSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        # Positions are always created vacant — a holder is assigned
        # separately via PositionPlacementListCreateView, which is what
        # actually creates the first Placement and triggers the designation
        # sync. Nothing to sync here.
        AuditLog.objects.create(
            user=request.user, action='create', module='org_structure',
            object_id=str(instance.pk), changes={'title': instance.title},
            ip_address=get_client_ip(request),
        )
        return success('Position created.', data=PositionSerializer(instance).data)


class PositionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Position.objects.select_related(*_POSITION_SELECT).prefetch_related(*_POSITION_PREFETCH).get(pk=pk)
        except Position.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)
        as_of, err = _parse_as_of(request)
        if err:
            return err
        position = self._get(pk)
        if not position:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Position retrieved.', data=PositionSerializer(position, context={'as_of': as_of}).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit positions.', http_status=status.HTTP_403_FORBIDDEN)
        position = self._get(pk)
        if not position:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = PositionSerializer(position, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        instance = serializer.save()
        # Title/org_unit/job_template can change the position's effective
        # title (and org_unit change can change its linked department) —
        # re-sync the current holder if there is one (non-forced: respects
        # a manual override, same as before).
        sync_from_position(instance)
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(instance.pk), changes={'title': instance.title},
            ip_address=get_client_ip(request),
        )
        return success('Position updated.', data=PositionSerializer(instance).data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'org_structure.delete'):
            return error('You do not have permission to delete positions.', http_status=status.HTTP_403_FORBIDDEN)
        position = self._get(pk)
        if not position:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        if position.placements.exists():
            return error(
                f'Cannot delete "{position.title}" — it has placement history. Deactivate it instead; deleting history is not allowed.',
                http_status=status.HTTP_409_CONFLICT,
            )
        title = position.title
        position_id = str(position.pk)
        position.delete()
        AuditLog.objects.create(
            user=request.user, action='delete', module='org_structure',
            object_id=position_id, changes={'title': title},
            ip_address=get_client_ip(request),
        )
        return success(f'"{title}" deleted.', data={})


class PositionDeactivateView(APIView):
    """Alternative to hard-delete once a position has placement history —
    see PositionDetailView.delete()'s 409 for the same rationale."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit positions.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            position = Position.objects.get(pk=pk)
        except Position.DoesNotExist:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        position.is_active = False
        position.save(update_fields=['is_active', 'updated_at'])
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(position.pk), changes={'title': position.title, 'is_active': False},
            ip_address=get_client_ip(request),
        )
        return success(f'"{position.title}" deactivated.', data=PositionSerializer(position).data)


class PositionActivateView(APIView):
    """Reverses PositionDeactivateView — deactivating is meant to be
    reversible (nothing about it touches placement history), so it needs
    an undo path rather than being a one-way door."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit positions.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            position = Position.objects.get(pk=pk)
        except Position.DoesNotExist:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        position.is_active = True
        position.save(update_fields=['is_active', 'updated_at'])
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(position.pk), changes={'title': position.title, 'is_active': True},
            ip_address=get_client_ip(request),
        )
        return success(f'"{position.title}" reactivated.', data=PositionSerializer(position).data)


class PositionPlacementListCreateView(APIView):
    """Handles both viewing a position's full placement history and
    assigning/reassigning its holder — POSTing a new placement is how a
    seat goes from vacant to filled, or from one holder to the next."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            position = Position.objects.get(pk=pk)
        except Position.DoesNotExist:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        qs = position.placements.select_related('employee', 'created_by').all()
        return success('Placement history retrieved.', data=PlacementSerializer(qs, many=True).data)

    def post(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to assign position holders.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            position = Position.objects.select_related('org_unit').get(pk=pk)
        except Position.DoesNotExist:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)

        employee_id = request.data.get('employee')
        effective_from_raw = request.data.get('effective_from')
        effective_to_raw = request.data.get('effective_to') or None
        if not employee_id:
            return error('employee is required.')
        if not effective_from_raw:
            return error('effective_from is required.')
        try:
            effective_from = date.fromisoformat(effective_from_raw)
        except (TypeError, ValueError):
            return error('effective_from must be a valid YYYY-MM-DD date.')
        effective_to = None
        if effective_to_raw:
            try:
                effective_to = date.fromisoformat(effective_to_raw)
            except (TypeError, ValueError):
                return error('effective_to must be a valid YYYY-MM-DD date.')
            if effective_to < effective_from:
                return error('effective_to cannot be before effective_from.')
        try:
            employee = User.objects.get(pk=employee_id, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        placement = assign_position(
            employee, position,
            effective_from=effective_from, effective_to=effective_to,
            note=(request.data.get('note') or '').strip(), created_by=request.user,
        )
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(position.pk),
            changes={'title': position.title, 'placement': str(placement.pk), 'employee': employee.full_name},
            ip_address=get_client_ip(request),
        )
        position.refresh_from_db()
        return success('Holder assigned.', data=PositionSerializer(position).data)


class PositionPlacementEndView(APIView):
    """Vacates a position by closing its current open placement — the seat
    is vacant starting the day after effective_to, not immediately, since
    effective_to is the last day actually worked."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to vacate positions.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            position = Position.objects.get(pk=pk)
        except Position.DoesNotExist:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        placement = position.placements.filter(effective_to__isnull=True).first()
        if placement is None:
            return error('This position has no current holder to vacate.', http_status=status.HTTP_409_CONFLICT)

        effective_to_raw = request.data.get('effective_to')
        effective_to = timezone.localdate()
        if effective_to_raw:
            try:
                effective_to = date.fromisoformat(effective_to_raw)
            except (TypeError, ValueError):
                return error('effective_to must be a valid YYYY-MM-DD date.')
        if effective_to < placement.effective_from:
            return error('effective_to cannot be before the placement started.')

        placement.effective_to = effective_to
        note = (request.data.get('note') or '').strip()
        if note:
            placement.note = note
        placement.full_clean()
        placement.save(update_fields=['effective_to', 'note', 'updated_at'])
        # Deliberately does not touch the former holder's User.designation —
        # vacating a seat means "no longer occupying this org-chart slot,"
        # not "no longer has a job." Blanking or reverting it here would
        # actively break leave-policy eligibility and announcement targeting
        # for someone who is still employed.
        AuditLog.objects.create(
            user=request.user, action='update', module='org_structure',
            object_id=str(position.pk),
            changes={'title': position.title, 'placement': str(placement.pk), 'effective_to': str(effective_to)},
            ip_address=get_client_ip(request),
        )
        position.refresh_from_db()
        return success('Position vacated.', data=PositionSerializer(position).data)


class PlacementDetailView(APIView):
    """DELETE only — cancels a scheduled (future) placement outright, or a
    past/current one if the caller holds org_structure.backdate. There's no
    generic edit here on purpose: tenure/payroll/gratuity depend on these
    dates, so touching history is deliberately narrower than "edit a field"."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not _has_perm(request.user, 'org_structure.edit'):
            return error('You do not have permission to edit placements.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            placement = Placement.objects.select_related('position', 'employee').get(pk=pk)
        except Placement.DoesNotExist:
            return error('Placement not found.', http_status=status.HTTP_404_NOT_FOUND)
        today = timezone.localdate()
        is_scheduled = placement.effective_from > today
        if not is_scheduled and not _has_perm(request.user, 'org_structure.backdate'):
            return error(
                'Only a scheduled (future) placement can be cancelled without the backdate permission.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        position = placement.position
        details = {
            'title': position.title, 'employee': placement.employee.full_name,
            'effective_from': str(placement.effective_from), 'effective_to': str(placement.effective_to),
        }
        with transaction.atomic():
            # If this placement's creation auto-closed the one before it
            # (see PositionPlacementListCreateView.post()'s "close the prior
            # open placement the day before" step), cancelling it should undo
            # that too — otherwise the previous holder is left with a bogus
            # future end-date for a successor who never actually started.
            # Delete first: the exclusion constraints check immediately, not
            # deferred, so reopening the prior placement before removing this
            # one would briefly overlap them and get rejected.
            reopened = position.placements.filter(
                effective_to=placement.effective_from - timedelta(days=1),
            ).exclude(pk=placement.pk).first()
            placement.delete()
            if reopened is not None:
                reopened.effective_to = None
                reopened.save(update_fields=['effective_to', 'updated_at'])
                details['reopened_placement'] = str(reopened.pk)
        AuditLog.objects.create(
            user=request.user, action='delete', module='org_structure',
            object_id=str(position.pk), changes=details,
            ip_address=get_client_ip(request),
        )
        return success('Placement cancelled.', data={})


