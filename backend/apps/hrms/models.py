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

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee     = models.ForeignKey(
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
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
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


# ─── Leave Policy ─────────────────────────────────────────────────────────────

class LeavePolicy(models.Model):
    leave_type             = models.CharField(max_length=50, unique=True)
    leave_type_label       = models.CharField(max_length=100, blank=True, default='')
    annual_days            = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    can_carry_forward      = models.BooleanField(default=False)
    max_carry_forward_days = models.PositiveIntegerField(default=0)
    policy_note            = models.TextField(blank=True, default='')
    is_active              = models.BooleanField(default=True)
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

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
    reason     = models.TextField()
    status     = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default=REQ_PENDING)
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
