import logging
import re

from django.db.models import Q
from rest_framework import serializers

from .models import (
    APPROVAL_PENDING,
    CarryForwardLog,
    Expense, ExpenseReceipt,
    Holiday,
    LeaveBalance, LeavePolicy, LeaveRequest,
    LEAVE_TYPE_CHOICES, DURATION_CHOICES,
    BUILTIN_LEAVE_TYPE_KEYS, leave_type_usage,
    WorkFromHomeRequest,
    WFHSavedLocation,
    SeparationRequest,
    SEP_PENDING, SEP_STAGE2_PENDING, SEP_APPROVED, SEP_REJECTED, SEP_CANCELLED,
    SEP_STAGE_HR, SEP_STAGE_MANAGER, SEP_STAGE_BRANCH_ADMIN,
    SEP_CLEARANCE_MANAGER,
    SeparationApprovalStage, SeparationHandoverTask, SeparationClearance,
    SeparationDocument, SeparationActivity,
)

logger = logging.getLogger(__name__)

MAX_RECEIPT_SIZE   = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}


class ExpenseReceiptSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model  = ExpenseReceipt
        fields = ['id', 'url']

    def get_url(self, obj: ExpenseReceipt) -> str | None:
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class ExpenseSerializer(serializers.ModelSerializer):
    employee_name  = serializers.SerializerMethodField()
    branch_name    = serializers.SerializerMethodField()
    receipts       = ExpenseReceiptSerializer(many=True, read_only=True)
    expense_ref    = serializers.SerializerMethodField()

    class Meta:
        model  = Expense
        fields = [
            'expense_number', 'expense_ref', 'title', 'category', 'amount', 'expense_date',
            'description', 'status', 'receipts',
            'employee_name', 'branch_name', 'created_at',
        ]

    def get_expense_ref(self, obj: Expense) -> str:
        if obj.expense_number is None:
            return ''
        return f'EXP{obj.expense_number:03d}'

    def get_employee_name(self, obj: Expense) -> str:
        return obj.employee.full_name if obj.employee_id else ''

    def get_branch_name(self, obj: Expense) -> str:
        return obj.branch.branch_name if obj.branch_id else ''


class ExpenseCreateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)

    class Meta:
        model  = Expense
        fields = ['title', 'category', 'amount', 'expense_date', 'description']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero.')
        return value

    def validate_category(self, value):
        lowered  = value.strip().lower()
        valid    = [c[0] for c in Expense.CATEGORY_CHOICES]
        if lowered in valid:
            return lowered
        by_label = {label.lower(): key for key, label in Expense.CATEGORY_CHOICES}
        if lowered in by_label:
            return by_label[lowered]
        raise serializers.ValidationError(
            f'Invalid category. Choose from: {", ".join(valid)}.'
        )

    def validate(self, attrs):
        if not attrs.get('title'):
            label_map      = {key: label for key, label in Expense.CATEGORY_CHOICES}
            category       = attrs.get('category', '')
            attrs['title'] = label_map.get(category, category.capitalize())
        return attrs


def validate_receipt_file(file) -> None:
    if file.size > MAX_RECEIPT_SIZE:
        raise serializers.ValidationError('Each receipt must be under 5 MB.')
    content_type = getattr(file, 'content_type', '')
    if content_type not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError('Only PDF, JPG, and PNG receipts are accepted.')


# ─── Leave serializers ────────────────────────────────────────────────────────

_LEAVE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z -]*$")


def _validate_leave_type_label(value: str, exclude_pk=None) -> str:
    """Shared by LeavePolicyCreateSerializer and LeavePolicyUpdateSerializer
    so the two flows can never drift apart. exclude_pk excludes the record
    being edited from the duplicate check (otherwise saving an unchanged
    name on update would always "collide" with itself). The duplicate check
    matches on the derived key (same slug a create would produce — catches
    a rename colliding with a built-in type's fixed leave_type, e.g.
    renaming something to "Sick") OR an exact case-insensitive match on
    another row's own explicit leave_type_label.
    """
    value = value.strip()
    if not value:
        raise serializers.ValidationError('Display name cannot be empty.')
    if not _LEAVE_NAME_RE.match(value):
        raise serializers.ValidationError(
            'Display name can only contain letters, spaces, and hyphens — no numbers or special characters.'
        )
    key = value.lower().replace(' ', '_').replace('-', '_')
    qs = LeavePolicy.objects.filter(Q(leave_type=key) | Q(leave_type_label__iexact=value))
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise serializers.ValidationError('A leave type with this name already exists.')
    return value

