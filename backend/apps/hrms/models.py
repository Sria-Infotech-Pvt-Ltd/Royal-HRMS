import uuid
import logging

from django.db import models

from core.storage import (
    AuthenticatedRawMediaCloudinaryStorage,
    expense_receipt_upload_path,
    leave_document_upload_path,
    separation_document_upload_path,
    separation_request_upload_path,
)

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

# The 6 seeded leave types every company gets by default — never deletable
# (only deactivatable), unlike a custom LeavePolicy an admin created later.
BUILTIN_LEAVE_TYPE_KEYS = {
    LEAVE_CASUAL, LEAVE_EARNED, LEAVE_SICK, LEAVE_LWP, LEAVE_MATERNITY, LEAVE_PATERNITY,
}

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
    # Set when this expense is paid out via a payroll payslip
    disbursed_in_payslip = models.ForeignKey(
        'payroll.EmployeePayslip',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='disbursed_expenses',
    )
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
    file       = models.FileField(upload_to=expense_receipt_upload_path, storage=AuthenticatedRawMediaCloudinaryStorage())
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

CARRY_FORWARD_LIMITED   = 'limited'
CARRY_FORWARD_UNLIMITED = 'unlimited'
CARRY_FORWARD_TYPE_CHOICES = [
    (CARRY_FORWARD_LIMITED,   'Limited'),
    (CARRY_FORWARD_UNLIMITED, 'Unlimited'),
]

CARRY_FORWARD_AUTO   = 'automatic'
CARRY_FORWARD_MANUAL = 'manual'
CARRY_FORWARD_MODE_CHOICES = [
    (CARRY_FORWARD_AUTO,   'Automatic'),
    (CARRY_FORWARD_MANUAL, 'Manual'),
]

GENDER_CHOICES = [('all', 'All'), ('male', 'Male'), ('female', 'Female')]


class LeavePolicy(models.Model):
    # ── Type & Credit ──
    leave_type             = models.CharField(max_length=50, unique=True)
    leave_type_label       = models.CharField(max_length=100, blank=True, default='')
    annual_days            = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    can_carry_forward         = models.BooleanField(default=False)
    max_carry_forward_days    = models.PositiveIntegerField(default=0)
    carry_forward_type        = models.CharField(max_length=20, choices=CARRY_FORWARD_TYPE_CHOICES, default=CARRY_FORWARD_LIMITED)
    carry_forward_mode        = models.CharField(max_length=20, choices=CARRY_FORWARD_MODE_CHOICES, default=CARRY_FORWARD_AUTO)
    carry_forward_expiry_days = models.PositiveIntegerField(default=0, help_text='Days before carry-forwarded balance expires. 0 = never.')
    policy_note               = models.TextField(blank=True, default='')
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
    total_days                = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days                 = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carried_forward           = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carry_forward_expiry_date = models.DateField(null=True, blank=True)
    created_at                = models.DateTimeField(auto_now_add=True)
    updated_at                = models.DateTimeField(auto_now=True)

    class Meta:
        db_table      = 'hrms_leave_balances'
        unique_together = ('employee', 'leave_type', 'year')

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.leave_type} {self.year}'

    @property
    def available_days(self):
        return self.total_days - self.used_days


# ─── Carry Forward Log ───────────────────────────────────────────────────────

class CarryForwardLog(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_year       = models.PositiveIntegerField()
    to_year         = models.PositiveIntegerField()
    leave_type      = models.CharField(max_length=50, blank=True, default='')
    executed_by     = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='carry_forward_executions',
    )
    process_mode    = models.CharField(max_length=20, default='execute')
    total_processed = models.PositiveIntegerField(default=0)
    total_skipped   = models.PositiveIntegerField(default=0)
    total_failed    = models.PositiveIntegerField(default=0)
    is_completed    = models.BooleanField(default=False)
    notes           = models.TextField(blank=True, default='')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_carry_forward_logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        by = self.executed_by.full_name if self.executed_by_id else 'System'
        return f'CarryForward {self.from_year}→{self.to_year} by {by}'


# ─── Separation Request ───────────────────────────────────────────────────────

SEPARATION_RESIGNATION  = 'resignation'
SEPARATION_RETIREMENT   = 'retirement'
SEPARATION_OTHER        = 'other'

SEPARATION_TYPE_CHOICES = [
    (SEPARATION_RESIGNATION,  'Resignation'),
    (SEPARATION_RETIREMENT,   'Retirement'),
    (SEPARATION_OTHER,        'Other'),
]

