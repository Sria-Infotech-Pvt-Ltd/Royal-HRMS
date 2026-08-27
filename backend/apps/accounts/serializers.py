
from __future__ import annotations

import os
import re

from django.core import signing

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import (
    AuditLog,
    Company,
    CompanyDirector,
    CompanyGSTRegistration,
    CustomFieldFileValue,
    Department,
    Designation,
    Document,
    DocumentTypeConfig,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeCodeSettings,
    EmployeeDocument,
    EmployeeProfile,
    JobTemplate,
    OnboardingFieldConfig,
    OrgUnit,
    Permission,
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


# ─── Organisation Structure ────────────────────────────────────────────────────

class DesignationSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model  = Designation
        fields = ('id', 'name', 'department', 'department_name', 'level', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'department_name', 'created_at', 'updated_at')

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Designation name must not be blank.')
        if len(value) > 100:
            raise serializers.ValidationError('Designation name must be under 100 characters.')
        return value

    def validate_department(self, value):
        if value is None:
            raise serializers.ValidationError('Department is required.')
        return value

    def validate(self, attrs: dict) -> dict:
        name  = attrs.get('name', getattr(self.instance, 'name', None))
        dept  = attrs.get('department', getattr(self.instance, 'department', None))
        if dept is None:
            raise serializers.ValidationError({'department': 'Department is required.'})
        qs    = Designation.objects.filter(name__iexact=name, department=dept)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'name': f'A designation named "{name}" already exists in this department.'}
            )
        return attrs


class DepartmentSerializer(serializers.ModelSerializer):
    designation_count = serializers.SerializerMethodField()
    employee_count    = serializers.SerializerMethodField()
    roles             = serializers.SerializerMethodField()
    manager_name      = serializers.CharField(source='manager.full_name', read_only=True, default=None)

    class Meta:
        model  = Department
        fields = (
            'id', 'name', 'description', 'is_active', 'created_at',
            'manager', 'manager_name',
            'designation_count', 'employee_count', 'roles',
        )
        read_only_fields = ('id', 'created_at', 'manager_name', 'designation_count', 'employee_count', 'roles')

    def get_designation_count(self, obj: Department) -> int:
        return len(obj.designations.all())  # uses prefetch cache — no extra query

    def get_employee_count(self, obj: Department) -> int:
        counts = self.context.get('emp_counts')
        if counts is not None:
            return counts.get(obj.name, 0)
        return User.objects.filter(department=obj.name).count()

    def get_roles(self, obj: Department) -> list:
        roles = self.context.get('dept_roles')
        if roles is not None:
            return [{'name': r[0], 'display_name': r[1]} for r in roles.get(obj.name, [])]
        rows = (
            User.objects.filter(department=obj.name)
                .select_related('role')
                .exclude(role=None)
                .values_list('role__name', 'role__display_name')
                .distinct()
                .order_by('role__display_name')
        )
        return [{'name': r[0], 'display_name': r[1]} for r in rows]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Department name must not be blank.')
        if len(value) > 100:
            raise serializers.ValidationError('Department name must be under 100 characters.')
        return value

    def validate_description(self, value: str) -> str:
        if len(value) > 300:
            raise serializers.ValidationError('Description must be under 300 characters.')
        return value


# ─── Org Structure (units, positions, job templates) ──────────────────────────
# Separate from Department/Designation above — a real hierarchy with its own
# Position/holder model, used only by the Org Structure page. Doesn't touch
# User.department/reporting_manager or any approval routing.

class JobTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = JobTemplate
        fields = ('id', 'name', 'band', 'is_active')
        read_only_fields = ('id',)


