"""
Phase 7A Task G — income tax engine as data.

`TaxRegime` (OLD/NEW) x `TaxYearConfig` (one row per regime per financial
year: slabs, rebate threshold, standard deduction, cess rate) x
`TaxSection` (80C/80D/80CCD1B/HRA — old-regime-only deductions, each with
its real statutory cap) together hold exactly what
`apps/payroll/services_income_tax.py` hardcodes today for FY2026-27 — see
seed_tax_year_config for the line-by-line citation.

Adding next year's slabs becomes a data task once this is actually wired in
(copy this FY's TaxYearConfig row, edit the numbers, set a new
financial_year_start) — not yet, since nothing reads this model: see
services_tax_engine.py's own docstring for the parity proof that the DATA
reproduces the current hardcoded computation exactly, which is as far as
Task G goes without touching the live engine.
"""
import uuid

from django.db import models


class TaxRegime(models.Model):
    CODE_OLD = 'old'
    CODE_NEW = 'new'
    CODE_CHOICES = [(CODE_OLD, 'Old Regime'), (CODE_NEW, 'New Regime (115BAC)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, choices=CODE_CHOICES, unique=True)
    country = models.ForeignKey(
        'platform_core.Country', on_delete=models.PROTECT, null=True, blank=True,
        related_name='tax_regimes',
    )

    class Meta:
        db_table = 'payroll_tax_regimes_v2'

    def __str__(self):
        return self.get_code_display()


class TaxYearConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    regime = models.ForeignKey(TaxRegime, on_delete=models.CASCADE, related_name='year_configs')
    financial_year_start = models.PositiveIntegerField(help_text='Calendar year the FY starts in, e.g. 2026 for FY2026-27.')
    # [{"start": "0", "end": "400000"|null, "rate": "0.00"}, ...] — annual, rupees.
    slabs = models.JSONField(default=list)
    rebate_threshold = models.DecimalField(max_digits=12, decimal_places=2)
    standard_deduction = models.DecimalField(max_digits=12, decimal_places=2)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.04)
    source_citation = models.CharField(max_length=200, blank=True)
    is_default = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_tax_year_configs_v2'
        unique_together = [('regime', 'financial_year_start')]
        ordering = ['-financial_year_start']

    def __str__(self):
        return f'{self.regime.code} FY{self.financial_year_start}-{str(self.financial_year_start + 1)[2:]}'


class TaxSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    # Regime codes this section's deduction applies under — today's engine
    # only ever applies these under the OLD regime (115BAC disallows them
    # for the new regime), so every seeded row is ['old'].
    applicable_regime_codes = models.JSONField(default=list)
    cap_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Null = no cap enforced today (e.g. HRA, taken at the declared amount as-is).',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'payroll_tax_sections_v2'
        ordering = ['code']

    def __str__(self):
        return self.code