SEPARATION_REASON_CHOICES = [
    ('better_career_opportunity', 'Better Career Opportunity'),
    ('personal_reason',           'Personal Reason'),
    ('higher_education',          'Higher Education'),
    ('relocation',                'Relocation'),
    ('compensation',              'Compensation'),
    ('health_family',             'Health / Family'),
    ('other',                     'Other'),
]

SEP_PENDING        = 'pending'         # awaiting the chain's 1st stage (see _resolve_separation_chain)
SEP_STAGE2_PENDING = 'stage2_pending'  # 1st stage approved, awaiting the 2nd (never reached for a 1-stage chain)
SEP_APPROVED       = 'approved'
SEP_REJECTED       = 'rejected'
SEP_CANCELLED      = 'cancelled'

SEPARATION_STATUS_CHOICES = [
    (SEP_PENDING,        'Pending'),
    (SEP_STAGE2_PENDING, 'Stage 2 Pending'),
    (SEP_APPROVED,       'Approved'),
    (SEP_REJECTED,       'Rejected'),
    (SEP_CANCELLED,      'Cancelled'),
]


class SeparationRequest(models.Model):
    id                        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number            = models.PositiveIntegerField(unique=True, null=True, blank=True, db_index=True)
    employee                  = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='separation_requests')
    separation_type           = models.CharField(max_length=20, choices=SEPARATION_TYPE_CHOICES)
    reason                    = models.CharField(max_length=30, choices=SEPARATION_REASON_CHOICES)
    request_date              = models.DateField()
    proposed_last_working_day = models.DateField()
    notice_period_days        = models.PositiveIntegerField(default=30)
    comments                  = models.TextField(blank=True, default='')
    document                  = models.FileField(upload_to=separation_request_upload_path, storage=AuthenticatedRawMediaCloudinaryStorage(), null=True, blank=True)
    status                    = models.CharField(max_length=20, choices=SEPARATION_STATUS_CHOICES, default=SEP_PENDING, db_index=True)

    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_requests_filed',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_separation_requests'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.separation_type} ({self.proposed_last_working_day})'


# ─── Separation — Approval Stages ─────────────────────────────────────────────
# Two-stage chain, always in this order:
#   1. HR Approval        — the employee's assigned HR (User.hr); falls back to
#                            any separation.approve holder in the employee's
#                            branch when no HR is assigned (unresolved approver).
#   2. Manager Approval    — the employee's Department.manager — OR, when the
#      / Branch Admin Approval  department has no manager or the employee IS
#                            that department's manager (can't approve their own
#                            exit), escalates to Branch Admin (role.can_manage_branch,
#                            same branch) instead — unresolved approver, any
#                            matching branch admin may act.

SEP_STAGE_HR           = 'hr'
SEP_STAGE_MANAGER      = 'manager'
SEP_STAGE_BRANCH_ADMIN = 'branch_admin'

SEP_STAGE_CHOICES = [
    (SEP_STAGE_HR,           'HR Approval'),
    (SEP_STAGE_MANAGER,      'Manager Approval'),
    (SEP_STAGE_BRANCH_ADMIN, 'Branch Admin Approval'),
]


class SeparationApprovalStage(models.Model):
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request  = models.ForeignKey(SeparationRequest, on_delete=models.CASCADE, related_name='approval_stages')
    stage    = models.CharField(max_length=20, choices=SEP_STAGE_CHOICES)
    sequence = models.PositiveSmallIntegerField()  # 1, 2 — action order

    # Left null when the stage resolves to a role/branch rather than one
    # specific person (e.g. an unassigned HR, or the branch-admin fallback).
    approver = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_approval_stages',
    )
    status      = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default=APPROVAL_PENDING)
    remarks     = models.TextField(blank=True, default='')
    actioned_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hrms_separation_approval_stages'
        ordering        = ['request', 'sequence']
        unique_together = ('request', 'sequence')

    def __str__(self) -> str:
        return f'{self.request_id} — {self.stage} ({self.status})'


# ─── Separation — KT / Handover Tasks ─────────────────────────────────────────

class SeparationHandoverTask(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request      = models.ForeignKey(SeparationRequest, on_delete=models.CASCADE, related_name='handover_tasks')
    task         = models.CharField(max_length=200)
    description  = models.TextField(blank=True, default='')
    assigned_to  = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_handover_tasks',
    )
    due_date      = models.DateField(null=True, blank=True)
    is_completed  = models.BooleanField(default=False)
    completed_at  = models.DateTimeField(null=True, blank=True)
    created_by    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_handover_tasks_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_separation_handover_tasks'
        ordering = ['is_completed', 'due_date', 'created_at']

    def __str__(self) -> str:
        return f'{self.task} ({self.request_id})'


