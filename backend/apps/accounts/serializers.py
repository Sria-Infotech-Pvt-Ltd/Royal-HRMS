
from __future__ import annotations

import os
import re

from django.core import signing
from django.db import transaction

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import date
from django.utils import timezone
from rest_framework import serializers

from core.permissions import has_perm as _has_perm
from core.file_validation import validate_file_content as _validate_file_content

from apps.accounts.models import (
    AuditLog,
    Company,
    CompanyDirector,
    CompanyGSTRegistration,
    CustomFieldFileValue,
    Document,
    DocumentTypeConfig,
    EducationExperienceFieldConfig,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeCodeSettings,
    EmployeeDocument,
    EmployeeProfile,
    HireActionDocument,
    JobTemplate,
    OnboardingFieldConfig,
    OnboardingSection,
    OrgUnit,
    Permission,
    Placement,
    Position,
    Role,
    RolePermission,
    SMTPSettings,
    User,
)

# Pre-compiled regex for reuse
_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')


# ─── Role & Permission ────────────────────────────────────────────────────────

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Permission
        fields = ('id', 'codename', 'module', 'action')


class RoleSerializer(serializers.ModelSerializer):
    permissions  = serializers.SerializerMethodField()
    user_count   = serializers.SerializerMethodField()
    # Write-only: list of codenames sent by client when creating / updating
    permission_codenames = serializers.ListField(
        child      = serializers.CharField(max_length=100),
        write_only = True,
        required   = False,
        default    = list,
    )

    class Meta:
        model  = Role
        fields = (
            'id', 'name', 'display_name', 'is_active', 'can_manage_team',
            'can_manage_branch', 'is_system_role',
            'permissions', 'permission_codenames', 'user_count',
            'created_at', 'updated_at',
        )
        # can_manage_branch is writable the same way can_manage_team already
        # is — an admin can grant unconditional branch-scoped access to any
        # role, not just the seeded Branch Admin. Callers (e.g. the "assign
        # Branch Admin" picker) find the role by this capability instead of
        # matching its name, same as core/permissions.py does server-side.
        # is_system_role is never settable by any client — provisioning-time only.
        read_only_fields = ('id', 'created_at', 'updated_at', 'is_system_role')

    def get_permissions(self, obj: Role) -> list[str]:
        # Uses prefetch_related('role_permissions__permission') cache — no extra query.
        return [rp.permission.codename for rp in obj.role_permissions.all()]

    def get_user_count(self, obj: Role) -> int:
        # Uses annotated active_user_count when available — no extra query.
        if hasattr(obj, 'active_user_count'):
            return obj.active_user_count
        return obj.users.filter(is_active=True).count()

    def validate_name(self, value: str) -> str:
        if not _NAME_RE.match(value):
            raise serializers.ValidationError(
                'Role name must start with a letter and contain only lowercase letters, '
                'digits, and underscores (e.g. hr_admin).'
            )
        return value

    def validate_permission_codenames(self, value: list[str]) -> list[str]:
        if not value:
            return value
        if len(value) > 200:
            raise serializers.ValidationError(
                'A role cannot be assigned more than 200 permissions at once.'
            )
        existing = set(
            Permission.objects.filter(codename__in=value)
                              .values_list('codename', flat=True)
        )
        invalid = set(value) - existing
        if invalid:
            raise serializers.ValidationError(
                f'Unknown permission codename(s): {", ".join(sorted(invalid))}'
            )
        return value

    def create(self, validated_data: dict) -> Role:
        from django.db import transaction
        codenames = validated_data.pop('permission_codenames', [])
        with transaction.atomic():
            role = Role.objects.create(**validated_data)
            self._sync_permissions(role, codenames)
        return role

    def update(self, instance: Role, validated_data: dict) -> Role:
        from django.db import transaction
        codenames = validated_data.pop('permission_codenames', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if codenames is not None:
                self._sync_permissions(instance, codenames)
        return instance

    @staticmethod
    def _sync_permissions(role: Role, codenames: list[str]) -> None:
        role.role_permissions.all().delete()
        if codenames:
            perms = Permission.objects.filter(codename__in=codenames)
            RolePermission.objects.bulk_create(
                [RolePermission(role=role, permission=p) for p in perms],
                ignore_conflicts=True,
            )


# ─── Auth serializers ─────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    email        = serializers.EmailField()
    password     = serializers.CharField(min_length=1, max_length=128)


class ForgotPasswordSerializer(serializers.Serializer):
    email        = serializers.EmailField()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp   = serializers.CharField(min_length=6, max_length=6)

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain digits only.')
        return value


class ResetPasswordSerializer(serializers.Serializer):
    reset_token      = serializers.UUIDField()
    new_password     = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password     = serializers.CharField(min_length=1, max_length=128, write_only=True)
    new_password     = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from the current password.'}
            )
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


# ─── SMTP Settings ────────────────────────────────────────────────────────────

