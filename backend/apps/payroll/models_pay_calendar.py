"""
Phase 7B Task A — pay groups, pay frequencies, and payroll calendars.

IMPORTANT FINDING this task is built around (confirmed by direct code
reading, not assumed): today's `PayrollSettings.cycle_start_day`/
`cycle_end_day`/`pay_day` fields are vestigial — grepped the entire
backend, nothing reads them. The real `PayrollCycleListView.post()`
(apps/payroll/views/cycle_list_detail.py) takes `cycle_start`/`cycle_end`/
`pay_date` as raw strings from the request body, with zero day-of-month
derivation and zero weekend/holiday pay-date adjustment. So "reproduce
today's behavior exactly" for calendars means: preserve manual cycle
creation as the default, unconstrained path (completely untouched —
`PayrollCycleListView` is not modified by this task), and treat the actual
day-of-month → date computation + holiday-aware pay-date shifting built
here as genuinely NEW functionality, not a behavior-preserving port. This
is stated plainly rather than silently waved through as "same as before."

`PayrollCycle` gains two new NULLABLE FKs (`pay_group`, `pay_period`) so
historical cycles can be linked without changing a single existing read of
that model — see services_pay_calendar.link_historical_cycles().
"""
import uuid

from django.db import models


class PayrollCalendar(models.Model):
    FREQ_MONTHLY      = 'monthly'
    FREQ_SEMI_MONTHLY = 'semi_monthly'
    FREQ_BI_WEEKLY    = 'bi_weekly'
    FREQ_WEEKLY       = 'weekly'
    FREQ_DAILY        = 'daily'
    FREQUENCY_CHOICES = [
        (FREQ_MONTHLY,      'Monthly'),
        (FREQ_SEMI_MONTHLY, 'Semi-monthly'),
        (FREQ_BI_WEEKLY,    'Bi-weekly'),
        (FREQ_WEEKLY,       'Weekly'),
        (FREQ_DAILY,        'Daily'),
    ]

    ADJUST_NONE     = 'none'
    ADJUST_PREVIOUS = 'previous_working_day'
    ADJUST_NEXT     = 'next_working_day'
    ADJUSTMENT_CHOICES = [
        (ADJUST_NONE,     'No adjustment'),
        (ADJUST_PREVIOUS, 'Shift to previous working day'),
        (ADJUST_NEXT,     'Shift to next working day'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    legal_entity = models.ForeignKey(
        'platform_core.LegalEntity', on_delete=models.PROTECT, null=True, blank=True,
        related_name='payroll_calendars',
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default=FREQ_MONTHLY)

    # Monthly/semi-monthly only — the exact fields PayrollSettings already
    # declared but never wired to anything; wired for real here.
    cycle_start_day = models.PositiveSmallIntegerField(default=25, help_text='Day of month the period starts.')
    cycle_end_day = models.PositiveSmallIntegerField(default=24, help_text='Day of month the period ends, in the following month.')
    pay_day = models.PositiveSmallIntegerField(default=30, help_text='Day of month pay is credited, in the period-end month.')

    # Weekly/bi-weekly/daily only — an anchor date so period boundaries are
    # deterministic regardless of which year generate_periods() is asked for.
    anchor_date = models.DateField(null=True, blank=True)
    period_length_days = models.PositiveSmallIntegerField(null=True, blank=True)

    pay_date_adjustment_rule = models.CharField(max_length=30, choices=ADJUSTMENT_CHOICES, default=ADJUST_PREVIOUS)
    # Scope the weekend/holiday check to one branch (matches Holiday's own
    # nullable branch FK — None = company-wide holidays only).
    branch = models.ForeignKey(
        'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_calendars',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_calendars_v2'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} ({self.get_frequency_display()})'


class PayPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar = models.ForeignKey(PayrollCalendar, on_delete=models.CASCADE, related_name='periods')
    period_start = models.DateField()
    period_end = models.DateField()
    raw_pay_date = models.DateField(help_text='Pay date before weekend/holiday adjustment.')
    pay_date = models.DateField(help_text='Pay date after the calendar\'s adjustment rule.')

    attendance_cutoff_date = models.DateField(null=True, blank=True)
    input_cutoff_date = models.DateField(null=True, blank=True)
    approval_cutoff_date = models.DateField(null=True, blank=True)

    financial_year_start = models.PositiveIntegerField()
    is_closed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_pay_periods_v2'
        unique_together = [('calendar', 'period_start', 'period_end')]
        ordering = ['calendar', 'period_start']

    def __str__(self):
        return f'{self.calendar.code}: {self.period_start}..{self.period_end} (pay {self.pay_date})'


class PayGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    legal_entity = models.ForeignKey(
        'platform_core.LegalEntity', on_delete=models.PROTECT, null=True, blank=True, related_name='pay_groups',
    )
    currency = models.ForeignKey(
        'platform_core.Currency', on_delete=models.PROTECT, null=True, blank=True, related_name='pay_groups',
    )
    calendar = models.ForeignKey(PayrollCalendar, on_delete=models.PROTECT, related_name='pay_groups')
    # Nullable branch scope — same convention PayrollCycle.branch already
    # uses (None = company-wide). A policy-based "membership" scope (the
    # master prompt's PAY_GROUP policy type) is deferred — see Task A report.
    branch = models.ForeignKey(
        'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='pay_groups',
    )
    default_bank_template_code = models.CharField(max_length=40, blank=True, help_text='Reserved for Task H — no BankFileTemplate model exists yet.')
    default_payslip_template_code = models.CharField(max_length=40, blank=True, help_text='Reserved for Task K — no PayslipTemplate model exists yet.')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_pay_groups_v2'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'