# ─── Separation — Clearances ───────────────────────────────────────────────────
# Fixed set of 4, auto-created alongside the SeparationRequest.

SEP_CLEARANCE_MANAGER = 'manager'
SEP_CLEARANCE_IT       = 'it'
SEP_CLEARANCE_FINANCE  = 'finance'
SEP_CLEARANCE_HR       = 'hr'

SEP_CLEARANCE_TYPE_CHOICES = [
    (SEP_CLEARANCE_MANAGER, 'Manager Clearance'),
    (SEP_CLEARANCE_IT,      'IT Clearance'),
    (SEP_CLEARANCE_FINANCE, 'Finance Clearance'),
    (SEP_CLEARANCE_HR,      'HR Clearance'),
]


class SeparationClearance(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request         = models.ForeignKey(SeparationRequest, on_delete=models.CASCADE, related_name='clearances')
    clearance_type  = models.CharField(max_length=20, choices=SEP_CLEARANCE_TYPE_CHOICES)
    status          = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default=APPROVAL_PENDING)
    cleared_by      = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_clearances_given',
    )
    remarks     = models.TextField(blank=True, default='')
    actioned_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hrms_separation_clearances'
        ordering        = ['clearance_type']
        unique_together = ('request', 'clearance_type')

    def __str__(self) -> str:
        return f'{self.request_id} — {self.clearance_type} ({self.status})'


# ─── Separation — Documents ────────────────────────────────────────────────────

SEP_DOC_RESIGNATION_LETTER  = 'resignation_letter'
SEP_DOC_RELIEVING_LETTER    = 'relieving_letter'
SEP_DOC_EXPERIENCE_LETTER   = 'experience_letter'
SEP_DOC_FULL_FINAL_STATEMENT = 'full_final_statement'
SEP_DOC_NDA                  = 'nda'
SEP_DOC_OTHER                = 'other'

SEP_DOCUMENT_TYPE_CHOICES = [
    (SEP_DOC_RESIGNATION_LETTER,   'Resignation Letter'),
    (SEP_DOC_RELIEVING_LETTER,     'Relieving Letter'),
    (SEP_DOC_EXPERIENCE_LETTER,    'Experience Letter'),
    (SEP_DOC_FULL_FINAL_STATEMENT, 'Full & Final Statement'),
    (SEP_DOC_NDA,                  'NDA / Undertaking'),
    (SEP_DOC_OTHER,                'Other'),
]


