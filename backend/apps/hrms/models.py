import uuid
import logging

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── Leave constants ──────────────────────────────────────────────────────────

LEAVE_CASUAL    = 'casual'
LEAVE_EARNED    = 'earned'
LEAVE_SICK      = 'sick'
LEAVE_LWP       = 'lwp'
LEAVE_MATERNITY = 'maternity'
LEAVE_PATERNITY = 'paternity'

LEAVE_TYPE_CHOICES = [
    (LEAVE_CASUAL,    'Casual Leave'),
    (LEAVE_EARNED,    'Earned Leave'),
    (LEAVE_SICK,      'Sick Leave'),
    (LEAVE_LWP,       'Leave Without Pay'),
    (LEAVE_MATERNITY, 'Maternity Leave'),
    (LEAVE_PATERNITY, 'Paternity Leave'),
]

DURATION_FULL      = 'full_day'
DURATION_MORNING   = 'half_morning'
DURATION_AFTERNOON = 'half_afternoon'

DURATION_CHOICES = [
    (DURATION_FULL,      'Full Day'),
    (DURATION_MORNING,   'Half Day (Morning)'),
    (DURATION_AFTERNOON, 'Half Day (Afternoon)'),
]

REQ_PENDING    = 'pending'
REQ_L2_PENDING = 'l2_pending'
REQ_APPROVED   = 'approved'
REQ_REJECTED   = 'rejected'
REQ_CANCELLED  = 'cancelled'

REQUEST_STATUS_CHOICES = [
    (REQ_PENDING,    'Pending'),
    (REQ_L2_PENDING, 'L2 Pending'),
    (REQ_APPROVED,   'Approved'),
    (REQ_REJECTED,   'Rejected'),
    (REQ_CANCELLED,  'Cancelled'),
]

APPROVAL_PENDING  = 'pending'
APPROVAL_APPROVED = 'approved'
APPROVAL_REJECTED = 'rejected'

APPROVAL_STATUS_CHOICES = [
    (APPROVAL_PENDING,  'Pending'),
    (APPROVAL_APPROVED, 'Approved'),
    (APPROVAL_REJECTED, 'Rejected'),
]

CATEGORY_TRAVEL    = 'travel'
CATEGORY_MEALS     = 'meals'
CATEGORY_EQUIPMENT = 'equipment'
CATEGORY_OTHER     = 'other'

STATUS_PENDING  = 'pending'
STATUS_APPROVED = 'approved'
STATUS_REJECTED = 'rejected'


