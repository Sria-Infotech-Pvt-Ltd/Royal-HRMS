import logging
import re

from rest_framework import serializers

from .models import (
    Expense, ExpenseReceipt,
    Holiday, HOLIDAY_TYPE_CHOICES,
    LeaveBalance, LeavePolicy, LeaveRequest,
    LEAVE_LWP, LEAVE_TYPE_CHOICES, DURATION_CHOICES,
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
        raise serializers.ValidationError(f'Each receipt must be under 5 MB.')
    content_type = getattr(file, 'content_type', '')
    if content_type not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError('Only PDF, JPG, and PNG receipts are accepted.')


# ─── Leave serializers ────────────────────────────────────────────────────────

_LEAVE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z -]*$")

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

    class Meta:
        model  = LeavePolicy
        fields = (
            ['id', 'leave_type', 'leave_type_display', 'annual_days', 'can_carry_forward',
             'max_carry_forward_days', 'policy_note', 'is_active']
            + _POLICY_RULE_FIELDS
            + ['updated_at']
        )

    def get_leave_type_display(self, obj) -> str:
        if obj.leave_type_label:
            return obj.leave_type_label
        return dict(LEAVE_TYPE_CHOICES).get(obj.leave_type, obj.leave_type.replace('_', ' ').title())


class LeavePolicyCreateSerializer(serializers.Serializer):
    leave_type_label       = serializers.CharField(max_length=100)
    annual_days            = serializers.DecimalField(max_digits=5, decimal_places=1, default=0)
    can_carry_forward      = serializers.BooleanField(default=False)
    max_carry_forward_days = serializers.IntegerField(default=0, min_value=0)
    policy_note            = serializers.CharField(required=False, default='', allow_blank=True)
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
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Display name cannot be empty.')
        if not _LEAVE_NAME_RE.match(value):
            raise serializers.ValidationError(
                'Display name can only contain letters, spaces, and hyphens — no numbers or special characters.'
            )
        key = value.lower().replace(' ', '_').replace('-', '_')
        if LeavePolicy.objects.filter(leave_type=key).exists():
            raise serializers.ValidationError('A leave type with this name already exists.')
        return value

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
    class Meta:
        model  = LeavePolicy
        fields = (
            ['annual_days', 'can_carry_forward', 'max_carry_forward_days', 'policy_note', 'is_active']
            + _POLICY_RULE_FIELDS
        )

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
            'year', 'total_days', 'used_days', 'carried_forward', 'available_days',
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