_POLICY_RULE_FIELDS = [
    # Application Rules
    'minimum_leave_duration', 'maximum_leave_duration', 'maximum_consecutive_days',
    'minimum_notice_period', 'allow_half_day', 'allow_backdated_leave',
    'maximum_backdated_days', 'allow_future_leave', 'maximum_future_days',
    # Holiday & Week-off Rules
    'sandwich_leave_enabled', 'count_holidays_as_leave', 'count_weekoffs_as_leave',
    # Eligibility Rules
    'applicable_branches', 'applicable_departments', 'applicable_designations',
    'applicable_employment_types', 'applicable_gender', 'minimum_service_period',
    # Documentation Rules
    'attachment_required', 'medical_certificate_required', 'medical_certificate_after_days',
    # Leave Restrictions
    'allow_negative_balance', 'convert_to_lop', 'allow_leave_cancellation',
    'cancellation_allowed_until',
    # Additional Rules
    'allow_probation_leave', 'allow_notice_period_leave', 'allow_leave_extension',
    'allow_leave_combination',
]


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_display = serializers.SerializerMethodField()
    # Lets the frontend show the right delete confirmation (plain confirm vs.
    # "in use, deactivate instead") without a separate round-trip per row —
    # the delete endpoint itself (LeavePolicyView.delete()) re-checks this
    # fresh and is the actual authoritative gate; this is a display hint only.
    usage_info = serializers.SerializerMethodField()

    class Meta:
        model  = LeavePolicy
        fields = (
            ['id', 'leave_type', 'leave_type_display', 'annual_days', 'can_carry_forward',
             'max_carry_forward_days', 'carry_forward_type', 'carry_forward_mode',
             'carry_forward_expiry_days', 'policy_note', 'is_active']
            + _POLICY_RULE_FIELDS
            + ['updated_at', 'usage_info']
        )

    def get_leave_type_display(self, obj) -> str:
        if obj.leave_type_label:
            return obj.leave_type_label
        return dict(LEAVE_TYPE_CHOICES).get(obj.leave_type, obj.leave_type.replace('_', ' ').title())

    def get_usage_info(self, obj) -> dict:
        if obj.leave_type in BUILTIN_LEAVE_TYPE_KEYS:
            # Built-ins are never deletable regardless of usage — no need to
            # run the queries just to report a number nothing will use.
            return {
                'in_use': False, 'affected_employee_count': 0,
                'leave_balance_count': 0, 'leave_request_count': 0,
            }
        return leave_type_usage(obj.leave_type)