class OrgUnitSerializer(serializers.ModelSerializer):
    position_count = serializers.SerializerMethodField()
    child_count    = serializers.SerializerMethodField()

    class Meta:
        model  = OrgUnit
        fields = (
            'id', 'name', 'code', 'parent', 'cost_center',
            'position_count', 'child_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'position_count', 'child_count', 'created_at', 'updated_at')

    def get_position_count(self, obj: OrgUnit) -> int:
        return obj.positions.count()

    def get_child_count(self, obj: OrgUnit) -> int:
        return obj.children.count()

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
    org_unit_name       = serializers.CharField(source='org_unit.name', read_only=True)
    job_template_name   = serializers.CharField(source='job_template.name', read_only=True, default=None)
    holder_name         = serializers.CharField(source='holder.full_name', read_only=True, default=None)
    holder_employee_id  = serializers.CharField(source='holder.employee_id', read_only=True, default=None)
    reports_to          = serializers.SerializerMethodField()

    class Meta:
        model  = Position
        fields = (
            'id', 'org_unit', 'org_unit_name', 'job_template', 'job_template_name',
            'title', 'grade', 'is_chief', 'holder', 'holder_name', 'holder_employee_id',
            'reports_to', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'org_unit_name', 'job_template_name', 'holder_name',
            'holder_employee_id', 'reports_to', 'created_at', 'updated_at',
        )

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position title is required.')
        if len(value) > 150:
            raise serializers.ValidationError('Position title must be under 150 characters.')
        return value

    def get_reports_to(self, obj: Position) -> dict | None:
        """Mirrors the mockup's own reportsToName() logic: a chief reports to
        the parent unit's chief; anyone else reports to their own unit's
        chief. Purely a computed display value — never a new source of truth
        for approval routing, which stays on User.reporting_manager."""
        if obj.is_chief:
            target = (
                obj.org_unit.parent.positions.filter(is_chief=True).first()
                if obj.org_unit.parent else None
            )
        else:
            target = obj.org_unit.positions.filter(is_chief=True).first()
        if not target or target.pk == obj.pk:
            return None
        return {
            'position_id': str(target.pk),
            'title': target.title,
            'holder_name': target.holder.full_name if target.holder else None,
        }

    def _unset_other_chiefs(self, instance: Position) -> None:
        if instance.is_chief:
            Position.objects.filter(org_unit=instance.org_unit).exclude(pk=instance.pk).update(is_chief=False)

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._unset_other_chiefs(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._unset_other_chiefs(instance)
        return instance

    def validate(self, attrs: dict) -> dict:
        name = attrs.get('name', getattr(self.instance, 'name', None))
        qs   = Department.objects.filter(name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {'name': f'A department named "{name}" already exists.'}
            )
        return attrs


# ─── Company ──────────────────────────────────────────────────────────────────

_GSTIN_RE = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z1-9]Z[A-Z\d]$')
_PAN_RE   = re.compile(r'^[A-Z]{5}\d{4}[A-Z]$')
_CIN_RE   = re.compile(r'^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$')
_TAN_RE   = re.compile(r'^[A-Z]{4}\d{5}[A-Z]$')
_PIN_RE   = re.compile(r'^\d{6}$')
_PHONE_RE = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')
_DIN_RE   = re.compile(r'^\d{8}$')

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


def _gstin_pan_mismatch_error(gstin: str, pan: str) -> str | None:
    # A GSTIN's characters 3-12 are always the PAN it was issued against —
    # this is free, offline arithmetic (no government lookup needed) that
    # still catches the common real mistake of a mistyped GSTIN or a
    # leftover GSTIN from a different PAN, without pretending to verify
    # the GSTIN is actually registered with the government.
    if gstin and pan and gstin[2:12] != pan:
        return f"This GSTIN belongs to PAN {gstin[2:12]}, not the company PAN ({pan})."
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
        if not _CIN_RE.match(v):
            raise serializers.ValidationError('Enter a valid CIN (e.g. U74999MH2020PTC123456).')
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
        if not _PIN_RE.match(v):
            raise serializers.ValidationError('PIN code must be exactly 6 digits.')
        return v

    def validate_communication_pin_code(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if not _PIN_RE.match(v):
            raise serializers.ValidationError('PIN code must be exactly 6 digits.')
        return v

    def validate_website(self, value: str) -> str:
        if not value:
            return value
        v = value.strip()
        if v and not v.startswith(('http://', 'https://')):
            raise serializers.ValidationError('Website must start with http:// or https://.')
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
                if not _val('tan'):
                    errors['tan'] = 'TAN is required for an Indian entity.'
                if entity_type in _CIN_ENTITY_TYPES and not _val('cin'):
                    errors['cin'] = 'CIN is required for this entity type.'
            else:
                if not _val('country_of_registration'):
                    errors['country_of_registration'] = 'Country of registration is required for a foreign entity.'
                if not _val('registration_number'):
                    errors['registration_number'] = 'Registration number is required for a foreign entity.'

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

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CompanyDirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompanyDirector
        fields = ['id', 'company', 'din', 'name', 'designation', 'created_at', 'updated_at']
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']

    def validate_din(self, value: str) -> str:
        v = value.strip()
        if not _DIN_RE.match(v):
            raise serializers.ValidationError('DIN must be exactly 8 digits.')
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
        if not value.isalpha():
            raise serializers.ValidationError('Prefix must contain letters only.')
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


class EmployeeProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = EmployeeProfile
        fields = [
            'date_of_birth', 'gender', 'marital_status', 'father_name',
            'blood_group', 'current_address', 'permanent_address',
            'highest_qualification', 'institution', 'year_of_passing', 'specialization',
            'total_experience_years', 'previous_employer', 'previous_designation', 'leaving_reason',
            'account_number', 'ifsc_code', 'bank_name', 'bank_branch_name',
            'account_holder_name', 'account_type',
            'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
            'uan_number', 'esi_number', 'name_as_per_aadhar', 'pan_number',
            'custom_field_values',
            'updated_at',
        ]
        read_only_fields = ('updated_at',)

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
        if value.size > EmployeeDocument.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f'File size {value.size / (1024 * 1024):.1f} MB exceeds the 5 MB limit.'
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
    step       = serializers.ChoiceField(choices=OnboardingFieldConfig.STEP_CHOICES)
    required   = serializers.BooleanField(default=False)

    def validate_label(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Label cannot be blank.')
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

    class Meta:
        model  = User
        fields = [
            'id', 'full_name', 'email', 'phone', 'employee_id',
            'department', 'designation', 'branch',
            'role_name', 'role_display', 'date_of_joining', 'date_joined',
            'onboarding_status', 'assessment_status',
            'reporting_manager', 'reporting_approver', 'hr',
            'profile', 'profile_photo_url',
        ]

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
    permanent_address      = serializers.CharField(max_length=500,  required=False, allow_blank=True)
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

    Role / department / designation / branch existence checks happen in the view
    (pre-loaded once per batch), so those fields are plain CharFields here.
    """

    first_name      = serializers.CharField(max_length=150)
    last_name       = serializers.CharField(max_length=150)
    email           = serializers.EmailField()
    phone           = serializers.CharField(max_length=20, required=False,
                                             allow_blank=True, default='')
    role            = serializers.CharField(max_length=100)
    department      = serializers.CharField(max_length=100)
    designation     = serializers.CharField(max_length=100)
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

    def validate_department(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Department is required.')
        return value

    def validate_uan_number(self, value: str) -> str:
        value = value.strip()
        if value and (len(value) != 12 or not value.isdigit()):
            raise serializers.ValidationError('UAN must be exactly 12 digits.')
        return value

    def validate_designation(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Designation is required.')
        return value

    def validate_branch(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Branch is required.')
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
