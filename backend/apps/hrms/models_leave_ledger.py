"""
Phase 6A Task A/C — the `LeaveType` master (fixing the defect where an
admin-created `LeavePolicy` had no matching `LeaveBalance`/`LeaveRequest`
column it could legally populate) and the append-only `LeaveTransaction`
ledger.

Additive and NOT wired as the source of truth in this pass: with
`leave.v2` not yet built, `LeaveBalance`'s existing columns remain
authoritative, written by the existing tasks.py jobs exactly as before.
`recompute_balance_cache()` here is available for callers that want to
mirror a change into the ledger (comp-off earning does, in this pass) but
is not invoked from the existing accrual/carry-forward/request-approval
code paths — see PHASE6A_REPORT.md's Task C/K notes.
"""
from __future__ import annotations

import uuid

from django.db import models


class LeaveType(models.Model):
    UNIT_DAY = 'day'
    UNIT_HOUR = 'hour'
    UNIT_CHOICES = [(UNIT_DAY, 'Day'), (UNIT_HOUR, 'Hour')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True, help_text='Matches LeavePolicy.leave_type / LeaveBalance.leave_type / LeaveRequest.leave_type.')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=UNIT_DAY)
    category = models.ForeignKey(
        'platform_core.LookupValue', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        limit_choices_to={'lookup_type__code': 'LEAVE_CATEGORY'},
    )
    is_paid = models.BooleanField(default=True)
    is_unpaid_lwp = models.BooleanField(default=False, help_text='Replaces direct comparisons against the LEAVE_LWP code constant.')
    affects_attendance_as = models.CharField(max_length=50, blank=True, help_text='Attendance status code this leave type maps to (Phase 6B hook).')
    is_comp_off = models.BooleanField(default=False)
    counts_towards_service = models.BooleanField(default=True)
    requires_balance = models.BooleanField(default=True)
    is_encashable = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False, help_text='One of the 8 original built-in codes — protected the same way _BUILTIN protected them.')
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    country = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_leave_types_v2'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.code


class LeaveTransaction(models.Model):
    TXN_OPENING = 'opening'
    TXN_ACCRUAL = 'accrual'
    TXN_PRORATION = 'proration'
    TXN_ADJUSTMENT = 'adjustment'
    TXN_AVAILED = 'availed'
    TXN_AVAILED_REVERSAL = 'availed_reversal'
    TXN_CANCELLATION = 'cancellation'
    TXN_CARRY_FORWARD_IN = 'carry_forward_in'
    TXN_CARRY_FORWARD_OUT = 'carry_forward_out'
    TXN_LAPSE = 'lapse'
    TXN_ENCASHMENT = 'encashment'
    TXN_COMP_OFF_EARNED = 'comp_off_earned'
    TXN_COMP_OFF_EXPIRED = 'comp_off_expired'
    TXN_TRANSFER_IN = 'transfer_in'
    TXN_TRANSFER_OUT = 'transfer_out'
    TXN_TYPE_CHOICES = [
        (TXN_OPENING, 'Opening'), (TXN_ACCRUAL, 'Accrual'), (TXN_PRORATION, 'Proration'),
        (TXN_ADJUSTMENT, 'Adjustment'), (TXN_AVAILED, 'Availed'), (TXN_AVAILED_REVERSAL, 'Availed reversal'),
        (TXN_CANCELLATION, 'Cancellation'), (TXN_CARRY_FORWARD_IN, 'Carry-forward in'),
        (TXN_CARRY_FORWARD_OUT, 'Carry-forward out'), (TXN_LAPSE, 'Lapse'), (TXN_ENCASHMENT, 'Encashment'),
        (TXN_COMP_OFF_EARNED, 'Comp-off earned'), (TXN_COMP_OFF_EXPIRED, 'Comp-off expired'),
        (TXN_TRANSFER_IN, 'Transfer in'), (TXN_TRANSFER_OUT, 'Transfer out'),
    ]
    # Entries that affect the year's total entitlement (today's LeaveBalance.total_days meaning).
    ENTITLEMENT_TYPES = {TXN_OPENING, TXN_ACCRUAL, TXN_PRORATION, TXN_ADJUSTMENT, TXN_CARRY_FORWARD_IN, TXN_CARRY_FORWARD_OUT, TXN_LAPSE}
    # Entries that affect today's LeaveBalance.used_days meaning (positive = more used).
    USAGE_TYPES = {TXN_AVAILED, TXN_AVAILED_REVERSAL, TXN_CANCELLATION}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='leave_transactions')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='transactions')
    leave_year = models.PositiveIntegerField(help_text='Calendar year, matching LeaveBalance.year (Task E leave-year configurability deferred).')
    txn_type = models.CharField(max_length=30, choices=TXN_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=6, decimal_places=2, help_text='Signed — positive credits the balance, negative debits it.')
    effective_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True, help_text='For carry-forward and comp-off lots.')
    reason = models.CharField(max_length=255, blank=True)
    run_id = models.CharField(max_length=50, blank=True, db_index=True)
    source_content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    source_object_id = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    reversal_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_by')

    class Meta:
        db_table = 'hrms_leave_transactions'
        ordering = ['-effective_date', '-created_at']
        indexes = [models.Index(fields=['employee', 'leave_type', 'leave_year'])]

    def __str__(self):
        return f'{self.employee_id}:{self.leave_type_id} {self.txn_type} {self.quantity}'