class LeavePolicyCreateSerializer(serializers.Serializer):
    leave_type_label       = serializers.CharField(max_length=100)
    annual_days            = serializers.DecimalField(max_digits=5, decimal_places=1, default=0)
    can_carry_forward         = serializers.BooleanField(default=False)
    max_carry_forward_days    = serializers.IntegerField(default=0, min_value=0)
    carry_forward_type        = serializers.ChoiceField(choices=['limited', 'unlimited'], default='limited', required=False)
    carry_forward_mode        = serializers.ChoiceField(choices=['automatic', 'manual'], default='automatic', required=False)
    carry_forward_expiry_days = serializers.IntegerField(default=0, min_value=0, required=False)
    policy_note               = serializers.CharField(required=False, default='', allow_blank=True)
    is_active              = serializers.BooleanField(default=True)
    # Application Rules
    minimum_leave_duration   = serializers.DecimalField(max_digits=4, decimal_places=1, default=0.5, required=False)
    maximum_leave_duration   = serializers.IntegerField(min_value=0, default=0, required=False)
    maximum_consecutive_days = serializers.IntegerField(min_value=0, default=0, required=False)
    minimum_notice_period    = serializers.IntegerField(min_value=0, default=0, required=False)
    allow_half_day           = serializers.BooleanField(default=True, required=False)
    allow_backdated_leave    = serializers.BooleanField(default=False, required=False)
    maximum_backdated_days   = serializers.IntegerField(min_value=0, default=0, required=False)
    allow_future_leave       = serializers.BooleanField(default=True, required=False)
    maximum_future_days      = serializers.IntegerField(min_value=0, default=0, required=False)
    # Holiday & Week-off Rules
    sandwich_leave_enabled  = serializers.BooleanField(default=False, required=False)
    count_holidays_as_leave = serializers.BooleanField(default=False, required=False)
    count_weekoffs_as_leave = serializers.BooleanField(default=False, required=False)
    # Eligibility Rules
    applicable_branches         = serializers.ListField(child=serializers.CharField(allow_blank=True), default=list, required=False)
    applicable_departments      = serializers.ListField(child=serializers.CharField(allow_blank=True), default=list, required=False)
    applicable_designations     = serializers.ListField(child=serializers.CharField(allow_blank=True), default=list, required=False)
    applicable_employment_types = serializers.ListField(child=serializers.CharField(allow_blank=True), default=list, required=False)
    applicable_gender           = serializers.ChoiceField(choices=['all', 'male', 'female'], default='all', required=False)
    minimum_service_period      = serializers.IntegerField(min_value=0, default=0, required=False)
    # Documentation Rules
    attachment_required            = serializers.BooleanField(default=False, required=False)
    medical_certificate_required   = serializers.BooleanField(default=False, required=False)
    medical_certificate_after_days = serializers.IntegerField(min_value=0, default=3, required=False)
    # Leave Restrictions
    allow_negative_balance     = serializers.BooleanField(default=False, required=False)
    convert_to_lop             = serializers.BooleanField(default=False, required=False)
    allow_leave_cancellation   = serializers.BooleanField(default=True, required=False)
    cancellation_allowed_until = serializers.IntegerField(min_value=0, default=0, required=False)
    # Additional Rules
    allow_probation_leave     = serializers.BooleanField(default=False, required=False)
    allow_notice_period_leave = serializers.BooleanField(default=False, required=False)
    allow_leave_extension     = serializers.BooleanField(default=False, required=False)
    allow_leave_combination   = serializers.BooleanField(default=False, required=False)

    def validate_leave_type_label(self, value):
        return _validate_leave_type_label(value)

    def validate_annual_days(self, value):
        if value < 0:
            raise serializers.ValidationError('Annual days cannot be negative.')
        return value

    def validate(self, data):
        max_dur = data.get('maximum_leave_duration', 0)
        min_dur = float(data.get('minimum_leave_duration', 0.5))
        if max_dur and min_dur and max_dur < min_dur:
            raise serializers.ValidationError({'maximum_leave_duration': 'Maximum duration must be ≥ minimum duration.'})
        if data.get('medical_certificate_required') and not data.get('medical_certificate_after_days'):
            raise serializers.ValidationError({'medical_certificate_after_days': 'Required when medical certificate is enabled.'})

        can_carry_forward      = data.get('can_carry_forward', False)
        max_carry_forward_days = data.get('max_carry_forward_days', 0)
        if not can_carry_forward:
            # Carry forward is off — any stale days left in the field are ignored,
            # not just disabled in the UI. Prevents a disabled-but-nonzero value
            # from silently persisting to the database.
            data['max_carry_forward_days'] = 0
        elif max_carry_forward_days < 1:
            raise serializers.ValidationError(
                {'max_carry_forward_days': 'Must be at least 1 when carry forward is enabled.'}
            )
        return data


