import logging

from rest_framework import serializers

from .models import (
    Expense, ExpenseReceipt,
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

class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)

    class Meta:
        model  = LeavePolicy
        fields = [
            'id', 'leave_type', 'leave_type_display',
            'annual_days', 'can_carry_forward', 'max_carry_forward_days',
            'policy_note', 'is_active', 'updated_at',
        ]


class LeavePolicyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeavePolicy
        fields = ['annual_days', 'can_carry_forward', 'max_carry_forward_days', 'policy_note', 'is_active']

    def validate_annual_days(self, value):
        if value < 0:
            raise serializers.ValidationError('Annual days cannot be negative.')
        return value

    def validate_max_carry_forward_days(self, value):
        if value < 0:
            raise serializers.ValidationError('Max carry forward days cannot be negative.')
        return value


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

    class Meta:
        model  = LeaveRequest
        fields = [
            'id', 'leave_type', 'leave_type_display', 'duration', 'duration_display',
            'start_date', 'end_date', 'total_days', 'reason', 'status', 'is_lwp',
            'employee_name', 'employee_code', 'employee_dept', 'employee_branch',
            'l1_approver_name', 'l1_status', 'l1_remarks', 'l1_actioned_at',
            'l2_approver_name', 'l2_status', 'l2_remarks', 'l2_actioned_at',
            'contact_during_leave', 'handover_to', 'handover_notes',
            'document_url', 'created_at',
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
