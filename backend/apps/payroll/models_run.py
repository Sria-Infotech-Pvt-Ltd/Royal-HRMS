"""
Phase 7B Task B — configurable payroll run lifecycle.

Scoped down from the master prompt's full stage-registry design: a
`RunStageTemplate` holds an ORDERED LIST of stage codes (plain strings,
validated against a fixed registry in services_run.py) rather than a
separate stage-handler-plugin system — real and functioning, but simpler
than a full pluggable registry UI. `RunVersion` gives real versioned
recalculation with a diff; finalisation is a real, enforced one-way state
transition (no RunVersion can be added to a finalised run — checked in
services_run.py, not just documented).

Not wired into real payroll processing — PayrollCycle/process_payroll_cycle
remain completely untouched; PayrollRun is additive, optionally linked to
a PayrollCycle via `cycle` for cross-reference.
"""
import uuid

from django.db import models


class RunStageTemplate(models.Model):
    """One ordered stage list, assignable to a PayGroup. Stage codes are
    validated against services_run.STAGE_REGISTRY, not stored as FKs to a
    separate Stage model — see that module's own docstring for why."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    pay_group = models.ForeignKey(
        'payroll.PayGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='stage_templates',
        help_text='Blank = usable by any pay group.',
    )
    stage_codes = models.JSONField(default=list, help_text='Ordered list of stage codes from services_run.STAGE_REGISTRY.')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_run_stage_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class PayrollRun(models.Model):
    TYPE_REGULAR           = 'regular'
    TYPE_OFF_CYCLE_BONUS   = 'off_cycle_bonus'
    TYPE_OFF_CYCLE_CORR    = 'off_cycle_correction'
    TYPE_REVERSAL          = 'reversal'
    TYPE_ARREARS           = 'arrears'
    TYPE_FINAL_SETTLEMENT  = 'final_settlement'
    TYPE_OTHER             = 'other'
    RUN_TYPE_CHOICES = [
        (TYPE_REGULAR,          'Regular'),
        (TYPE_OFF_CYCLE_BONUS,  'Off-cycle: Bonus'),
        (TYPE_OFF_CYCLE_CORR,   'Off-cycle: Correction'),
        (TYPE_REVERSAL,         'Reversal'),
        (TYPE_ARREARS,          'Arrears'),
        (TYPE_FINAL_SETTLEMENT, 'Final Settlement'),
        (TYPE_OTHER,            'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pay_group = models.ForeignKey('payroll.PayGroup', on_delete=models.PROTECT, related_name='runs')
    period = models.ForeignKey('payroll.PayPeriod', on_delete=models.PROTECT, related_name='runs')
    run_type = models.CharField(max_length=30, choices=RUN_TYPE_CHOICES, default=TYPE_REGULAR)
    reference_number = models.CharField(max_length=60, unique=True, blank=True)
    stage_template = models.ForeignKey(RunStageTemplate, on_delete=models.PROTECT, related_name='runs')
    # Index into stage_template.stage_codes — "which stage is this run
    # currently at". -1 = not yet started.
    current_stage_index = models.IntegerField(default=-1)
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)

    # Compatibility link — the PayrollCycle this run represents, if any.
    cycle = models.ForeignKey('payroll.PayrollCycle', on_delete=models.SET_NULL, null=True, blank=True, related_name='runs')
    parent_run = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_runs')

    created_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='payroll_runs_created')
    employee = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_runs_for_employee',
        help_text='Set for a single-employee run (e.g. final_settlement). Blank = a normal multi-employee run.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_runs_v2'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference_number or f'Run {self.id}'

    @property
    def current_stage_code(self):
        codes = self.stage_template.stage_codes
        if 0 <= self.current_stage_index < len(codes):
            return codes[self.current_stage_index]
        return None


class RunVersion(models.Model):
    """One versioned recalculation of a run. `results` is a snapshot dict
    (employee_id -> computed fields) — a lightweight versioned snapshot,
    not a full duplicate PayslipLine mirror table (that already exists at
    the real-payslip level via Task E's PayslipLine; this is the RUN-level
    recompute-and-diff record Task B.3 asks for)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    results = models.JSONField(default=dict, help_text='{employee_id: {component_code: amount}} snapshot for this version.')
    affected_employee_ids = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='run_versions_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_run_versions_v2'
        unique_together = [('run', 'version_number')]
        ordering = ['run', '-version_number']

    def __str__(self):
        return f'{self.run_id} v{self.version_number}'