class SMTPSettingsSerializer(serializers.ModelSerializer):
    password_display  = serializers.SerializerMethodField()
    smtp_type_display = serializers.CharField(source='get_smtp_type_display', read_only=True)
    password          = serializers.CharField(write_only=True, required=False, max_length=255)

    class Meta:
        model  = SMTPSettings
        fields = (
            'id', 'name',
            'smtp_type', 'smtp_type_display',
            'host', 'port', 'username',
            'password', 'password_display',
            'use_tls', 'sender_name', 'from_email', 'bcc_email',
            'priority', 'receiver_email_type',
            'is_active', 'updated_at',
        )
        read_only_fields = ('id', 'updated_at', 'password_display', 'smtp_type_display', 'is_active')

    def get_password_display(self, obj: SMTPSettings) -> str:
        return '••••••••' if obj.password else ''

    def validate_name(self, value: str) -> str:
        v = value.strip()
        if not v:
            raise serializers.ValidationError('Name must not be blank.')
        return v

    def validate_host(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Host must not be blank.')
        return value.strip()

    def validate_port(self, value: int) -> int:
        if not (1 <= value <= 65535):
            raise serializers.ValidationError('Port must be between 1 and 65535.')
        return value

    def validate_username(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError('SMTP username must not be blank.')
        return value.strip()

    def validate_from_email(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('From email must not be blank.')
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        instance = self.instance
        new_name = attrs.get('name', getattr(instance, 'name', None))
        if new_name:
            qs = SMTPSettings.objects.filter(name__iexact=new_name)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'name': f'An SMTP config named "{new_name}" already exists.'}
                )
        return attrs


class SMTPTestSerializer(serializers.Serializer):
    host           = serializers.CharField(max_length=255)
    port           = serializers.IntegerField(min_value=1, max_value=65535)
    username       = serializers.CharField(max_length=255)   # may be email OR plain username
    password       = serializers.CharField(max_length=255)
    use_tls        = serializers.BooleanField(default=True)
    sender_name    = serializers.CharField(required=False, allow_blank=True, default='', max_length=255)
    from_email     = serializers.EmailField()
    bcc_email      = serializers.EmailField(required=False, allow_blank=True, default='')
    test_recipient = serializers.EmailField()

    def validate_host(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Host must not be blank.')
        return value.strip()

    def validate_sender_name(self, value: str) -> str:
        if '\r' in value or '\n' in value:
            raise serializers.ValidationError('Sender name must not contain line breaks.')
        return value


# ─── Email Templates ──────────────────────────────────────────────────────────

class EmailTemplateCategorySerializer(serializers.ModelSerializer):
    template_count = serializers.SerializerMethodField()

    class Meta:
        model  = EmailTemplateCategory
        fields = ('id', 'name', 'display_name', 'is_builtin', 'order', 'template_count')
        read_only_fields = ('id', 'is_builtin', 'template_count')

    def get_template_count(self, obj: EmailTemplateCategory) -> int:
        counts = self.context.get('template_counts')
        if counts is not None:
            return counts.get(obj.name, 0)
        return EmailTemplate.objects.filter(template_type=obj.name).count()

    def validate_name(self, value: str) -> str:
        if not _NAME_RE.match(value):
            raise serializers.ValidationError(
                'Name must start with a letter and contain only lowercase letters, '
                'digits, and underscores (e.g. birthday_wishes).'
            )
        return value


class EmailTemplateAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model  = EmailTemplateAttachment
        fields = ('id', 'filename', 'mime_type', 'size', 'url', 'uploaded_at')
        read_only_fields = ('id', 'filename', 'mime_type', 'size', 'url', 'uploaded_at')

    def get_url(self, obj):
        if not obj.file or not obj.file.name:
            return ''
        url = obj.file.url
        request = self.context.get('request')
        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)
        return url


class EmailTemplateSerializer(serializers.ModelSerializer):
    template_type_display = serializers.SerializerMethodField()
    attachments           = EmailTemplateAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model  = EmailTemplate
        fields = (
            'id', 'name', 'display_name', 'description',
            'template_type', 'template_type_display',
            'subject', 'body',
            'is_active', 'is_builtin',
            'available_variables', 'updated_at',
            'attachments',
        )
        read_only_fields = ('id', 'is_builtin', 'updated_at', 'template_type_display')

    def get_template_type_display(self, obj: EmailTemplate) -> str:
        category_map = self.context.get('category_map')
        if category_map is not None:
            return category_map.get(obj.template_type, obj.template_type)
        try:
            return EmailTemplateCategory.objects.get(name=obj.template_type).display_name
        except EmailTemplateCategory.DoesNotExist:
            return obj.template_type

    def validate_template_type(self, value: str) -> str:
        if not EmailTemplateCategory.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f'Template type "{value}" does not exist. '
                'Create it first via POST /api/settings/email-template-categories/.'
            )
        return value

    def validate_name(self, value: str) -> str:
        if not _NAME_RE.match(value):
            raise serializers.ValidationError(
                'Name must start with a letter and contain only lowercase letters, '
                'digits, and underscores (e.g. birthday_wish).'
            )
        return value

    def validate_subject(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Subject must not be blank.')
        return value.strip()

    def validate_body(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Body must not be blank.')
        return value

    def validate(self, attrs: dict) -> dict:
        instance = self.instance

        # Built-in templates: protect the name from being changed
        if instance and instance.is_builtin:
            new_name = attrs.get('name', instance.name)
            if new_name != instance.name:
                raise serializers.ValidationError(
                    {'name': 'The name of a built-in template cannot be changed.'}
                )

        # Name uniqueness on update (create uniqueness is enforced by the DB unique constraint)
        if instance:
            new_name = attrs.get('name', instance.name)
            if (
                new_name != instance.name
                and EmailTemplate.objects.filter(name=new_name).exclude(pk=instance.pk).exists()
            ):
                raise serializers.ValidationError(
                    {'name': f'A template with the name "{new_name}" already exists.'}
                )

        return attrs


class EmailTemplatePreviewSerializer(serializers.Serializer):
    """Context variables to use when rendering a preview of the template."""
    context = serializers.DictField(
        child    = serializers.CharField(allow_blank=True),
        required = False,
        default  = dict,
    )


# ─── Org Structure (units, positions, job templates) ──────────────────────────
# Replaced Department/Designation entirely (Stage 6) — a real hierarchy with
# its own Position/Placement model.

class JobTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = JobTemplate
        fields = ('id', 'name', 'band', 'is_active')
        read_only_fields = ('id',)


class OrgUnitSerializer(serializers.ModelSerializer):
    position_count  = serializers.SerializerMethodField()
    child_count     = serializers.SerializerMethodField()

    class Meta:
        model  = OrgUnit
        fields = (
            'id', 'name', 'code', 'parent', 'cost_center', 'is_active',
            'is_department_level',
            'position_count', 'child_count', 'created_at', 'updated_at',
        )
        # is_active is set only via the dedicated deactivate action (audit-
        # logged there), never through a generic field update here.
        # is_department_level is writable — an admin marks a unit as
        # representing a real department through the same generic PUT this
        # page already uses for parent/cost_center.
        read_only_fields = ('id', 'is_active', 'position_count', 'child_count', 'created_at', 'updated_at')

    def get_position_count(self, obj: OrgUnit) -> int:
        # Prefer the queryset-level annotation (see OrgUnitListCreateView.get)
        # so a list of N units doesn't run N of these as separate queries —
        # falls back to a direct count for the single-object call sites
        # (create/update/deactivate responses) that don't annotate.
        annotated = getattr(obj, '_position_count_annotated', None)
        return annotated if annotated is not None else obj.positions.count()

    def get_child_count(self, obj: OrgUnit) -> int:
        annotated = getattr(obj, '_child_count_annotated', None)
        return annotated if annotated is not None else obj.children.count()

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Unit name is required.')
        if len(value) > 150:
            raise serializers.ValidationError('Unit name must be under 150 characters.')
        return value

    def validate_parent(self, value):
        if value and self.instance:
            node = value
            while node is not None:
                if node.pk == self.instance.pk:
                    raise serializers.ValidationError('This would create a circular reporting structure.')
                node = node.parent
        return value


class PositionSerializer(serializers.ModelSerializer):
    """`holder`/`holder_name`/`holder_employee_id` are read-only, computed
    from whichever Placement on this position covers `context['as_of']`
    (default today) — not a stored field. Assigning/reassigning/ending a
    holder happens through the dedicated Placement endpoints, not by
    writing to this serializer. Field names are kept identical to the old
    stored-FK version on purpose, so every existing frontend consumer
    (OrgTree, most of OrgDetail, the stats strip) needed zero changes."""
    org_unit_name       = serializers.CharField(source='org_unit.name', read_only=True)
    job_template_name   = serializers.CharField(source='job_template.name', read_only=True, default=None)
    branch_name         = serializers.CharField(source='branch.branch_name', read_only=True, default=None)
    default_role_name   = serializers.CharField(source='default_role.display_name', read_only=True, default=None)
    holder              = serializers.SerializerMethodField()
    holder_name         = serializers.SerializerMethodField()
    holder_employee_id  = serializers.SerializerMethodField()
    holder_since        = serializers.SerializerMethodField()
    scheduled           = serializers.SerializerMethodField()
    reports_to          = serializers.SerializerMethodField()

    class Meta:
        model  = Position
        fields = (
            'id', 'org_unit', 'org_unit_name', 'job_template', 'job_template_name',
            'title', 'grade', 'is_chief', 'is_active',
            'holder', 'holder_name', 'holder_employee_id', 'holder_since', 'scheduled',
            'branch', 'branch_name', 'default_role', 'default_role_name',
            'reports_to', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'org_unit_name', 'job_template_name', 'is_active',
            'holder', 'holder_name', 'holder_employee_id', 'holder_since', 'scheduled',
            'branch_name', 'default_role_name', 'reports_to', 'created_at', 'updated_at',
        )

    def validate_default_role(self, value):
        # Same rule as assigning a Role to an employee directly (Create/Edit
        # Employee, views.py) — a seat can't default to a Role that carries
        # settings.edit, one level up from the employee-level guard. A
        # can_manage_branch role is excluded too: Branch Admin is assigned
        # via Designation, never via a Position, so it could never actually
        # be reached through a seat's default anyway.
        if value and (
            value.role_permissions.filter(permission__codename='settings.edit').exists()
            or value.can_manage_branch
        ):
            raise serializers.ValidationError(
                f'"{value.display_name}" cannot be set as a seat\'s default role.'
            )
        return value

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position title is required.')
        if len(value) > 150:
            raise serializers.ValidationError('Position title must be under 150 characters.')
        return value

    def _as_of(self):
        return self.context.get('as_of') or timezone.localdate()

    def _all_placements(self, obj: Position) -> list:
        # If the queryset prefetched `placements` (see PositionListCreateView),
        # this list comes for free; otherwise it's one query per position —
        # correct either way, just not equally cheap.
        return list(obj.placements.all())

    def _current_placement(self, obj: Position):
        cache_attr = '_current_placement_cache'
        if not hasattr(obj, cache_attr):
            as_of = self._as_of()
            current = next(
                (p for p in self._all_placements(obj)
                 if p.effective_from <= as_of and (p.effective_to is None or p.effective_to >= as_of)),
                None,
            )
            setattr(obj, cache_attr, current)
        return getattr(obj, cache_attr)

    def get_holder(self, obj: Position) -> str | None:
        p = self._current_placement(obj)
        return str(p.employee_id) if p else None

    def get_holder_name(self, obj: Position) -> str | None:
        p = self._current_placement(obj)
        return p.employee.full_name if p else None

    def get_holder_employee_id(self, obj: Position) -> str | None:
        p = self._current_placement(obj)
        return p.employee.employee_id if p else None

    def get_holder_since(self, obj: Position):
        p = self._current_placement(obj)
        return p.effective_from if p else None

    def get_scheduled(self, obj: Position) -> dict | None:
        as_of = self._as_of()
        upcoming = sorted(
            (p for p in self._all_placements(obj) if p.effective_from > as_of),
            key=lambda p: p.effective_from,
        )
        if not upcoming:
            return None
        p = upcoming[0]
        return {
            'placement_id': str(p.pk),
            'employee_name': p.employee.full_name,
            'effective_from': p.effective_from,
        }

    def get_reports_to(self, obj: Position) -> dict | None:
        """Mirrors the mockup's own reportsToName() logic: a chief reports to
        the parent unit's chief; anyone else reports to their own unit's
        chief. Purely a computed display value — never a new source of truth
        for approval routing, which stays on User.reporting_manager.

        `chief_by_unit` (a {org_unit_id: Position} map, built once by
        PositionListCreateView.get() for however many rows are on the page)
        turns this into a dict lookup when present — without it, this ran a
        fresh, unprefetched query per position (org_unit.positions.filter(...))
        plus another for that target's own placements, invisible while the
        list endpoint's own pagination bug capped every page at 100 rows, but
        a real ~450-query N+1 once that cap was fixed and a full 223-position
        page is actually requested. PositionDetailView (a single object) still
        falls back to the query below, where the cost is negligible."""
        chief_by_unit = self.context.get('chief_by_unit')
        if chief_by_unit is not None:
            unit_id = obj.org_unit.parent_id if obj.is_chief else obj.org_unit_id
            target = chief_by_unit.get(unit_id) if unit_id else None
        elif obj.is_chief:
            target = (
                obj.org_unit.parent.positions.filter(is_chief=True).first()
                if obj.org_unit.parent else None
            )
        else:
            target = obj.org_unit.positions.filter(is_chief=True).first()
        if not target or target.pk == obj.pk:
            return None
        target_placement = self._current_placement(target)
        return {
            'position_id': str(target.pk),
            'title': target.title,
            'holder_name': target_placement.employee.full_name if target_placement else None,
        }

    def _unset_other_chiefs(self, org_unit, exclude_pk=None) -> None:
        qs = Position.objects.filter(org_unit=org_unit, is_chief=True)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        qs.update(is_chief=False)

    def create(self, validated_data):
        # Unset any existing chief in this org unit BEFORE inserting the new
        # row — position_one_chief_per_unit is a non-deferrable DB
        # constraint, so doing this the other way around (create, then
        # unset) would violate it the instant the new row is inserted while
        # the old one still has is_chief=True, before the unset ever runs.
        with transaction.atomic():
            if validated_data.get('is_chief'):
                self._unset_other_chiefs(validated_data['org_unit'])
            return super().create(validated_data)

    def update(self, instance, validated_data):
        with transaction.atomic():
            if validated_data.get('is_chief'):
                org_unit = validated_data.get('org_unit', instance.org_unit)
                self._unset_other_chiefs(org_unit, exclude_pk=instance.pk)
            return super().update(instance, validated_data)


class PlacementSerializer(serializers.ModelSerializer):
    employee_name        = serializers.CharField(source='employee.full_name', read_only=True)
    employee_employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    created_by_name       = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    status                = serializers.SerializerMethodField()

    class Meta:
        model  = Placement
        fields = (
            'id', 'position', 'employee', 'employee_name', 'employee_employee_id',
            'effective_from', 'effective_to', 'note', 'status',
            'created_at', 'created_by', 'created_by_name', 'updated_at',
        )
        read_only_fields = (
            'id', 'employee_name', 'employee_employee_id', 'status',
            'created_at', 'created_by', 'created_by_name', 'updated_at',
        )

    def get_status(self, obj: Placement) -> str:
        today = timezone.localdate()
        if obj.effective_from > today:
            return 'scheduled'
        if obj.effective_to is not None and obj.effective_to < today:
            return 'ended'
        return 'current'


# ─── Company ──────────────────────────────────────────────────────────────────

_GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z1-9]Z[A-Z\d]$')
_PAN_RE   = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')
_CIN_RE   = re.compile(r'^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$')
_TAN_RE   = re.compile(r'^[A-Z]{4}\d{5}[A-Z]$')
_PIN_RE   = re.compile(r'^\d{6}$')
_PHONE_RE = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')
_DIN_RE   = re.compile(r'^\d{8}$')
_UDYAM_RE = re.compile(r'^UDYAM-[A-Z]{2}-\d{2}-\d{7}$')
_ESIC_RE  = re.compile(r'^\d{17}$')
# LLPIN format per the approved design reference (india-company-profile-v2
# artifact's validateRegNo()) — 3 letters, an optional hyphen, 4 digits
# (e.g. AAB-1234).
_LLPIN_RE = re.compile(r'^[A-Z]{3}-?\d{4}$')
# EPFO establishment codes and state Professional Tax registration numbers
# have no single nationally-standardized format (EPFO varies by regional
# office prefix; Professional Tax is levied and numbered per-state) — unlike
# PAN/CIN/TAN/GSTIN/UDYAM/ESIC above, so this only guards against garbage
# input (blank-only, stray symbols) rather than asserting a specific shape.
_LOOSE_REGISTRATION_RE = re.compile(r'^[A-Z0-9/\-]{1,30}$')
_WEBSITE_RE = re.compile(
    r'^https?://[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(:\d{1,5})?(/\S*)?$',
)

# 2-digit GSTIN state code, keyed by the state names used elsewhere in this
# app — lets a GST registration row be cross-checked against its own
# `state` field without a government lookup.
GST_STATE_CODES = {
    'Jammu and Kashmir': '01', 'Himachal Pradesh': '02', 'Punjab': '03',
    'Chandigarh': '04', 'Uttarakhand': '05', 'Haryana': '06', 'Delhi': '07',
    'Rajasthan': '08', 'Uttar Pradesh': '09', 'Bihar': '10', 'Sikkim': '11',
    'Arunachal Pradesh': '12', 'Nagaland': '13', 'Manipur': '14', 'Mizoram': '15',
    'Tripura': '16', 'Meghalaya': '17', 'Assam': '18', 'West Bengal': '19',
    'Jharkhand': '20', 'Odisha': '21', 'Chhattisgarh': '22', 'Madhya Pradesh': '23',
    'Gujarat': '24', 'Dadra and Nagar Haveli and Daman and Diu': '26',
    'Maharashtra': '27', 'Karnataka': '29', 'Goa': '30', 'Lakshadweep': '31',
    'Kerala': '32', 'Tamil Nadu': '33', 'Puducherry': '34',
    'Andaman and Nicobar Islands': '35', 'Telangana': '36', 'Andhra Pradesh': '37',
    'Ladakh': '38',
}

_CIN_ENTITY_TYPES = {'private_limited', 'public_limited', 'opc', 'section8'}
# The single `cin` column is reused for whatever this entity type's actual
# registration number is called (see validate_cin below). Required/optional
# and format per entity type follow the approved design reference
# (india-company-profile-v2 artifact's TYPES_IN + applyEntityType()/
# validateRegNo()) exactly, not independent legal research: every entity
# type with a registration number at all (CIN types, LLP, Partnership,
# Trust/Society) requires it — only Proprietorship/HUF have none, and the
# frontend hides the field entirely for those two.
_LLPIN_ENTITY_TYPES = {'llp'}
_GENERIC_REG_ENTITY_TYPES = {'partnership', 'trust_society'}
_NO_REG_ENTITY_TYPES = {'sole_proprietorship', 'huf'}

# CIN's embedded "ownership class" (3 letters right after the year, e.g. the
# PTC in U74999MH2020PTC123456) reliably maps to entity type for these three
# — MCA introduced OPC as its own class specifically so it's unambiguous, and
# PTC/PLC are consistent across the ROC record. Section 8 is deliberately
# excluded: it's a *license* layered onto an otherwise-normal private/public
# company, so its CIN class is still PTC/PLC/OPC depending on the underlying
# company type, not a class of its own.
_CIN_CLASS_BY_ENTITY = {'private_limited': 'PTC', 'public_limited': 'PLC', 'opc': 'OPC'}
# Only a Public Limited company can legally be listed (CIN prefix "L") — a
# Private Limited/OPC/Section 8 company is structurally barred from public
# listing.
_CIN_CANNOT_BE_LISTED_ENTITY_TYPES = {'private_limited', 'opc', 'section8'}
# Indian postal PINs never start with 0 (the leading digit encodes one of 9
# postal regions, 1-9) — plain \d{6} happily accepts "000000".
_PIN_LEADING_ZERO_RE = re.compile(r'^0')
_MIN_INCORPORATION_DATE = date(1850, 1, 1)

# CIN's embedded state code (e.g. the MH in U74999MH2020PTC123456) is MCA's
# own 2-LETTER ROC abbreviation — a completely different coding system from
# GSTIN's 2-DIGIT numeric state code (GST_STATE_CODES above), not the same
# table reused. Chhattisgarh and Uttarakhand have seen more than one
# abbreviation in real CINs over the years (CG/CT and UT/UK respectively,
# from ROC jurisdiction renames) — using the current, more common variant
# for each; a false mismatch on an older CIN from one of those two states is
# a known residual gap, not a silent wrong assumption.
ROC_STATE_CODES = {
    'Andaman and Nicobar Islands': 'AN', 'Andhra Pradesh': 'AP', 'Arunachal Pradesh': 'AR',
    'Assam': 'AS', 'Bihar': 'BR', 'Chandigarh': 'CH', 'Chhattisgarh': 'CG',
    'Dadra and Nagar Haveli and Daman and Diu': 'DN', 'Delhi': 'DL', 'Goa': 'GA',
    'Gujarat': 'GJ', 'Haryana': 'HR', 'Himachal Pradesh': 'HP', 'Jammu and Kashmir': 'JK',
    'Jharkhand': 'JH', 'Karnataka': 'KA', 'Kerala': 'KL', 'Ladakh': 'LA',
    'Lakshadweep': 'LD', 'Madhya Pradesh': 'MP', 'Maharashtra': 'MH', 'Manipur': 'MN',
    'Meghalaya': 'ML', 'Mizoram': 'MZ', 'Nagaland': 'NL', 'Odisha': 'OR',
    'Puducherry': 'PY', 'Punjab': 'PB', 'Rajasthan': 'RJ', 'Sikkim': 'SK',
    'Tamil Nadu': 'TN', 'Telangana': 'TG', 'Tripura': 'TR', 'Uttar Pradesh': 'UP',
    'Uttarakhand': 'UT', 'West Bengal': 'WB',
}


# GSTIN checksum — the 15th character is a check digit over the first 14, a
# Luhn-like algorithm in base 36 (0-9 then A-Z). Publicly documented GSTN
# spec; verified against known-valid GSTINs (including the exact one used in
# this defect report) before being relied on — see the identical
# implementation and its test in frontend/_data.ts's gstinCheckDigit().
_GSTIN_CHARSET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _gstin_check_digit(first14: str) -> str:
    length = len(_GSTIN_CHARSET)
    factor = 2
    total = 0
    for ch in reversed(first14):
        d = factor * _GSTIN_CHARSET.index(ch)
        d = d // length + d % length
        total += d
        factor = 1 if factor == 2 else 2
    return _GSTIN_CHARSET[(length - (total % length)) % length]


def _gstin_pan_mismatch_error(gstin: str, pan: str) -> str | None:
    # A GSTIN's characters 3-12 are always the PAN it was issued against —
    # this is free, offline arithmetic (no government lookup needed) that
    # still catches the common real mistake of a mistyped GSTIN or a
    # leftover GSTIN from a different PAN, without pretending to verify
    # the GSTIN is actually registered with the government.
    if gstin and pan and gstin[2:12] != pan:
        return f"This GSTIN belongs to PAN {gstin[2:12]}, not the company PAN ({pan})."
    return None


def _iec_pan_mismatch_error(iec: str, pan: str) -> str | None:
    # Since 2018, DGFT issues the Import Export Code as the entity's PAN
    # itself (no separate IEC series) — same free cross-check idea as
    # GSTIN-vs-PAN above, catching a stale/mistyped IEC from before a PAN
    # change without a government lookup.
    if iec and pan and iec != pan:
        return f"IEC is PAN-based since 2018 and should match the company PAN ({pan})."
    return None


class CompanySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField(read_only=True)
    # Write-only, never persisted (popped in validate()) — when true, skips
    # the cross-field "required for this jurisdiction/entity type" checks
    # below so an in-progress profile can be saved without being complete.
    # Field-level validators (company_name/address/city) also read it via
    # self.initial_data, since is_draft itself isn't available yet when
    # those individual field validators run.
    is_draft = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model  = Company
        fields = [
            'id', 'jurisdiction', 'entity_type', 'company_name', 'trade_name',
            'logo', 'logo_url', 'date_of_incorporation', 'is_listed', 'holding_company_info',
            'cin', 'roc_jurisdiction', 'pan', 'tan',
            'country_of_registration', 'registration_number', 'ein',
            'udyam_msme', 'msme_class', 'iec', 'epfo_code', 'esic_code', 'professional_tax_reg',
            'signatory_full_name', 'signatory_designation', 'signatory_din_pan',
            'signatory_email', 'signatory_appears_on_invoices',
            'bank_account_holder', 'bank_account_number', 'bank_ifsc', 'bank_account_type',
            'industry', 'nic_code', 'nature_of_business',
            'address', 'city', 'state', 'pin_code',
            'communication_address_same_as_registered', 'communication_address',
            'communication_city', 'communication_state', 'communication_pin_code',
            'default_currency', 'date_format', 'timezone', 'financial_year_start_month',
            'primary_email', 'website', 'official_phone', 'portal_url', 'updated_at',
            'is_draft',
        ]
        read_only_fields = ['id', 'updated_at', 'logo_url']
        extra_kwargs     = {
            'logo': {'required': False, 'allow_null': True},
            # DRF's own CharField(allow_blank=False) — the default for a
            # non-blank=True model field — rejects an empty string before
            # validate_company_name/address/city ever runs, which is what
            # actually enforces "required unless is_draft". allow_blank=True
            # here just moves the blank-check into those methods instead.
            'company_name': {'allow_blank': True},
            'address':      {'allow_blank': True},
            'city':         {'allow_blank': True},
        }

    def _is_draft_request(self) -> bool:
        raw = self.initial_data.get('is_draft', False) if hasattr(self, 'initial_data') else False
        return str(raw).strip().lower() in ('true', '1', 'yes')

    def get_logo_url(self, obj: Company) -> str | None:
        if not obj.logo:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    # PAN/bank details/signatory ID are the same PII tier as an employee's
    # own PAN/bank details (encrypted at rest, see EncryptedCharField on the
    # model) — CompanyRetrieveUpdateView.get() is reachable by any
    # authenticated user (my-payslip, approval modals, and several other
    # pages all legitimately need the non-sensitive fields — name, logo,
    # address, CIN — so the endpoint itself can't just be locked down to
    # settings.edit without breaking those). Strip the sensitive fields here
    # instead, for anyone who can't also edit company settings.
    _SENSITIVE_FIELDS = ('pan', 'bank_account_number', 'bank_ifsc', 'signatory_din_pan')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not (user and _has_perm(user, 'settings.edit')):
            for field in self._SENSITIVE_FIELDS:
                data.pop(field, None)
        return data

    def validate_company_name(self, value: str) -> str:
        value = value.strip()
        if not value and not self._is_draft_request():
            raise serializers.ValidationError('Company name is required.')
        if len(value) > 255:
            raise serializers.ValidationError('Company name must be 255 characters or fewer.')
        return value

    def validate_address(self, value: str) -> str:
        if value is not None:
            value = value.strip()
        if not value and not self._is_draft_request():
            raise serializers.ValidationError('Company address is required.')
        if value and len(value) > 500:
            raise serializers.ValidationError('Address must be 500 characters or fewer.')
        return value

    def validate_city(self, value: str) -> str:
        if value is not None:
            value = value.strip()
        if not value and not self._is_draft_request():
            raise serializers.ValidationError('City is required.')
        if value and len(value) > 100:
            raise serializers.ValidationError('City must be 100 characters or fewer.')
        return value

    def validate_state(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if len(v) > 100:
            raise serializers.ValidationError('State must be 100 characters or fewer.')
        return v

    def validate_cin(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        entity_type = (self.initial_data.get('entity_type') if hasattr(self, 'initial_data') else None) \
            or getattr(self.instance, 'entity_type', '')
        if entity_type in _CIN_ENTITY_TYPES:
            if not _CIN_RE.match(v):
                raise serializers.ValidationError('Enter a valid CIN (e.g. U74999MH2020PTC123456).')
        elif entity_type in _NO_REG_ENTITY_TYPES:
            pass  # No such number for these entity types — nothing to validate.
        elif entity_type in _LLPIN_ENTITY_TYPES:
            if not _LLPIN_RE.match(v):
                raise serializers.ValidationError('LLPIN is 3 letters + 4 digits (e.g. AAB-1234).')
        else:
            # Partnership/Trust — the artifact's own validateRegNo() applies
            # no format check at all here beyond a minimum length, since a
            # state filing number has no single national shape.
            if len(v) < 3:
                raise serializers.ValidationError('Enter the registration number from your certificate.')
        return v

    def validate_pan(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _PAN_RE.match(v):
            raise serializers.ValidationError('Enter a valid 10-character PAN (e.g. AAAAA0000A).')
        return v

    def validate_tan(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _TAN_RE.match(v):
            raise serializers.ValidationError('Enter a valid 10-character TAN (e.g. PNEA12345B).')
        return v

    def validate_pin_code(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if not _PIN_RE.match(v) or _PIN_LEADING_ZERO_RE.match(v):
            raise serializers.ValidationError("Enter a valid 6-digit Indian PIN code (can't start with 0).")
        return v

    def validate_communication_pin_code(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if not _PIN_RE.match(v) or _PIN_LEADING_ZERO_RE.match(v):
            raise serializers.ValidationError("Enter a valid 6-digit Indian PIN code (can't start with 0).")
        return v

    def validate_date_of_incorporation(self, value):
        if not value:
            return value
        if value > timezone.localdate():
            raise serializers.ValidationError("Date of Incorporation can't be in the future.")
        if value < _MIN_INCORPORATION_DATE:
            raise serializers.ValidationError('Enter a realistic Date of Incorporation.')
        return value

    def validate_udyam_msme(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _UDYAM_RE.match(v):
            raise serializers.ValidationError('Enter a valid Udyam number (e.g. UDYAM-TS-00-0000000).')
        return v

    def validate_iec(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _PAN_RE.match(v):
            raise serializers.ValidationError('IEC is PAN-based since 2018 — enter a valid 10-character PAN-format code.')
        return v

    def validate_epfo_code(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _LOOSE_REGISTRATION_RE.match(v):
            raise serializers.ValidationError('EPFO code must be 30 characters or fewer, letters/digits/slashes/hyphens only.')
        return v

    def validate_esic_code(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if not _ESIC_RE.match(v):
            raise serializers.ValidationError('ESIC code must be exactly 17 digits.')
        return v

    def validate_professional_tax_reg(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not _LOOSE_REGISTRATION_RE.match(v):
            raise serializers.ValidationError('Professional Tax registration must be 30 characters or fewer, letters/digits/slashes/hyphens only.')
        return v

    def validate_signatory_din_pan(self, value: str) -> str:
        if not value:
            return value
        v = value.strip().upper()
        if not (_DIN_RE.match(v) or _PAN_RE.match(v)):
            raise serializers.ValidationError('Enter a valid DIN (8 digits) or PAN (10 characters) — the signatory is not always a director.')
        return v

    def validate_website(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        # A bare domain or "www.example.com" has no scheme at all — rather
        # than reject it, assume https:// like a browser address bar does.
        # _WEBSITE_RE below still shape-checks the whole string afterward
        # (not just the prefix), so this doesn't loosen what's accepted.
        if not re.match(r'^https?://', v, re.IGNORECASE):
            v = f'https://{v}'
        # Shape-checks the whole string, not just its prefix — a bare
        # startswith("http") check still lets a scheme-confusion payload
        # like "http://x/\njavascript:alert(1)" through if this value is
        # ever rendered as a raw href.
        if not _WEBSITE_RE.match(v):
            raise serializers.ValidationError('Enter a valid website, e.g. www.example.com.')
        return v

    def validate_official_phone(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if v and not _PHONE_RE.match(v):
            raise serializers.ValidationError('Enter a valid phone number.')
        return v

    def validate_primary_email(self, value: str) -> str:
        return value.strip() if value else value

    def validate_signatory_email(self, value: str) -> str:
        return value.strip() if value else value

    def validate_portal_url(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if v and not v.startswith(('http://', 'https://')):
            raise serializers.ValidationError('Portal URL must start with http:// or https://.')
        return v

    def validate_logo(self, value):
        if value is None:
            return value
        if hasattr(value, 'size') and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Logo must be under 5 MB.')
        allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/svg+xml'}
        if hasattr(value, 'content_type') and value.content_type not in allowed:
            raise serializers.ValidationError('Only JPEG, PNG, WebP, or SVG files are allowed.')
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        return value

    def validate(self, attrs):
        # Never persisted — read above in the field-level validators via
        # self.initial_data, popped here so it never reaches .save().
        is_draft = attrs.pop('is_draft', False)

        def _val(field):
            return attrs.get(field, getattr(self.instance, field, ''))

        errors: dict[str, str] = {}

        comm_same = attrs.get(
            'communication_address_same_as_registered',
            getattr(self.instance, 'communication_address_same_as_registered', True),
        )
        if not comm_same and not is_draft:
            if not _val('communication_address'):
                errors['communication_address'] = 'Communication address is required when it differs from the registered office.'
            if not _val('communication_city'):
                errors['communication_city'] = 'Communication city is required when it differs from the registered office.'

        if not is_draft:
            jurisdiction = _val('jurisdiction') or Company.JURISDICTION_INDIA
            entity_type  = _val('entity_type')

            if jurisdiction == Company.JURISDICTION_INDIA:
                if not _val('pan'):
                    errors['pan'] = 'PAN is required for an Indian entity.'
                # TAN is intentionally NOT required here, for any entity
                # type — matches the approved design reference, which marks
                # it "(for TDS)"/optional throughout and never makes it
                # required per entity type. Format is still checked below
                # (validate_tan) whenever a value is actually entered.
                if entity_type in _CIN_ENTITY_TYPES and not _val('cin'):
                    errors['cin'] = 'CIN is required for this entity type.'
                elif entity_type in _LLPIN_ENTITY_TYPES and not _val('cin'):
                    errors['cin'] = 'LLPIN is required for an LLP.'
                elif entity_type in _GENERIC_REG_ENTITY_TYPES and not _val('cin'):
                    errors['cin'] = 'Registration number is required for this entity type.'
                elif entity_type in _CIN_ENTITY_TYPES and _val('cin') and 'cin' not in errors:
                    # Cross-checks against CIN's own embedded data — same
                    # rules as the client-side hint in _data.ts's
                    # validateCompany(), re-asserted here since the client is
                    # never the authority on data integrity. Only meaningful
                    # once the CIN has already passed validate_cin's format
                    # check above (a malformed CIN reaching here would mean
                    # validate_cin already raised before this method ran).
                    cin = _val('cin').upper()
                    expected_class = _CIN_CLASS_BY_ENTITY.get(entity_type)
                    cin_class = cin[12:15]
                    cin_state_code = cin[6:8]
                    cin_year = cin[8:12]
                    doi = _val('date_of_incorporation')
                    state = _val('state')
                    if expected_class and cin_class != expected_class:
                        errors['cin'] = f"This CIN's company class ({cin_class}) doesn't match the selected entity type (expected {expected_class})."
                    elif cin[0] == 'L' and entity_type in _CIN_CANNOT_BE_LISTED_ENTITY_TYPES:
                        errors['cin'] = "This CIN's listing prefix (L) marks it as a listed company, which isn't possible for this entity type."
                    elif state and ROC_STATE_CODES.get(state) and cin_state_code != ROC_STATE_CODES[state]:
                        errors['cin'] = f"This CIN's state code ({cin_state_code}) doesn't match the registered office state ({state})."
                    elif doi and cin_year != str(doi.year):
                        errors['cin'] = f"This CIN's registration year ({cin_year}) doesn't match the Date of Incorporation ({doi.year})."
                iec_mismatch = _iec_pan_mismatch_error(_val('iec'), _val('pan'))
                if iec_mismatch:
                    errors['iec'] = iec_mismatch
            else:
                if not _val('country_of_registration'):
                    errors['country_of_registration'] = 'Country of registration is required for a foreign entity.'
                if not _val('registration_number'):
                    errors['registration_number'] = 'Registration number is required for a foreign entity.'
                # EIN is a US IRS-issued tax ID — only meaningful (and only
                # required) for entities registered in the US, same idea as
                # CIN only applying to certain India entity types above.
                if _val('country_of_registration') == 'US' and not _val('ein'):
                    errors['ein'] = 'EIN is required for a US entity.'

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CompanyGSTRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompanyGSTRegistration
        fields = ['id', 'company', 'gstin', 'state', 'registration_type', 'place_of_business', 'created_at', 'updated_at']
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

    def validate_gstin(self, value: str) -> str:
        v = value.strip().upper()
        if not _GSTIN_RE.match(v):
            raise serializers.ValidationError('Enter a valid 15-character GSTIN (e.g. 22AAAAA0000A1Z5).')
        if _gstin_check_digit(v[:14]) != v[14]:
            raise serializers.ValidationError('Invalid GSTIN checksum — check for a typo.')
        return v

    def validate_state(self, value: str) -> str:
        v = value.strip() if value else value
        if not v:
            raise serializers.ValidationError('State is required.')
        return v

    def validate(self, attrs):
        gstin   = attrs.get('gstin', getattr(self.instance, 'gstin', None))
        state   = attrs.get('state', getattr(self.instance, 'state', None))
        company = self.context.get('company') or getattr(self.instance, 'company', None)
        errors: dict[str, str] = {}

        if gstin and company and company.pan:
            mismatch = _gstin_pan_mismatch_error(gstin, company.pan)
            if mismatch:
                errors['gstin'] = mismatch

        if gstin and state:
            expected_code = GST_STATE_CODES.get(state)
            if expected_code and gstin[:2] != expected_code and 'gstin' not in errors:
                errors['gstin'] = f"This GSTIN's state code ({gstin[:2]}) doesn't match the selected state ({state})."

        # "One GSTIN per state" is stated in the UI's own subtitle but was
        # never actually enforced — only (company, gstin) had a uniqueness
        # constraint, which doesn't catch a second, different-but-valid
        # GSTIN entered for a state that already has one. Checked here
        # rather than as a DB constraint, since a migration adding one now
        # could fail outright if duplicate state rows already exist in
        # production and there's no way to inspect that data directly.
        if state and company and 'state' not in errors:
            dupe_qs = CompanyGSTRegistration.objects.filter(company=company, state=state)
            if self.instance:
                dupe_qs = dupe_qs.exclude(pk=self.instance.pk)
            if dupe_qs.exists():
                errors['state'] = f'A GST registration already exists for {state}.'

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CompanyDirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompanyDirector
        fields = ['id', 'company', 'din', 'name', 'designation', 'created_at', 'updated_at']
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

    def validate_din(self, value: str) -> str:
        v = value.strip() if value else value
        if not v:
            raise serializers.ValidationError('This field is required.')
        # This column is reused for whatever ID this entity type's people
        # actually carry — same reuse pattern as CompanySerializer.cin. The
        # company isn't this serializer's instance (a director is), so the
        # create path passes it via context; the update path already has it
        # through the select_related instance.
        company = self.context.get('company') or getattr(self.instance, 'company', None)
        entity_type = getattr(company, 'entity_type', '') if company else ''
        if entity_type in _CIN_ENTITY_TYPES or entity_type in _LLPIN_ENTITY_TYPES:
            if not _DIN_RE.match(v):
                raise serializers.ValidationError('DIN must be exactly 8 digits.')
        elif entity_type in _GENERIC_REG_ENTITY_TYPES:
            v = v.upper()
            if not _PAN_RE.match(v):
                raise serializers.ValidationError('Enter a valid PAN (e.g. AAAAA0000A).')
        else:
            # Foreign entity types (and any unset entity_type) have no single
            # standard personal-ID format — just guard against garbage input.
            if len(v) < 2:
                raise serializers.ValidationError('Enter a valid identifier.')
        return v

    def validate_name(self, value: str) -> str:
        v = value.strip() if value else value
        if not v:
            raise serializers.ValidationError('Director name is required.')
        return v

    def validate_designation(self, value: str) -> str:
        v = value.strip() if value else value
        if not v:
            raise serializers.ValidationError('Designation is required.')
        return v


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLogSerializer(serializers.ModelSerializer):
    actor_name  = serializers.SerializerMethodField()
    actor_email = serializers.SerializerMethodField()
    actor_role  = serializers.SerializerMethodField()

    class Meta:
        model  = AuditLog
        fields = [
            'id', 'actor_name', 'actor_email', 'actor_role',
            'action', 'module', 'object_id', 'ip_address', 'created_at',
        ]

    def get_actor_name(self, obj: AuditLog) -> str:
        return obj.user.full_name if obj.user_id else 'System'

    def get_actor_email(self, obj: AuditLog) -> str | None:
        return obj.user.email if obj.user_id else None

    def get_actor_role(self, obj: AuditLog) -> str | None:
        if obj.user_id and obj.user.role_id:
            return obj.user.role.display_name
        return None


# ─── Document Center ──────────────────────────────────────────────────────────

class DocumentSerializer(serializers.ModelSerializer):
    file_url          = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    category_display  = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_name  = serializers.SerializerMethodField()
    branch_name       = serializers.SerializerMethodField()

    class Meta:
        model  = Document
        fields = (
            'id', 'title', 'description',
            'category', 'category_display',
            'version', 'effective_date',
            'file', 'file_url', 'file_name', 'file_type',
            'file_size', 'file_size_display',
            'branch', 'branch_name',
            'uploaded_by_name', 'uploaded_at', 'updated_at', 'is_active',
        )
        read_only_fields = (
            'id', 'file_url', 'file_name', 'file_type', 'file_size',
            'file_size_display', 'category_display',
            'uploaded_by_name', 'branch_name', 'uploaded_at', 'updated_at',
            'is_active',   # managed by the view — never set by the client
        )
        extra_kwargs = {'file': {'required': True}}

    def get_file_url(self, obj: Document) -> str:
        if not obj.file or not obj.file.name:
            return ''
        # Issue a short-lived signed token so the frontend can fetch the file
        # through Django's proxy endpoint without needing an auth header.
        token = signing.dumps({'id': obj.pk}, salt='doc-dl')
        path = f'/api/documents/{obj.pk}/?t={token}'
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(path)
        return path

    def get_file_size_display(self, obj: Document) -> str:
        size = obj.file_size
        if size < 1024:
            return f'{size} B'
        if size < 1024 * 1024:
            return f'{size / 1024:.0f} KB'
        return f'{size / (1024 * 1024):.1f} MB'

    def get_branch_name(self, obj: Document):
        return obj.branch.branch_name if obj.branch_id else None

    def get_uploaded_by_name(self, obj: Document) -> str:
        return obj.uploaded_by.full_name if obj.uploaded_by else '—'

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title must not be blank.')
        if len(value) > 200:
            raise serializers.ValidationError('Title must be under 200 characters.')
        # Uniqueness check — instance is set on update (PATCH), None on create (POST)
        qs = Document.objects.filter(title__iexact=value, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A document with this title already exists.')
        return value

    def validate_description(self, value: str) -> str:
        value = value.strip() if value else ''
        if len(value) > 1000:
            raise serializers.ValidationError('Description must be under 1,000 characters.')
        return value

    def validate_category(self, value: str) -> str:
        valid = {c for c, _ in Document.CATEGORY_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid category. Choose from: {", ".join(sorted(valid))}.'
            )
        return value

    def validate_version(self, value: str) -> str:
        value = value.strip() if value else ''
        if len(value) > 20:
            raise serializers.ValidationError('Version must be under 20 characters.')
        return value

    def validate_file(self, value) -> object:
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.size == 0:
            raise serializers.ValidationError('Uploaded file is empty.')
        if value.content_type not in Document.ALLOWED_MIME_TYPES:
            allowed = ', '.join(sorted(Document.MIME_TO_TYPE.values()))
            raise serializers.ValidationError(
                f'Unsupported file type "{value.content_type}". Allowed: {allowed}.'
            )
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        if value.size > Document.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size {value.size / (1024 * 1024):.1f} MB exceeds the 25 MB limit.'
            )
        # Strip any path components a client might inject (e.g. "../../etc/passwd")
        value.name = os.path.basename(value.name).strip()
        if not value.name:
            raise serializers.ValidationError('File name is invalid after sanitization.')
        return value

    def validate(self, attrs):
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        if branch is not None:
            # Verify the branch is active (has employees_count or at least exists & is not deleted)
            from apps.branch.models import Branch
            if not Branch.objects.filter(pk=branch.pk).exists():
                raise serializers.ValidationError({'branch': 'Selected branch does not exist.'})
        return attrs


# ─── Employee Code Settings ───────────────────────────────────────────────────

class EmployeeCodeSettingsSerializer(serializers.ModelSerializer):
    format_description = serializers.SerializerMethodField()

    class Meta:
        model  = EmployeeCodeSettings
        fields = ['prefix', 'padding', 'next_sequence', 'format_description']
        read_only_fields = ['format_description']

    def get_format_description(self, obj) -> str:
        seq = str(obj.next_sequence).zfill(obj.padding)
        return f'{obj.prefix}{seq}  (prefix + {obj.padding}-digit sequence, next = {obj.next_sequence})'

    def validate_prefix(self, value):
        value = value.strip().upper()
        # Letters/digits/hyphen/underscore — covers real-world employee ID
        # prefixes like "HR-", "IT_2024", "EMP01", not just plain letters.
        # Still excludes whitespace/other symbols since this value is
        # concatenated straight into employee_id (portal usernames, emails,
        # DB lookups) with no further sanitization downstream.
        if not re.fullmatch(r'[A-Z0-9_-]+', value):
            raise serializers.ValidationError(
                'Prefix may contain only letters, numbers, hyphens, and underscores.'
            )
        return value

    def validate_padding(self, value):
        if not 3 <= value <= 8:
            raise serializers.ValidationError('Padding must be between 3 and 8.')
        return value

    def validate_next_sequence(self, value):
        if value < 1:
            raise serializers.ValidationError('Starting number must be at least 1.')
        return value


# ─── Employee Profile (onboarding wizard) ─────────────────────────────────────

_IFSC_RE  = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
_PHONE_RE_PROFILE = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')
# Indian PIN codes are always 6 digits and never start with 0 (the leading
# digit encodes one of 9 postal regions, 1-9) — same rule the Company address
# form's isValidPin() enforces (frontend/app/dashboard/settings/company/_data.ts).
_PIN_CODE_RE = re.compile(r'^[1-9]\d{5}$')


class EmployeeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EmployeeProfile
        fields = [
            'date_of_birth', 'gender', 'marital_status', 'father_name',
            'blood_group', 'current_address', 'current_address_line2',
            'current_village', 'current_district', 'current_state', 'current_pin_code',
            'permanent_address', 'permanent_address_line2',
            'permanent_village', 'permanent_district', 'permanent_state', 'permanent_pin_code',
            'permanent_same_as_current',
            'highest_qualification', 'institution', 'year_of_passing', 'specialization',
            'total_experience_years', 'previous_employer', 'previous_designation', 'leaving_reason',
            'account_number', 'ifsc_code', 'bank_name', 'bank_branch_name',
            'account_holder_name', 'account_type',
            'bank_change_status', 'bank_change_requested_at',
            'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
            'uan_number', 'esi_number', 'name_as_per_aadhar', 'pan_number',
            'aadhaar_number', 'pf_covered', 'pf_number', 'esi_covered',
            'is_disabled', 'disability_type', 'disability_percentage', 'disability_certificate_number',
            'is_international_worker', 'international_worker_country', 'passport_number', 'passport_expiry',
            'custom_field_values',
            'updated_at',
        ]
        read_only_fields = ('updated_at', 'bank_change_status', 'bank_change_requested_at')

    def validate_pan_number(self, value: str) -> str:
        if not value:
            return value
        from apps.accounts.models import find_conflicting_pan_profile, normalize_and_validate_pan
        try:
            value = normalize_and_validate_pan(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        conflict = find_conflicting_pan_profile(
            value, exclude_profile_pk=self.instance.pk if self.instance else None,
        )
        if conflict:
            raise serializers.ValidationError(
                f'This PAN is already registered to {conflict.user.full_name} '
                f'({conflict.user.employee_id or conflict.user.email}).'
            )
        return value

    def validate_date_of_birth(self, value):
        if value is None:
            return value
        from datetime import date as _date
        today = _date.today()
        if value >= today:
            raise serializers.ValidationError('Date of birth must be in the past.')
        age = (today - value).days // 365
        if age < 18:
            raise serializers.ValidationError('Employee must be at least 18 years old.')
        if age > 80:
            raise serializers.ValidationError('Please enter a valid date of birth.')
        return value

    def validate_year_of_passing(self, value):
        if value is not None and not (1950 <= value <= 2099):
            raise serializers.ValidationError('Year of passing must be between 1950 and 2099.')
        return value

    def validate_ifsc_code(self, value: str) -> str:
        if not value:
            return value
        value = value.strip().upper()
        if not _IFSC_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid IFSC code (e.g. SBIN0001234) — '
                '4 letters, digit 0, then 6 alphanumeric characters.'
            )
        return value

    def validate_account_number(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError('Account number must contain digits only.')
        if not (9 <= len(value) <= 18):
            raise serializers.ValidationError('Account number must be between 9 and 18 digits.')
        return value

    def validate_account_holder_name(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Account holder name must not be blank.')
        if len(value) > 150:
            raise serializers.ValidationError('Account holder name must be 150 characters or fewer.')
        return value

    def validate_emergency_name(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Emergency contact name must not be blank.')
        if len(value) > 150:
            raise serializers.ValidationError('Emergency contact name must be 150 characters or fewer.')
        return value

    def validate_emergency_phone(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PHONE_RE_PROFILE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
            )
        return value

    def validate_total_experience_years(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Total experience years cannot be negative.')
        return value

    # ── Step 0 — Personal ─────────────────────────────────────────────────────

    def validate_father_name(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Father\'s name must not be blank.')
        return value

    def validate_current_address(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Current address must not be blank.')
        if len(value) > 1000:
            raise serializers.ValidationError('Current address must be 1000 characters or fewer.')
        return value

    def validate_permanent_address(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if len(value) > 1000:
            raise serializers.ValidationError('Permanent address must be 1000 characters or fewer.')
        return value

    def _validate_pin_code_value(self, value: str, field_label: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PIN_CODE_RE.match(value):
            raise serializers.ValidationError(f'Enter a valid 6-digit {field_label} (cannot start with 0).')
        return value

    def validate_current_pin_code(self, value: str) -> str:
        return self._validate_pin_code_value(value, 'PIN code')

    def validate_permanent_pin_code(self, value: str) -> str:
        return self._validate_pin_code_value(value, 'PIN code')

    # ── Step 1 — Education & Experience ──────────────────────────────────────

    def validate_highest_qualification(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Highest qualification must not be blank.')
        return value

    def validate_institution(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Institution name must not be blank.')
        return value

    def validate_specialization(self, value: str) -> str:
        if not value:
            return value
        return value.strip()

    def validate_previous_employer(self, value: str) -> str:
        if not value:
            return value
        return value.strip()

    def validate_previous_designation(self, value: str) -> str:
        if not value:
            return value
        return value.strip()

    def validate_leaving_reason(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if len(value) > 2000:
            raise serializers.ValidationError('Reason for leaving must be 2000 characters or fewer.')
        return value

    # ── Step 2 — Bank Details ─────────────────────────────────────────────────

    def validate_bank_name(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Bank name must not be blank.')
        return value

    def validate_bank_branch_name(self, value: str) -> str:
        if not value:
            return value
        return value.strip()

    # ── Step 0 — Choice fields ────────────────────────────────────────────────

    def validate_gender(self, value: str) -> str:
        if not value:
            return value
        valid = {c[0] for c in self.Meta.model.GENDER_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid gender. Choose from: {", ".join(sorted(valid))}.'
            )
        return value

    def validate_marital_status(self, value: str) -> str:
        if not value:
            return value
        valid = {c[0] for c in self.Meta.model.MARITAL_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid marital status. Choose from: {", ".join(sorted(valid))}.'
            )
        return value

    def validate_blood_group(self, value: str) -> str:
        if not value:
            return value
        valid = {c[0] for c in self.Meta.model.BLOOD_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid blood group. Choose from: {", ".join(sorted(valid))}.'
            )
        return value

    # ── Step 2 — Account type ─────────────────────────────────────────────────

    def validate_account_type(self, value: str) -> str:
        if not value:
            return value
        valid = {c[0] for c in self.Meta.model.ACCOUNT_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(
                f'Invalid account type. Choose from: {", ".join(sorted(valid))}.'
            )
        return value

    # ── Step 3 — Emergency Contact ────────────────────────────────────────────

    def validate_emergency_relationship(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Relationship must not be blank.')
        if len(value) > 50:
            raise serializers.ValidationError('Relationship must be 50 characters or fewer.')
        return value

    def validate_emergency_email(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        from django.core.validators import validate_email as _validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            _validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError('Enter a valid email address.')
        return value


# ─── Employee Document ────────────────────────────────────────────────────────

class EmployeeDocumentSerializer(serializers.ModelSerializer):
    # document_type no longer has a `choices=` enum (see DocumentTypeConfig),
    # so there's no auto-generated get_document_type_display() to source from
    # any more — resolved via the same config cache the settings/upload views
    # already read.
    document_type_display = serializers.SerializerMethodField()
    # file_url points to our backend proxy which signs the storage request —
    # the raw storage URL requires authentication and cannot be opened directly.
    file_url = serializers.SerializerMethodField()

    class Meta:
        model  = EmployeeDocument
        fields = [
            'id', 'document_type', 'document_type_display',
            'file', 'file_url', 'file_name', 'file_size', 'uploaded_at',
        ]
        read_only_fields = ('id', 'document_type_display', 'file_url', 'file_name', 'file_size', 'uploaded_at')
        extra_kwargs = {'file': {'write_only': True}}

    def get_document_type_display(self, obj):
        from core.cache_service import DocumentTypeConfigCacheService
        return DocumentTypeConfigCacheService.label_for(obj.document_type)

    def get_file_url(self, obj):
        # HR approval context: return a signed storage URL so admins can
        # open the file directly without routing through the employee proxy.
        if self.context.get('use_direct_url') and obj.file:
            try:
                return obj.file.url
            except Exception:
                pass

        # Default: backend proxy URL (signs the request server-side so the
        # browser never hits storage directly — required for employee flow).
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/onboarding/documents/{obj.pk}/')

    def validate_file(self, value):
        import os
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.size == 0:
            raise serializers.ValidationError('Uploaded file is empty.')
        if value.content_type not in EmployeeDocument.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG files are allowed.')
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        if value.size > EmployeeDocument.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size {value.size / (1024 * 1024):.1f} MB exceeds the 5 MB limit.'
            )
        value.name = os.path.basename(value.name).strip()
        return value


class HireActionDocumentSerializer(serializers.ModelSerializer):
    """Mirrors EmployeeDocumentSerializer above — same validation, same
    ALLOWED_MIME_TYPES/MAX_FILE_SIZE (borrowed from EmployeeDocument rather
    than duplicated, since a hire-action document becomes a real
    EmployeeDocument at Stage 2 and must pass the exact same rules either
    way)."""
    document_type_display = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model  = HireActionDocument
        fields = [
            'id', 'document_type', 'document_type_display', 'entry_ref',
            'file', 'file_url', 'file_name', 'file_size', 'uploaded_at',
        ]
        read_only_fields = ('id', 'document_type_display', 'file_url', 'file_name', 'file_size', 'uploaded_at')
        extra_kwargs = {'file': {'write_only': True}, 'entry_ref': {'required': False, 'allow_blank': True}}

    def get_document_type_display(self, obj):
        from core.cache_service import DocumentTypeConfigCacheService
        return DocumentTypeConfigCacheService.label_for(obj.document_type)

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/hire-actions/{obj.hire_action_id}/documents/{obj.pk}/')

    # A genuine ID-card photo or scan is never this small — catches a blank
    # page, a 1x1 placeholder image, or a truncated upload that technically
    # passes the format check above but clearly isn't a real document.
    MIN_FILE_SIZE = 2 * 1024

    def validate_file(self, value):
        import os
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.size == 0:
            raise serializers.ValidationError('Uploaded file is empty.')
        if value.content_type not in EmployeeDocument.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG files are allowed.')
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        if value.size > EmployeeDocument.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size {value.size / (1024 * 1024):.1f} MB exceeds the 5 MB limit.'
            )
        if value.size < self.MIN_FILE_SIZE:
            raise serializers.ValidationError(
                'This file is too small to be a real document scan or photo. Please check the file and try again.'
            )
        value.name = os.path.basename(value.name).strip()
        return value


# ─── Custom Field File Value ───────────────────────────────────────────────────

class CustomFieldFileValueSerializer(serializers.ModelSerializer):
    # Same signed-proxy reasoning as EmployeeDocumentSerializer.file_url above —
    # the raw storage URL requires authentication the browser doesn't have.
    file_url = serializers.SerializerMethodField()

    class Meta:
        model  = CustomFieldFileValue
        fields = ['id', 'field_key', 'file', 'file_url', 'file_name', 'file_size', 'uploaded_at']
        read_only_fields = ('id', 'file_url', 'file_name', 'file_size', 'uploaded_at')
        extra_kwargs = {'file': {'write_only': True}}

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/onboarding/custom-file-fields/{obj.pk}/')

    def validate_file(self, value):
        # Identical validation to EmployeeDocumentSerializer.validate_file —
        # ad-hoc custom-field uploads get the same whitelist/size treatment as
        # real documents, reusing EmployeeDocument's constants rather than
        # redeclaring them.
        import os
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.size == 0:
            raise serializers.ValidationError('Uploaded file is empty.')
        if value.content_type not in EmployeeDocument.ALLOWED_MIME_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG files are allowed.')
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        if value.size > EmployeeDocument.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size {value.size / (1024 * 1024):.1f} MB exceeds the 5 MB limit.'
            )
        value.name = os.path.basename(value.name).strip()
        return value


# ─── Onboarding Field Configuration ────────────────────────────────────────────

class OnboardingFieldConfigSerializer(serializers.ModelSerializer):
    """Read-only — used for the settings list and the wizard-facing config."""
    class Meta:
        model  = OnboardingFieldConfig
        fields = [
            'field_key', 'label', 'field_type', 'options', 'allow_multiple', 'step', 'order',
            'visible', 'required', 'is_custom', 'is_locked', 'updated_at',
        ]
        read_only_fields = fields


class EducationExperienceFieldConfigSerializer(serializers.ModelSerializer):
    """visible/required are the only writable fields — see
    EducationExperienceFieldConfig's own docstring for why this is a fixed
    set of rows (no add/remove, unlike OnboardingFieldConfig)."""
    class Meta:
        model  = EducationExperienceFieldConfig
        fields = ['id', 'list_type', 'field_key', 'label', 'visible', 'required', 'order']
        read_only_fields = ['id', 'list_type', 'field_key', 'label', 'order']


class OnboardingFieldConfigCreateSerializer(serializers.Serializer):
    """Creates a new HR-defined custom field. field_key is derived from label
    in the view (mirrors LeavePolicyCreateSerializer's leave_type_label ->
    leave_type_key pattern) rather than submitted directly."""
    label      = serializers.CharField(max_length=150, trim_whitespace=True)
    field_type = serializers.ChoiceField(choices=OnboardingFieldConfig.FIELD_TYPE_CHOICES)
    options    = serializers.ListField(child=serializers.CharField(max_length=200), required=False, default=list)
    # File fields only, mirrors `options` being dropdown-only — ignored for
    # every other field_type.
    allow_multiple = serializers.BooleanField(default=False)
    # Not a fixed ChoiceField(STEP_CHOICES) — HR-created OnboardingSection
    # rows add valid step numbers beyond the 4 built-ins, so membership is
    # checked dynamically in validate_step() below instead.
    step       = serializers.IntegerField()
    required   = serializers.BooleanField(default=False)

    def validate_label(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Label cannot be blank.')
        return value

    def validate_step(self, value: int) -> int:
        from apps.accounts.views import _valid_steps
        if value not in _valid_steps():
            raise serializers.ValidationError('Not a valid step.')
        return value

    def validate(self, attrs):
        if attrs['field_type'] == OnboardingFieldConfig.TYPE_DROPDOWN and not attrs.get('options'):
            raise serializers.ValidationError('Dropdown fields need at least one option.')
        return attrs


class OnboardingFieldConfigUpdateSerializer(serializers.ModelSerializer):
    """Partial update only — field_key, field_type, is_custom, and is_locked
    are immutable after creation (changing field_type after data has been
    collected under the old type would corrupt existing custom_field_values)."""
    class Meta:
        model  = OnboardingFieldConfig
        fields = ['label', 'options', 'order', 'visible', 'required']


# ─── Onboarding Sections (HR-created custom wizard tabs) ───────────────────────

class OnboardingSectionSerializer(serializers.ModelSerializer):
    """Read-only — used for the settings list and the wizard-facing config."""
    class Meta:
        model  = OnboardingSection
        fields = ['id', 'step', 'label', 'icon', 'order', 'is_active', 'updated_at']
        read_only_fields = fields


class OnboardingSectionCreateSerializer(serializers.Serializer):
    """Creates a new HR-defined section. `step`/`order` are server-assigned
    (see OnboardingSectionListCreateView) — never client-submitted, so a
    custom section's step can never collide with the 5 reserved built-in
    step numbers (0-4)."""
    label = serializers.CharField(max_length=100, trim_whitespace=True)
    icon  = serializers.CharField(max_length=50, default='ti-folder', trim_whitespace=True)

    def validate_label(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Label cannot be blank.')
        return value

    def validate_icon(self, value: str) -> str:
        value = value.strip()
        return value or 'ti-folder'


class OnboardingSectionUpdateSerializer(serializers.ModelSerializer):
    """Partial update only — `step` is immutable after creation, same
    reasoning as OnboardingFieldConfig's field_key/field_type."""
    class Meta:
        model  = OnboardingSection
        fields = ['label', 'icon', 'order', 'is_active']


# ─── Document Type Configuration (onboarding Step 5) ───────────────────────────

class DocumentTypeConfigSerializer(serializers.ModelSerializer):
    """Read-only — used for the settings list and the wizard/Profile/Employee-
    Detail-facing public config."""
    class Meta:
        model  = DocumentTypeConfig
        fields = [
            'type_key', 'label', 'order', 'visible', 'required',
            'allow_multiple', 'is_custom', 'is_locked', 'updated_at',
        ]
        read_only_fields = fields


class DocumentTypeConfigCreateSerializer(serializers.Serializer):
    """Creates a new HR-defined document type. type_key is derived from
    label in the view, same pattern as OnboardingFieldConfigCreateSerializer's
    field_key derivation."""
    label          = serializers.CharField(max_length=150, trim_whitespace=True)
    required       = serializers.BooleanField(default=False)
    allow_multiple = serializers.BooleanField(default=False)

    def validate_label(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Label cannot be blank.')
        return value


class DocumentTypeConfigUpdateSerializer(serializers.ModelSerializer):
    """Partial update only — type_key and is_custom are immutable after
    creation (changing type_key would orphan already-uploaded documents
    referencing the old key)."""
    class Meta:
        model  = DocumentTypeConfig
        fields = ['label', 'order', 'visible', 'required', 'allow_multiple']


# ─── Onboarding Pipeline (pending + submitted) ────────────────────────────────

class OnboardingPipelineSerializer(serializers.ModelSerializer):
    candidate_id     = serializers.SerializerMethodField()
    position_applied = serializers.SerializerMethodField()
    candidate_status = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'email', 'phone',
            'onboarding_status', 'date_joined',
            'candidate_id', 'position_applied', 'candidate_status',
        ]

    def _candidate(self, obj):
        return self.context.get('candidates_by_user', {}).get(obj.pk)

    def get_candidate_id(self, obj):
        cand = self._candidate(obj)
        return cand.pk if cand else None

    def get_position_applied(self, obj):
        cand = self._candidate(obj)
        return cand.position_applied if cand else ''

    def get_candidate_status(self, obj):
        cand = self._candidate(obj)
        return cand.status if cand else ''


# ─── Onboarding Approval ──────────────────────────────────────────────────────

class OnboardingApprovalSerializer(serializers.ModelSerializer):
    role_name        = serializers.CharField(source='role.name',         read_only=True, default='')
    role_display     = serializers.CharField(source='role.display_name', read_only=True, default='')
    profile          = EmployeeProfileSerializer(read_only=True)
    documents        = EmployeeDocumentSerializer(source='employee_documents', many=True, read_only=True)
    candidate_id     = serializers.SerializerMethodField()
    position_applied = serializers.SerializerMethodField()
    branch           = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'email', 'phone', 'department', 'designation', 'branch',
            'role_name', 'role_display', 'employee_id', 'date_of_joining',
            'onboarding_status', 'date_joined',
            'candidate_id', 'position_applied',
            'profile', 'documents',
        ]

    def _candidate(self, obj):
        return self.context.get('candidates_by_user', {}).get(obj.pk)

    def get_candidate_id(self, obj):
        cand = self._candidate(obj)
        return cand.pk if cand else None

    def get_position_applied(self, obj):
        cand = self._candidate(obj)
        return cand.position_applied if cand else ''

    def get_branch(self, obj):
        # User.branch is set after approval; before that, read from the linked Candidate record
        if obj.branch:
            return obj.branch
        cand = self._candidate(obj)
        if cand and cand.branch:
            return cand.branch.branch_name
        return ''


# ─── My Profile (authenticated employee view) ─────────────────────────────────

class MyProfileSerializer(serializers.ModelSerializer):
    role_name       = serializers.CharField(source='role.name',         read_only=True, default='')
    role_display    = serializers.CharField(source='role.display_name', read_only=True, default='')
    profile         = EmployeeProfileSerializer(read_only=True)
    assessment_status  = serializers.SerializerMethodField()
    reporting_manager  = serializers.SerializerMethodField()
    reporting_approver = serializers.SerializerMethodField()
    hr                 = serializers.SerializerMethodField()
    profile_photo_url  = serializers.SerializerMethodField()
    # ESS "Employment" tab's "Current assignment" tiles (EMPLOYMENT STATUS,
    # NOTICE PERIOD) — both fields already existed on the User model but
    # were never exposed to the employee's own profile endpoint before.
    employment_status_display = serializers.CharField(source='get_employment_status_display', read_only=True)
    # The real Org Unit/Position an employee was placed into at hire time
    # (Placement, set via assign_position() during the Hire wizard) — kept
    # separate from `department`, which is only the nearest is_department
    # -level ancestor's name and stays legitimately blank when no such
    # ancestor exists in the org chart. Without this, self-service onboarding
    # had no way to show the org unit HR already assigned and looked like it
    # was "asking again" for something never actually filled.
    org_unit_name  = serializers.SerializerMethodField()
    position_title = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'email', 'phone', 'employee_id',
            'department', 'designation', 'branch', 'employee_type',
            'org_unit_name', 'position_title',
            'role_name', 'role_display', 'date_of_joining', 'date_joined',
            'work_location', 'onboarding_status', 'assessment_status',
            'employment_status', 'employment_status_display', 'notice_period_days',
            'reporting_manager', 'reporting_approver', 'hr',
            'profile', 'profile_photo_url',
        ]

    def _current_placement(self, obj: User):
        # Same "open, still-current" filter _employee_dict() (views/shared.py)
        # already uses elsewhere — an open-ended Placement (no effective_to)
        # is the one that's active right now.
        return obj.placements.filter(effective_to__isnull=True).select_related(
            'position', 'position__org_unit',
        ).first()

    def get_org_unit_name(self, obj: User) -> str | None:
        placement = self._current_placement(obj)
        return placement.position.org_unit.name if placement else None

    def get_position_title(self, obj: User) -> str | None:
        placement = self._current_placement(obj)
        return placement.position.title if placement else None

    def get_profile_photo_url(self, obj: User) -> str | None:
        if not obj.profile_photo:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.profile_photo.url) if request else obj.profile_photo.url

    def get_reporting_manager(self, obj):
        # Managers are the reporting manager for others — they have none of their own to show.
        if obj.role and obj.role.can_manage_team:
            return None
        mgr = obj.reporting_manager
        if not mgr:
            return None
        return {'id': mgr.employee_id, 'name': mgr.full_name}

    def get_reporting_approver(self, obj):
        approver = obj.reporting_approver
        if not approver:
            return None
        return {'id': approver.employee_id, 'name': approver.full_name}

    def get_hr(self, obj):
        assigned_hr = obj.hr
        if not assigned_hr:
            return None
        return {'id': assigned_hr.employee_id, 'name': assigned_hr.full_name}

    def get_assessment_status(self, obj):
        from apps.assessments.models import CandidateAssignment
        from apps.recruitment.models import Candidate

        pending_statuses = [CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]

        # Always check candidate-based assignments (covers former candidates who became employees)
        candidate = Candidate.objects.filter(portal_user=obj).first()
        if candidate:
            if CandidateAssignment.objects.filter(candidate=candidate, status__in=pending_statuses).exists():
                return 'pending'

        # For role-bearing users also check employee-based assignments
        if obj.role_id:
            if CandidateAssignment.objects.filter(employee=obj, status__in=pending_statuses).exists():
                return 'pending'
            return 'complete'

        # Portal candidate with no pending candidate assignments
        return 'complete'


class MyProfileUpdateSerializer(serializers.Serializer):
    phone                  = serializers.CharField(max_length=20,  required=False, allow_blank=True)
    current_address        = serializers.CharField(max_length=500,  required=False, allow_blank=True)
    current_address_line2  = serializers.CharField(max_length=200,  required=False, allow_blank=True)
    current_village        = serializers.CharField(max_length=150,  required=False, allow_blank=True)
    current_district       = serializers.CharField(max_length=100,  required=False, allow_blank=True)
    current_state          = serializers.CharField(max_length=100,  required=False, allow_blank=True)
    current_pin_code       = serializers.CharField(max_length=6,    required=False, allow_blank=True)
    permanent_address      = serializers.CharField(max_length=500,  required=False, allow_blank=True)
    permanent_address_line2 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    permanent_village      = serializers.CharField(max_length=150,  required=False, allow_blank=True)
    permanent_district     = serializers.CharField(max_length=100,  required=False, allow_blank=True)
    permanent_state        = serializers.CharField(max_length=100,  required=False, allow_blank=True)
    permanent_pin_code     = serializers.CharField(max_length=6,    required=False, allow_blank=True)
    permanent_same_as_current = serializers.BooleanField(required=False)
    emergency_name         = serializers.CharField(max_length=150,  required=False, allow_blank=True)
    emergency_relationship = serializers.CharField(max_length=50,   required=False, allow_blank=True)
    emergency_phone        = serializers.CharField(max_length=20,   required=False, allow_blank=True)
    emergency_email        = serializers.EmailField(required=False, allow_blank=True)
    # HR-created custom fields belonging to the Emergency Contact category
    # only (self-service can't edit Personal/Education/Bank custom fields,
    # matching those categories' existing built-in fields being read-only
    # here) — MyProfileView.patch() filters this to Emergency-only keys
    # before merging, so a crafted request can't smuggle in a Bank-category
    # custom field edit even though this serializer itself doesn't know the
    # difference.
    custom_field_values    = serializers.DictField(required=False)

    def _validate_phone_value(self, value: str, field_label: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PHONE_RE_PROFILE.match(value):
            raise serializers.ValidationError(
                f'Enter a valid {field_label} (digits, spaces, +, -, ( ) allowed; 7–20 characters).'
            )
        return value

    def validate_phone(self, value: str) -> str:
        return self._validate_phone_value(value, 'phone number')

    def validate_emergency_phone(self, value: str) -> str:
        return self._validate_phone_value(value, 'emergency contact phone number')

    def _validate_pin_code_value(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PIN_CODE_RE.match(value):
            raise serializers.ValidationError('Enter a valid 6-digit PIN code (cannot start with 0).')
        return value

    def validate_current_pin_code(self, value: str) -> str:
        return self._validate_pin_code_value(value)

    def validate_permanent_pin_code(self, value: str) -> str:
        return self._validate_pin_code_value(value)


# ─── Approval Matrix ──────────────────────────────────────────────────────────

class ApprovalWorkflowRuleSerializer(serializers.ModelSerializer):
    workflow_label    = serializers.CharField(source='get_workflow_type_display', read_only=True)
    l1_approver_role  = serializers.SerializerMethodField()
    l1_approver_label = serializers.SerializerMethodField()
    l2_approver_role  = serializers.SerializerMethodField()
    l2_approver_label = serializers.SerializerMethodField()

    class Meta:
        from apps.accounts.models import ApprovalWorkflowRule as _Rule
        model  = _Rule
        fields = [
            'workflow_type', 'workflow_label',
            'l1_approver_role', 'l1_approver_label',
            'l2_approver_role', 'l2_approver_label',
        ]

    def get_l1_approver_role(self, obj):
        return obj.l1_approver_role_id

    def get_l1_approver_label(self, obj) -> str:
        return obj.l1_approver_role.display_name if obj.l1_approver_role else ''

    def get_l2_approver_role(self, obj):
        return obj.l2_approver_role_id

    def get_l2_approver_label(self, obj) -> str:
        return obj.l2_approver_role.display_name if obj.l2_approver_role else ''


class ApprovalWorkflowRuleUpdateSerializer(serializers.Serializer):
    from apps.accounts.models import ApprovalWorkflowRule as _Rule
    workflow_type    = serializers.ChoiceField(choices=[c[0] for c in _Rule.WORKFLOW_CHOICES])
    l1_approver_role = serializers.IntegerField(min_value=1)
    l2_approver_role = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)

    def validate_l1_approver_role(self, value):
        from apps.accounts.models import Role
        try:
            return Role.objects.get(pk=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError('Role not found or inactive.')

    def validate_l2_approver_role(self, value):
        if value is None:
            return None
        from apps.accounts.models import Role
        try:
            return Role.objects.get(pk=value, is_active=True)
        except Role.DoesNotExist:
            raise serializers.ValidationError('Role not found or inactive.')


# ── Employee Bulk Import ───────────────────────────────────────────────────────

_EMP_PHONE_RE         = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')
_EMP_IMPORT_DATE_FMTS = ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', 'iso-8601']
_EMP_VALID_GENDERS    = frozenset({'male', 'female', 'other'})
_EMP_VALID_BLOOD      = frozenset({'a+', 'a-', 'b+', 'b-', 'o+', 'o-', 'ab+', 'ab-'})


class EmployeeBulkImportRowSerializer(serializers.Serializer):
    """Validates one row from an employee bulk-import CSV/XLSX file.

    Role / org_unit+position_title / branch existence checks happen in the
    view (pre-loaded once per batch), so those fields are plain CharFields
    here. org_unit/position_title resolve to a real Position (see
    EmployeeBulkImportView.post()), with department/designation derived
    from it — same as Create Employee's own Position picker. Manual
    department/designation columns are no longer accepted.
    """

    first_name      = serializers.CharField(max_length=150)
    last_name       = serializers.CharField(max_length=150)
    email           = serializers.EmailField()
    phone           = serializers.CharField(max_length=20, required=False,
                                             allow_blank=True, default='')
    role            = serializers.CharField(max_length=100)
    org_unit        = serializers.CharField(max_length=150)
    position_title  = serializers.CharField(max_length=150)
    branch          = serializers.CharField(max_length=100)
    employee_type   = serializers.CharField(max_length=50, required=False,
                                             allow_blank=True, default='Permanent')
    date_of_joining = serializers.DateField(input_formats=_EMP_IMPORT_DATE_FMTS)
    gender          = serializers.CharField(max_length=10, required=False,
                                             allow_blank=True, default='')
    date_of_birth   = serializers.DateField(
                          required=False, allow_null=True, default=None,
                          input_formats=_EMP_IMPORT_DATE_FMTS,
                      )
    blood_group          = serializers.CharField(max_length=5, required=False,
                                                  allow_blank=True, default='')
    address              = serializers.CharField(required=False, allow_blank=True, default='')
    uan_number           = serializers.CharField(max_length=12, required=False,
                                                  allow_blank=True, default='')
    name_as_per_aadhar   = serializers.CharField(max_length=150, required=False,
                                                  allow_blank=True, default='')
    annual_ctc           = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_first_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('First name is required.')
        return value

    def validate_last_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Last name is required.')
        return value

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        if value and not _EMP_PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
            )
        return value

    def validate_role(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Role is required.')
        return value

    def validate_uan_number(self, value: str) -> str:
        value = value.strip()
        if value and (len(value) != 12 or not value.isdigit()):
            raise serializers.ValidationError('UAN must be exactly 12 digits.')
        return value

    def validate_org_unit(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Org Unit is required.')
        return value

    def validate_position_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position is required.')
        return value

    def validate_branch(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Company Code is required.')
        return value

    def validate_gender(self, value: str) -> str:
        if not value:
            return value
        normalized = value.strip().lower()
        if normalized not in _EMP_VALID_GENDERS:
            raise serializers.ValidationError(
                f'Invalid gender "{value}". Allowed: male, female, other.'
            )
        return normalized

    def validate_blood_group(self, value: str) -> str:
        if not value:
            return value
        normalized = value.strip().lower()
        if normalized not in _EMP_VALID_BLOOD:
            raise serializers.ValidationError(
                f'Invalid blood group "{value}". '
                f'Allowed: A+, A-, B+, B-, O+, O-, AB+, AB-.'
            )
        return value.strip().upper()

    def validate_address(self, value: str) -> str:
        if value and len(value) > 500:
            raise serializers.ValidationError('Address must be 500 characters or fewer.')
        return value