class Expense(models.Model):
    CATEGORY_CHOICES = [
        (CATEGORY_TRAVEL,    'Travel'),
        (CATEGORY_MEALS,     'Meals'),
        (CATEGORY_EQUIPMENT, 'Equipment'),
        (CATEGORY_OTHER,     'Other'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_number = models.PositiveIntegerField(unique=True, null=True, blank=True, db_index=True)
    employee       = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='expenses',
    )
    branch       = models.ForeignKey(
        'branch.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
    )
    title        = models.CharField(max_length=200)
    category     = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount       = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    description  = models.TextField(blank=True, default='')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_expense'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.title} — {self.employee.full_name}'


class ExpenseReceipt(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense    = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='receipts')
    file       = models.FileField(upload_to='expenses/receipts/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_expense_receipt'

    def __str__(self) -> str:
        return f'Receipt for {self.expense.title}'


# ─── Holiday Calendar ─────────────────────────────────────────────────────────

HOLIDAY_TYPE_CHOICES = [
    ('national', 'National Holiday'),
    ('regional', 'Regional Holiday'),
    ('company',  'Company Holiday'),
]


class Holiday(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=200)
    date         = models.DateField(db_index=True)
    holiday_type = models.CharField(max_length=20, choices=HOLIDAY_TYPE_CHOICES, default='national')
    is_optional  = models.BooleanField(default=False, help_text='Optional/restricted holiday — employee can choose to take it.')
    description  = models.TextField(blank=True, default='')
    branch       = models.ForeignKey(
        'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='holidays',
        help_text='Leave blank for a company-wide holiday.',
    )
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_holidays'
        ordering = ['date']

    def __str__(self) -> str:
        return f'{self.name} ({self.date})'


# ─── Leave Policy ─────────────────────────────────────────────────────────────

GENDER_CHOICES = [('all', 'All'), ('male', 'Male'), ('female', 'Female')]


class LeavePolicy(models.Model):
    # ── Type & Credit ──
    leave_type             = models.CharField(max_length=50, unique=True)
    leave_type_label       = models.CharField(max_length=100, blank=True, default='')
    annual_days            = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    can_carry_forward      = models.BooleanField(default=False)
    max_carry_forward_days = models.PositiveIntegerField(default=0)
    policy_note            = models.TextField(blank=True, default='')
    is_active              = models.BooleanField(default=True)

    # ── Leave Application Rules ──
    minimum_leave_duration   = models.DecimalField(max_digits=4, decimal_places=1, default=0.5)
    maximum_leave_duration   = models.PositiveIntegerField(default=0)   # 0 = unlimited
    maximum_consecutive_days = models.PositiveIntegerField(default=0)   # 0 = unlimited
    minimum_notice_period    = models.PositiveIntegerField(default=0)   # days advance
    allow_half_day           = models.BooleanField(default=True)
    allow_backdated_leave    = models.BooleanField(default=False)
    maximum_backdated_days   = models.PositiveIntegerField(default=0)   # 0 = unlimited
    allow_future_leave       = models.BooleanField(default=True)
    maximum_future_days      = models.PositiveIntegerField(default=0)   # 0 = unlimited

    # ── Holiday & Week-off Rules ──
    sandwich_leave_enabled   = models.BooleanField(default=False)
    count_holidays_as_leave  = models.BooleanField(default=False)
    count_weekoffs_as_leave  = models.BooleanField(default=False)

    # ── Eligibility Rules ──
    applicable_branches         = models.JSONField(default=list, blank=True)
    applicable_departments      = models.JSONField(default=list, blank=True)
    applicable_designations     = models.JSONField(default=list, blank=True)
    applicable_employment_types = models.JSONField(default=list, blank=True)
    applicable_gender           = models.CharField(max_length=10, choices=GENDER_CHOICES, default='all')
    minimum_service_period      = models.PositiveIntegerField(default=0)  # months

    # ── Documentation Rules ──
    attachment_required            = models.BooleanField(default=False)
    medical_certificate_required   = models.BooleanField(default=False)
    medical_certificate_after_days = models.PositiveIntegerField(default=3)

    # ── Leave Restrictions ──
    allow_negative_balance     = models.BooleanField(default=False)
    convert_to_lop             = models.BooleanField(default=False)
    allow_leave_cancellation   = models.BooleanField(default=True)
    cancellation_allowed_until = models.PositiveIntegerField(default=0)  # days before start

    # ── Additional Rules ──
    allow_probation_leave     = models.BooleanField(default=False)
    allow_notice_period_leave = models.BooleanField(default=False)
    allow_leave_extension     = models.BooleanField(default=False)
    allow_leave_combination   = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_leave_policies'

    def __str__(self) -> str:
        label = self.leave_type_label or dict(LEAVE_TYPE_CHOICES).get(self.leave_type, self.leave_type)
        return f'{label} — {self.annual_days}d/yr'


# ─── Leave Balance ────────────────────────────────────────────────────────────

class LeaveBalance(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee         = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='leave_balances')
    leave_type       = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    year             = models.PositiveIntegerField()
    total_days       = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days        = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carried_forward  = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table      = 'hrms_leave_balances'
        unique_together = ('employee', 'leave_type', 'year')

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.leave_type} {self.year}'

    @property
    def available_days(self):
        return self.total_days - self.used_days


# ─── Leave Request ────────────────────────────────────────────────────────────

class LeaveRequest(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee   = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)
    duration   = models.CharField(max_length=20, choices=DURATION_CHOICES, default=DURATION_FULL)
    start_date = models.DateField()
    end_date   = models.DateField()
    total_days = models.DecimalField(max_digits=4, decimal_places=1)
    lop_days   = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    reason     = models.TextField()
    status     = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default=REQ_PENDING, db_index=True)
    is_lwp     = models.BooleanField(default=False)

    # L1 approval
    l1_approver    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l1_leave_approvals',
    )
    l1_status      = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, null=True, blank=True)
    l1_remarks     = models.TextField(blank=True, default='')
    l1_actioned_at = models.DateTimeField(null=True, blank=True)

    # L2 approval
    l2_approver    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l2_leave_approvals',
    )
    l2_status      = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, null=True, blank=True)
    l2_remarks     = models.TextField(blank=True, default='')
    l2_actioned_at = models.DateTimeField(null=True, blank=True)

    # Handover & contact
    contact_during_leave = models.CharField(max_length=30, blank=True, default='')
    handover_to          = models.CharField(max_length=150, blank=True, default='')
    handover_notes       = models.TextField(blank=True, default='')

    document   = models.FileField(upload_to='leave_documents/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_leave_requests'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.leave_type} ({self.start_date})'
