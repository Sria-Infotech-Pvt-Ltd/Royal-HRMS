"""
Phase 7A Task F — statutory schemes as effective-dated data.

`StatutoryScheme` is the catalogue (PF/EPS/EDLI/EPF_ADMIN/ESI/PT/LWF/
GRATUITY); `StatutoryRate` is the actual versioned parameter data (rates,
ceilings, state scoping) seeded from whatever this company's real
StatutoryConfig/PayrollSettings rows say today — see seed_statutory_schemes
for the exact source of every seeded number.

Every seeded value is statutory/tax data: flagged here and in the seed
command as "verify with a qualified professional before go-live" per the
master prompt's own rule — nothing here is a legal guarantee of correctness,
only a faithful copy of what this codebase already computes.

Not wired into the live engine. apps.payroll.engine.legacy still reads
StatutoryConfig/BranchPayrollConfig/PayrollSettings directly, unchanged.
"""
import uuid

from django.db import models


class StatutoryScheme(models.Model):
    CODE_EPF        = 'PF'
    CODE_EPS        = 'EPS'
    CODE_EDLI       = 'EDLI'
    CODE_EPF_ADMIN  = 'EPF_ADMIN'
    CODE_ESI        = 'ESI'
    CODE_PT         = 'PT'
    CODE_LWF        = 'LWF'
    CODE_GRATUITY   = 'GRATUITY'
    CODE_BONUS      = 'BONUS'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    country = models.ForeignKey(
        'platform_core.Country', on_delete=models.PROTECT, null=True, blank=True,
        related_name='statutory_schemes',
    )
    # Free-form description of what this scheme's StatutoryRate.parameters
    # dict is expected to contain for this code (e.g. for ESI:
    # {"employee_rate": "...", "employer_rate": "...", "wage_ceiling": "..."})
    # — documented per-scheme in seed_statutory_schemes rather than enforced
    # by a JSONSchema validator, which would be new infrastructure this task
    # doesn't need to introduce.
    parameter_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_statutory_schemes_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class StatutoryRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scheme = models.ForeignKey(StatutoryScheme, on_delete=models.CASCADE, related_name='rates')
    state = models.ForeignKey(
        'branch.State', on_delete=models.PROTECT, null=True, blank=True,
        related_name='statutory_rates_v2',
        help_text='Set for state-specific schemes (PT, LWF). Blank = applies everywhere.',
    )
    legal_entity = models.ForeignKey(
        'platform_core.LegalEntity', on_delete=models.PROTECT, null=True, blank=True,
        related_name='statutory_rates_v2',
    )
    parameters = models.JSONField(
        default=dict,
        help_text='Scheme-specific rate data — see StatutoryScheme.parameter_notes for the expected shape.',
    )
    source_citation = models.CharField(
        max_length=200, blank=True,
        help_text='Exact file:line (or DB row) this value was copied from, for the pre-go-live legal review.',
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_statutory_rates_v2'
        ordering = ['scheme__code', '-effective_from']

    def __str__(self):
        scope = self.state.name if self.state_id else 'all states'
        return f'{self.scheme.code} ({scope}) from {self.effective_from or "always"}'