class LeavePolicyUpdateSerializer(serializers.ModelSerializer):
    # Explicit (not auto-generated from the model field, which is blank=True
    # and would default to required=False) — editing the name still
    # requires a real value, same as creating one.
    leave_type_label = serializers.CharField(max_length=100, required=False)

    class Meta:
        model  = LeavePolicy
        fields = (
            ['leave_type_label', 'annual_days', 'can_carry_forward', 'max_carry_forward_days',
             'carry_forward_type', 'carry_forward_mode', 'carry_forward_expiry_days',
             'policy_note', 'is_active']
            + _POLICY_RULE_FIELDS
        )

    def validate_leave_type_label(self, value):
        return _validate_leave_type_label(value, exclude_pk=self.instance.pk if self.instance else None)

    def validate_annual_days(self, value):
        if value < 0:
            raise serializers.ValidationError('Annual days cannot be negative.')
        return value

    def validate(self, data):
        max_dur = data.get('maximum_leave_duration')
        min_dur = data.get('minimum_leave_duration')
        if max_dur is not None and min_dur is not None and max_dur > 0 and float(max_dur) < float(min_dur):
            raise serializers.ValidationError({'maximum_leave_duration': 'Maximum duration must be ≥ minimum duration.'})
        if data.get('medical_certificate_required') and not data.get('medical_certificate_after_days'):
            raise serializers.ValidationError({'medical_certificate_after_days': 'Required when medical certificate is enabled.'})

        can_carry_forward = data.get(
            'can_carry_forward',
            self.instance.can_carry_forward if self.instance else False,
        )
        max_carry_forward_days = data.get(
            'max_carry_forward_days',
            self.instance.max_carry_forward_days if self.instance else 0,
        )
        if not can_carry_forward:
            # Carry forward is off — any stale days left in the field are ignored,
            # not just disabled in the UI. Prevents a disabled-but-nonzero value
            # from silently persisting to the database.
            data['max_carry_forward_days'] = 0
        elif max_carry_forward_days < 1:
            raise serializers.ValidationError(
                {'max_carry_forward_days': 'Must be at least 1 when carry forward is enabled.'}
            )
        return data


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    available_days = serializers.SerializerMethodField()
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)

    class Meta:
        model  = LeaveBalance
        fields = [
            'id', 'employee_name', 'leave_type', 'leave_type_display',
            'year', 'total_days', 'used_days', 'carried_forward',
            'carry_forward_expiry_date', 'available_days',
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee_id else ''

    def get_available_days(self, obj):
        return float(obj.total_days - obj.used_days)


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name      = serializers.SerializerMethodField()
    employee_code      = serializers.SerializerMethodField()
    employee_dept      = serializers.SerializerMethodField()
    employee_branch    = serializers.SerializerMethodField()
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)
    duration_display   = serializers.CharField(source='get_duration_display', read_only=True)
    l1_approver_name   = serializers.SerializerMethodField()
    l2_approver_name   = serializers.SerializerMethodField()
    document_url       = serializers.SerializerMethodField()
    can_approve        = serializers.SerializerMethodField()
    can_cancel         = serializers.SerializerMethodField()
    approved_by        = serializers.SerializerMethodField()
    approved_at        = serializers.SerializerMethodField()

    class Meta:
        model  = LeaveRequest
        fields = [
            'id', 'leave_type', 'leave_type_display', 'duration', 'duration_display',
            'start_date', 'end_date', 'total_days', 'lop_days', 'reason', 'status', 'is_lwp',
            'employee_name', 'employee_code', 'employee_dept', 'employee_branch',
            'l1_approver_name', 'l1_status', 'l1_remarks', 'l1_actioned_at',
            'l2_approver_name', 'l2_status', 'l2_remarks', 'l2_actioned_at',
            'contact_during_leave', 'handover_to', 'handover_notes',
            'document_url', 'created_at',
            'can_approve', 'can_cancel',
            'approved_by', 'approved_at',
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee_id else ''

    def get_employee_code(self, obj):
        return obj.employee.employee_id if obj.employee_id else ''

    def get_employee_dept(self, obj):
        return obj.employee.department if obj.employee_id else ''

    def get_employee_branch(self, obj):
        return obj.employee.branch if obj.employee_id else ''

    def get_l1_approver_name(self, obj):
        return obj.l1_approver.full_name if obj.l1_approver_id else ''

    def get_l2_approver_name(self, obj):
        return obj.l2_approver.full_name if obj.l2_approver_id else ''

    def get_document_url(self, obj):
        if not obj.document:
            return None
        request = self.context.get('request')
        url = obj.document.url
        return request.build_absolute_uri(url) if request else url

    def get_approved_by(self, obj):
        """Latest actioner: HR if they acted, else manager if they acted, else assigned manager."""
        if obj.l2_status:
            return obj.l2_approver.full_name if obj.l2_approver_id else ''
        if obj.l1_status:
            return obj.l1_approver.full_name if obj.l1_approver_id else ''
        return obj.l1_approver.full_name if obj.l1_approver_id else ''

    def get_approved_at(self, obj):
        """Timestamp of the latest action taken."""
        if obj.l2_actioned_at:
            return obj.l2_actioned_at
        return obj.l1_actioned_at

    def get_can_approve(self, obj):
        """True only for approvers viewing someone else's pending request."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        user = request.user
        is_own = obj.employee_id == user.id
        is_pending = obj.status in ('pending', 'l2_pending')
        has_perm = (
            user.role is not None
            and user.role.role_permissions.filter(permission__codename='leave.approve').exists()
        )
        return has_perm and not is_own and is_pending

    def get_can_cancel(self, obj):
        """True only for the employee who submitted the request, while still pending."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        is_own    = obj.employee_id == request.user.id
        is_pending = obj.status in ('pending', 'l2_pending')
        return is_own and is_pending


MAX_DOCUMENT_SIZE  = 5 * 1024 * 1024
ALLOWED_DOC_TYPES  = {'image/jpeg', 'image/png', 'application/pdf'}


# ─── Work From Home serializers ───────────────────────────────────────────────

class WorkFromHomeRequestSerializer(serializers.ModelSerializer):
    employee_name    = serializers.SerializerMethodField()
    employee_code    = serializers.SerializerMethodField()
    employee_dept    = serializers.SerializerMethodField()
    employee_branch  = serializers.SerializerMethodField()
    l1_approver_name = serializers.SerializerMethodField()
    l2_approver_name = serializers.SerializerMethodField()
    can_approve      = serializers.SerializerMethodField()
    can_cancel       = serializers.SerializerMethodField()

    class Meta:
        model  = WorkFromHomeRequest
        fields = [
            'id', 'start_date', 'end_date', 'reason', 'location_label',
            'latitude', 'longitude', 'status',
            'employee_name', 'employee_code', 'employee_dept', 'employee_branch',
            'l1_approver_name', 'l1_status', 'l1_remarks', 'l1_actioned_at',
            'l2_approver_name', 'l2_status', 'l2_remarks', 'l2_actioned_at',
            'created_at',
            'can_approve', 'can_cancel',
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee_id else ''

    def get_employee_code(self, obj):
        return obj.employee.employee_id if obj.employee_id else ''

    def get_employee_dept(self, obj):
        return obj.employee.department if obj.employee_id else ''

    def get_employee_branch(self, obj):
        return obj.employee.branch if obj.employee_id else ''

    def get_l1_approver_name(self, obj):
        return obj.l1_approver.full_name if obj.l1_approver_id else ''

    def get_l2_approver_name(self, obj):
        return obj.l2_approver.full_name if obj.l2_approver_id else ''

    def get_can_approve(self, obj):
        """True only for approvers viewing someone else's pending request."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        user = request.user
        is_own = obj.employee_id == user.id
        is_pending = obj.status in ('pending', 'l2_pending')
        has_perm = (
            user.role is not None
            and user.role.role_permissions.filter(permission__codename='wfh.approve').exists()
        )
        return has_perm and not is_own and is_pending

    def get_can_cancel(self, obj):
        """True only for the employee who submitted the request, while still pending."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        is_own = obj.employee_id == request.user.id
        is_pending = obj.status in ('pending', 'l2_pending')
        return is_own and is_pending


class WorkFromHomeRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WorkFromHomeRequest
        fields = ['start_date', 'end_date', 'reason', 'location_label', 'latitude', 'longitude']

    def to_internal_value(self, data):
        # The browser's Geolocation API returns far more decimal precision
        # than the model's decimal_places=6 (e.g. 17.3850445674382) — DRF's
        # DecimalField validates the raw digit count before any rounding, so
        # an unrounded reading fails max_digits even though the value itself
        # is a perfectly valid coordinate. Round here so any client's raw
        # GPS precision is accepted; 6 decimal places is already ~0.11m
        # resolution, far tighter than a WFH geofence check needs.
        data = data.copy()
        for field in ('latitude', 'longitude'):
            if data.get(field) is not None:
                try:
                    data[field] = round(float(data[field]), 6)
                except (TypeError, ValueError):
                    pass  # let the field's own validation report the bad value
        return super().to_internal_value(data)

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date must be on or after start date.'})
        return data


class WFHSavedLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WFHSavedLocation
        fields = ['id', 'label', 'latitude', 'longitude', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_internal_value(self, data):
        # Same raw-GPS-precision issue as WorkFromHomeRequestCreateSerializer
        # above — round before DRF's own DecimalField validation runs.
        data = data.copy()
        for field in ('latitude', 'longitude'):
            if data.get(field) is not None:
                try:
                    data[field] = round(float(data[field]), 6)
                except (TypeError, ValueError):
                    pass
        return super().to_internal_value(data)

    def validate_label(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Label is required.')
        return value


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaveRequest
        fields = [
            'leave_type', 'duration', 'start_date', 'end_date',
            'reason', 'contact_during_leave', 'handover_to', 'handover_notes', 'document',
        ]

    def validate_leave_type(self, value):
        valid = [k for k, _ in LEAVE_TYPE_CHOICES]
        if value not in valid:
            if not LeavePolicy.objects.filter(leave_type=value, is_active=True).exists():
                raise serializers.ValidationError('Invalid leave type.')
        return value

    def validate_duration(self, value):
        valid = [k for k, _ in DURATION_CHOICES]
        if value not in valid:
            raise serializers.ValidationError('Invalid duration.')
        return value

    def validate_reason(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError('Reason must be at least 10 characters.')
        return value

    def validate_document(self, value):
        if value is None:
            return value
        if value.size > MAX_DOCUMENT_SIZE:
            raise serializers.ValidationError('Document must be under 5 MB.')
        content_type = getattr(value, 'content_type', '')
        if content_type not in ALLOWED_DOC_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG documents are accepted.')
        return value

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': 'End date must be on or after start date.'})
        return data


# ─── Holiday serializers ──────────────────────────────────────────────────────

# Letters, spaces, and the punctuation real holiday names use — e.g.
# "New Year's Day", "Dr. B.R. Ambedkar Jayanti" — but never a bare number
# or symbol string (the lookahead requires at least one letter).
_HOLIDAY_NAME_RE = re.compile(r"^(?=.*[A-Za-z])[A-Za-z .'-]+$")

class HolidaySerializer(serializers.ModelSerializer):
    branch_name          = serializers.SerializerMethodField()
    holiday_type_display = serializers.CharField(source='get_holiday_type_display', read_only=True)
    day                  = serializers.SerializerMethodField()
    mandatory_optional   = serializers.SerializerMethodField()

    class Meta:
        model  = Holiday
        fields = [
            'id', 'name', 'date', 'day', 'holiday_type', 'holiday_type_display',
            'is_optional', 'mandatory_optional',
            'description', 'branch', 'branch_name', 'is_active', 'created_at',
        ]

    def get_branch_name(self, obj) -> str:
        return obj.branch.branch_name if obj.branch_id else 'All Branches'

    def get_day(self, obj) -> str:
        return obj.date.strftime('%a')  # "Mon", "Tue", ...

    def get_mandatory_optional(self, obj) -> str:
        return 'Optional' if obj.is_optional else 'Mandatory'


class HolidayCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Holiday
        fields = ['name', 'date', 'holiday_type', 'is_optional', 'description', 'branch', 'is_active']

    def validate_date(self, value):
        if value.year < 2000:
            raise serializers.ValidationError('Date must be year 2000 or later.')
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Holiday name cannot be empty.')
        if not _HOLIDAY_NAME_RE.match(value):
            raise serializers.ValidationError(
                'Holiday name can only contain letters, spaces, apostrophes, periods, and hyphens — '
                'not just numbers or symbols.'
            )
        return value

    def validate(self, data):
        name   = (data.get('name') or (self.instance.name if self.instance else '')).strip()
        hdate  = data.get('date', self.instance.date if self.instance else None)
        branch = data.get('branch', self.instance.branch if self.instance else None)

        if self.instance:
            # Editing without touching name/date/branch must never fail this check —
            # otherwise pre-existing duplicate rows would block unrelated edits
            # (e.g. toggling is_active) to any of their own siblings forever.
            unchanged = (
                name.lower() == (self.instance.name or '').strip().lower()
                and hdate == self.instance.date
                and branch == self.instance.branch
            )
            if unchanged:
                return data

        if name and hdate:
            qs = Holiday.objects.filter(name__iexact=name, date__year=hdate.year, branch=branch)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'name': f'A holiday named "{name}" already exists for {hdate.year}.'}
                )
        return data


# ─── Carry Forward serializers ────────────────────────────────────────────────

class CarryForwardInputSerializer(serializers.Serializer):
    from_year = serializers.IntegerField(min_value=2000, max_value=2100)
    to_year   = serializers.IntegerField(min_value=2000, max_value=2100)

    def validate(self, data):
        if data['to_year'] <= data['from_year']:
            raise serializers.ValidationError({'to_year': 'to_year must be greater than from_year.'})
        return data


class CarryForwardLogSerializer(serializers.ModelSerializer):
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = CarryForwardLog
        fields = [
            'id', 'from_year', 'to_year', 'leave_type', 'executed_by_name',
            'process_mode', 'total_processed', 'total_skipped', 'total_failed',
            'is_completed', 'notes', 'created_at',
        ]

    def get_executed_by_name(self, obj):
        return obj.executed_by.full_name if obj.executed_by_id else 'System'


# ─── Separation — shared permission helper ────────────────────────────────────
# Read-only mirror of the enforcement gate in views/separation_workflow.py —
# drives the can_action/can_approve display flags. The view remains the
# authoritative check; this only has to be a faithful approximation, same as
# LeaveRequestSerializer.get_can_approve vs. leave.py's _can_approve_at_stage.

def _stage_actionable(user, sep_request, stage) -> bool:
    if not user or sep_request.employee_id == user.id or stage.status != APPROVAL_PENDING:
        return False
    earlier_pending = SeparationApprovalStage.objects.filter(
        request_id=sep_request.id, sequence__lt=stage.sequence, status=APPROVAL_PENDING,
    ).exists()
    if earlier_pending:
        return False
    if user.role and user.role.role_permissions.filter(permission__codename='settings.edit').exists():
        return True
    if stage.stage == SEP_STAGE_MANAGER:
        if stage.approver_id:
            return stage.approver_id == user.id
        has_perm = bool(
            user.role and user.role.role_permissions.filter(
                permission__codename__in={'separation.approve', 'settings.edit'}
            ).exists()
        )
        return has_perm and (not user.branch or user.branch == sep_request.employee.branch)
    if stage.stage == SEP_STAGE_BRANCH_ADMIN:
        return bool(
            user.role and user.role.can_manage_branch
            and (user.branch or '') == (sep_request.employee.branch or '')
        )
    if stage.stage == SEP_STAGE_HR:
        if stage.approver_id:
            return stage.approver_id == user.id
        has_perm = bool(
            user.role and user.role.role_permissions.filter(
                permission__codename__in={'separation.approve', 'settings.edit'}
            ).exists()
        )
        return has_perm and (not user.branch or user.branch == sep_request.employee.branch)
    return False


def _authed_user(context):
    request = context.get('request')
    if not request or not request.user or not request.user.is_authenticated:
        return None
    return request.user


# ─── Separation — Approval Stage serializer ───────────────────────────────────

class SeparationApprovalStageSerializer(serializers.ModelSerializer):
    stage_display  = serializers.CharField(source='get_stage_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approver_name  = serializers.SerializerMethodField()
    can_action     = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationApprovalStage
        fields = [
            'id', 'stage', 'stage_display', 'sequence', 'status', 'status_display',
            'approver_name', 'remarks', 'actioned_at', 'can_action',
        ]

    def get_approver_name(self, obj):
        return obj.approver.full_name if obj.approver_id else ''

    def get_can_action(self, obj):
        user = _authed_user(self.context)
        return bool(user) and _stage_actionable(user, obj.request, obj)


# ─── Separation Request serializers ───────────────────────────────────────────

class SeparationRequestSerializer(serializers.ModelSerializer):
    request_ref             = serializers.SerializerMethodField()
    employee_name           = serializers.SerializerMethodField()
    employee_code           = serializers.SerializerMethodField()
    employee_department     = serializers.SerializerMethodField()
    employee_designation    = serializers.SerializerMethodField()
    reporting_manager       = serializers.SerializerMethodField()
    created_by_name          = serializers.SerializerMethodField()
    separation_type_display = serializers.CharField(source='get_separation_type_display', read_only=True)
    reason_display           = serializers.CharField(source='get_reason_display', read_only=True)
    status_display           = serializers.SerializerMethodField()
    document_url             = serializers.SerializerMethodField()
    approval_stages           = SeparationApprovalStageSerializer(many=True, read_only=True)
    can_approve               = serializers.SerializerMethodField()
    can_cancel                = serializers.SerializerMethodField()
    can_edit                  = serializers.SerializerMethodField()
    can_delete                = serializers.SerializerMethodField()
    is_own                    = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationRequest
        fields = [
            'id', 'request_ref', 'separation_type', 'separation_type_display', 'reason', 'reason_display',
            'request_date', 'proposed_last_working_day', 'notice_period_days', 'comments',
            'status', 'status_display',
            'employee_name', 'employee_code', 'employee_department', 'employee_designation', 'reporting_manager',
            'document_url', 'created_by_name', 'approval_stages',
            'can_approve', 'can_cancel', 'can_edit', 'can_delete', 'is_own', 'created_at',
        ]

    def get_request_ref(self, obj):
        return f'SEP-{obj.request_number}' if obj.request_number else ''

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee_id else ''

    def get_employee_code(self, obj):
        return obj.employee.employee_id if obj.employee_id else ''

    def get_employee_department(self, obj):
        return obj.employee.department if obj.employee_id else ''

    def get_employee_designation(self, obj):
        return obj.employee.designation if obj.employee_id else ''

    def get_reporting_manager(self, obj):
        mgr = obj.employee.reporting_manager if obj.employee_id else None
        if not mgr:
            return None
        return {'id': mgr.employee_id, 'name': mgr.full_name}

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by_id else ''

    def get_document_url(self, obj):
        if not obj.document:
            return None
        request = self.context.get('request')
        url = obj.document.url
        return request.build_absolute_uri(url) if request else url

    def get_status_display(self, obj):
        if obj.status in (SEP_APPROVED, SEP_REJECTED, SEP_CANCELLED):
            return obj.get_status_display()
        stage = next((s for s in sorted(obj.approval_stages.all(), key=lambda s: s.sequence) if s.status == APPROVAL_PENDING), None)
        if stage:
            return f'{stage.get_stage_display().replace(" Approval", "")} Review'
        return obj.get_status_display()

    def get_can_approve(self, obj):
        user = _authed_user(self.context)
        if not user or obj.status not in (SEP_PENDING, SEP_STAGE2_PENDING):
            return False
        return any(_stage_actionable(user, obj, s) for s in obj.approval_stages.all())

    def get_can_cancel(self, obj):
        user = _authed_user(self.context)
        return bool(user and obj.employee_id == user.id and obj.status in (SEP_PENDING, SEP_STAGE2_PENDING))

    def get_can_edit(self, obj):
        return self.get_can_cancel(obj)

    def get_is_own(self, obj):
        user = _authed_user(self.context)
        return bool(user and obj.employee_id == user.id)

    def get_can_delete(self, obj):
        user = _authed_user(self.context)
        if not user or obj.employee_id == user.id or obj.status not in (SEP_PENDING, SEP_STAGE2_PENDING):
            return False
        return any(_stage_actionable(user, obj, s) for s in obj.approval_stages.all())


MAX_SEPARATION_DOC_SIZE   = 5 * 1024 * 1024
ALLOWED_SEPARATION_DOC_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}


class SeparationRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SeparationRequest
        fields = [
            'separation_type', 'reason', 'request_date', 'proposed_last_working_day',
            'notice_period_days', 'comments', 'document',
        ]

    def validate_notice_period_days(self, value):
        if value < 0:
            raise serializers.ValidationError('Notice period cannot be negative.')
        return value

    def validate_document(self, value):
        if value is None:
            return value
        if value.size > MAX_SEPARATION_DOC_SIZE:
            raise serializers.ValidationError('Document must be under 5 MB.')
        content_type = getattr(value, 'content_type', '')
        if content_type not in ALLOWED_SEPARATION_DOC_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG documents are accepted.')
        return value

    def validate(self, data):
        request_date = data.get('request_date', self.instance.request_date if self.instance else None)
        last_day     = data.get('proposed_last_working_day', self.instance.proposed_last_working_day if self.instance else None)
        if request_date and last_day and last_day < request_date:
            raise serializers.ValidationError(
                {'proposed_last_working_day': 'Proposed last working day must be on or after the request date.'}
            )
        return data


# ─── Separation — KT / Handover Task serializers ──────────────────────────────

class SeparationHandoverTaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    created_by_name   = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationHandoverTask
        fields = [
            'id', 'task', 'description', 'assigned_to', 'assigned_to_name',
            'due_date', 'is_completed', 'completed_at', 'created_by_name', 'created_at',
        ]

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.full_name if obj.assigned_to_id else ''

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by_id else ''


class SeparationHandoverTaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SeparationHandoverTask
        fields = ['task', 'description', 'assigned_to', 'due_date']

    def validate_task(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Task name is required.')
        return value


# ─── Separation — Clearance serializer ─────────────────────────────────────────

class SeparationClearanceSerializer(serializers.ModelSerializer):
    clearance_type_display = serializers.CharField(source='get_clearance_type_display', read_only=True)
    status_display          = serializers.CharField(source='get_status_display', read_only=True)
    cleared_by_name          = serializers.SerializerMethodField()
    can_action               = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationClearance
        fields = [
            'id', 'clearance_type', 'clearance_type_display', 'status', 'status_display',
            'cleared_by_name', 'remarks', 'actioned_at', 'can_action',
        ]

    def get_cleared_by_name(self, obj):
        return obj.cleared_by.full_name if obj.cleared_by_id else ''

    def get_can_action(self, obj):
        user = _authed_user(self.context)
        if not user or obj.request.employee_id == user.id or obj.status != APPROVAL_PENDING:
            return False
        if user.role and user.role.role_permissions.filter(
            permission__codename__in={'separation.approve', 'settings.edit'}
        ).exists():
            return True
        if obj.clearance_type == SEP_CLEARANCE_MANAGER:
            from apps.accounts.models import Department
            dept = Department.objects.filter(name=obj.request.employee.department).first()
            return bool(dept and dept.manager_id == user.id)
        return False


# ─── Separation — Document serializer ──────────────────────────────────────────

class SeparationDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    uploaded_by_name        = serializers.SerializerMethodField()
    file_url                = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationDocument
        fields = ['id', 'document_type', 'document_type_display', 'file_url', 'uploaded_by_name', 'created_at']

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.full_name if obj.uploaded_by_id else ''

    def get_file_url(self, obj):
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class SeparationDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SeparationDocument
        fields = ['document_type', 'file']

    def validate_file(self, value):
        if value.size > MAX_SEPARATION_DOC_SIZE:
            raise serializers.ValidationError('Document must be under 5 MB.')
        content_type = getattr(value, 'content_type', '')
        if content_type not in ALLOWED_SEPARATION_DOC_TYPES:
            raise serializers.ValidationError('Only PDF, JPG, and PNG documents are accepted.')
        return value


# ─── Separation — Activity serializer ──────────────────────────────────────────

class SeparationActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.SerializerMethodField()

    class Meta:
        model  = SeparationActivity
        fields = ['id', 'message', 'actor_name', 'actor_role', 'created_at']

    def get_actor_name(self, obj):
        return obj.actor.full_name if obj.actor_id else 'System'

    def get_actor_role(self, obj):
        return obj.actor.role.name if obj.actor_id and obj.actor.role_id else 'system'