class SeparationDocument(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request        = models.ForeignKey(SeparationRequest, on_delete=models.CASCADE, related_name='documents')
    document_type  = models.CharField(max_length=30, choices=SEP_DOCUMENT_TYPE_CHOICES, default=SEP_DOC_OTHER)
    file           = models.FileField(upload_to=separation_document_upload_path, storage=AuthenticatedRawMediaCloudinaryStorage())
    uploaded_by    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_documents_uploaded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_separation_documents'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.get_document_type_display()} ({self.request_id})'


# ─── Separation — Activity Log ─────────────────────────────────────────────────

class SeparationActivity(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request    = models.ForeignKey(SeparationRequest, on_delete=models.CASCADE, related_name='activities')
    actor      = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='separation_activities',
    )
    message    = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_separation_activities'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.message


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

    document   = models.FileField(upload_to=leave_document_upload_path, storage=AuthenticatedRawMediaCloudinaryStorage(), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_leave_requests'
        ordering = ['-created_at']
        indexes = [
            # Phase 4: matches the dominant repeated query shape across the
            # codebase — the leave-overlap check, absence detection, monthly
            # working-days calc, and manager/HR dashboards all filter by
            # employee + status(__in) + a start_date/end_date range. Today
            # only `employee` (FK auto-index) and `status` (standalone) exist
            # separately, with no composite covering all four together.
            models.Index(
                fields=['employee', 'status', 'start_date', 'end_date'],
                name='leave_emp_status_dates_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.leave_type} ({self.start_date})'


def leave_type_usage(leave_type: str) -> dict:
    """
    Whether a leave_type has any existing employee data attached to it, and
    how much — used to decide whether deleting its LeavePolicy is safe.

    LeaveBalance.leave_type and LeaveRequest.leave_type are both plain
    CharFields, not a ForeignKey to LeavePolicy — so deleting a LeavePolicy
    row never cascades to or corrupts either table. But it does orphan them:
    an existing balance/request for that type would be left with no backing
    policy configuration, silently dropping out of allocation/sync (every
    LeaveBalance-creating path filters LeavePolicy.objects.filter(is_active=
    True)) and out of leave-application validation (LeavePolicyCacheService.
    get() would return None for it). That's treated as "in use" and blocking
    deletion, not a safe cascade to implement.
    """
    balance_qs = LeaveBalance.objects.filter(leave_type=leave_type)
    request_qs = LeaveRequest.objects.filter(leave_type=leave_type)
    balance_count = balance_qs.count()
    request_count = request_qs.count()

    employee_ids = set(balance_qs.values_list('employee_id', flat=True))
    employee_ids.update(request_qs.values_list('employee_id', flat=True))

    return {
        'in_use':                  balance_count > 0 or request_count > 0,
        'affected_employee_count': len(employee_ids),
        'leave_balance_count':     balance_count,
        'leave_request_count':     request_count,
    }


# ─── Work From Home Request ────────────────────────────────────────────────────

class WorkFromHomeRequest(models.Model):
    """
    Employee-submitted request to work from a declared location for a date
    range. Approval follows the same L1/L2 chain as LeaveRequest (see
    apps.accounts.services_approval) — deliberately shaped like LeaveRequest
    minus the leave-specific fields (balance, policy, document, handover).

    latitude/longitude are captured via the browser's own Geolocation API at
    submit time, not a typed address — this app has no geocoding integration
    anywhere (Branch geofencing itself is plain manually-entered lat/long,
    see apps/branch/models.py), so there's no existing "address -> coordinates"
    path to reuse, and adding one would be new infrastructure for a feature
    that doesn't need it. The saved point is what a later WFH punch's GPS is
    validated against (services_geofencing.py's wfh strategy), the same way
    an office punch is validated against its Branch's saved point.
    """
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee     = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='wfh_requests')
    start_date   = models.DateField()
    end_date     = models.DateField()
    reason       = models.TextField(blank=True, default='')
    location_label = models.CharField(max_length=150, blank=True, default='')
    latitude     = models.DecimalField(max_digits=9, decimal_places=6)
    longitude    = models.DecimalField(max_digits=9, decimal_places=6)
    status       = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default=REQ_PENDING, db_index=True)

    # L1 approval
    l1_approver    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l1_wfh_approvals',
    )
    l1_status      = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, null=True, blank=True)
    l1_remarks     = models.TextField(blank=True, default='')
    l1_actioned_at = models.DateTimeField(null=True, blank=True)

    # L2 approval
    l2_approver    = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l2_wfh_approvals',
    )
    l2_status      = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, null=True, blank=True)
    l2_remarks     = models.TextField(blank=True, default='')
    l2_actioned_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_wfh_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['employee', 'status', 'start_date', 'end_date'],
                name='wfh_emp_status_dates_idx',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.employee.full_name} — WFH ({self.start_date} to {self.end_date})'

    @classmethod
    def approved_for(cls, employee, for_date):
        """The approved WFH request (if any) covering this employee on this
        date. Single lookup shared by punch-time geofence validation
        (services_geofencing.py) and day processing (services_attendance.py)
        so both agree on what "today is a WFH day" means."""
        return (
            cls.objects
            .filter(employee=employee, status=REQ_APPROVED, start_date__lte=for_date, end_date__gte=for_date)
            .order_by('-created_at')
            .first()
        )


# ─── WFH Saved Location ─────────────────────────────────────────────────────────

class WFHSavedLocation(models.Model):
    """
    An employee's own reusable WFH location (e.g. "Home", "Co-working space"),
    so they don't have to re-run the browser's Geolocation API and re-capture
    the same coordinates on every request. Purely a per-employee convenience
    list — has no bearing on WorkFromHomeRequest's own latitude/longitude,
    which is still copied in as plain values at submit time (see
    WorkFromHomeRequest's docstring for why there's no live address/geocoding
    integration to hook into instead).
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee   = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='wfh_saved_locations')
    label      = models.CharField(max_length=100)
    latitude   = models.DecimalField(max_digits=9, decimal_places=6)
    longitude  = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hrms_wfh_saved_locations'
        ordering        = ['label']
        unique_together = ('employee', 'label')

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.label}'
