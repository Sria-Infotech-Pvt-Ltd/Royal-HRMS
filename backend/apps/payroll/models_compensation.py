"""
Phase 7A Task D — effective-dated employee compensation.

`EmployeeCompensation` extends `EmployeeSalaryConfig` (Task C's `PayStructure`
instead of the legacy `SalaryStructure`, a `pay_frequency` field 7B will use,
and per-employee component overrides) without replacing it — every row
created through `services_compensation.create_compensation()` writes BOTH a
real `EmployeeSalaryConfig` row (so every existing reader — payroll
processing, the Hire wizard, reports — keeps working exactly as before) and
an `EmployeeCompensation` row linked to it 1:1 via `legacy_salary_config`.

Known limitation, stated plainly: this syncs only the NEW creation path.
Any `EmployeeSalaryConfig` row created directly (bulk import, admin, a
future call site that doesn't go through `create_compensation()`) has no
matching `EmployeeCompensation` row and is simply invisible to the CTC
breakup API until it is. Backfilling every historical row and retrofitting
every existing call site is real-engine-cutover work, not Task D's
"scaffolding, not yet load-bearing" scope.
"""
import uuid

from django.db import models


class EmployeeCompensation(models.Model):
    FREQ_MONTHLY = 'monthly'
    PAY_FREQUENCY_CHOICES = [(FREQ_MONTHLY, 'Monthly')]  # 7B introduces the rest

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='compensation_versions',
    )
    annual_ctc = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.ForeignKey(
        'platform_core.Currency', on_delete=models.PROTECT, null=True, blank=True,
        related_name='employee_compensations',
    )
    pay_structure = models.ForeignKey(
        'payroll.PayStructure', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_compensations',
        help_text='Blank = resolve the default published structure at evaluation time.',
    )
    pay_frequency = models.CharField(max_length=20, choices=PAY_FREQUENCY_CHOICES, default=FREQ_MONTHLY)

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    # Same REASON_* vocabulary as the legacy EmployeeSalaryConfig it's
    # written alongside — one real set of reasons, not two.
    reason = models.CharField(max_length=20, blank=True)
    reason_note = models.CharField(max_length=200, blank=True)
    linked_promotion = models.ForeignKey(
        'accounts.PromotionRecord', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='compensation_versions',
    )
    # The real EmployeeSalaryConfig row this version keeps synced with — see
    # module docstring. SET_NULL (not CASCADE): the compensation-history row
    # must survive even if the legacy row it was created alongside is later
    # deleted some other way.
    legacy_salary_config = models.OneToOneField(
        'payroll.EmployeeSalaryConfig', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='compensation_v2',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_employee_compensation_v2'
        ordering = ['-effective_from']

    def __str__(self):
        return f'{self.employee_id} — {self.annual_ctc}/yr from {self.effective_from}'

    @property
    def monthly_ctc(self):
        return self.annual_ctc / 12


class EmployeeCompensationComponent(models.Model):
    """A per-employee override of one component's calculation for this
    compensation version only — e.g. a fixed vehicle allowance this one
    employee gets that isn't in their structure at all, or a different
    percentage than the structure's default for a negotiated term."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    compensation = models.ForeignKey(EmployeeCompensation, on_delete=models.CASCADE, related_name='component_overrides')
    component_code = models.CharField(max_length=40)
    calculation_method = models.CharField(max_length=20, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    formula = models.TextField(blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'payroll_employee_compensation_components_v2'
        unique_together = [('compensation', 'component_code')]

    def __str__(self):
        return f'{self.compensation_id} › {self.component_code}'


class EmployeeRecurringComponent(models.Model):
    """A recurring employee-level earning/deduction independent of any
    compensation revision — e.g. a fixed canteen deduction or a standing
    vehicle allowance that doesn't change when CTC is revised."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='recurring_pay_components')
    component_code = models.CharField(max_length=40)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_employee_recurring_components_v2'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.employee_id} › {self.component_code} ({self.amount})'
