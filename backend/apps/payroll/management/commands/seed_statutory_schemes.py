"""
Phase 7A Task F — seed StatutoryScheme/StatutoryRate from this company's
REAL current data, not invented values. Every number below is copied from
one of two places (cited per-row):

  1. apps.payroll.engine.legacy / apps.payroll.models field DEFAULTS —
     these are the fallback values used when no BranchPayrollConfig/
     StatutoryConfig row overrides them. Exact source lines (as of Phase
     7A Task A's extraction):
       - PF employee/employer rate 12.00%, ceiling Rs.15,000 —
         apps/payroll/engine/legacy.py: _PF_DEFAULT_RATE / _PF_DEFAULT_CEILING
       - EPS rate 8.33% — apps/payroll/models.py: PayrollSettings.eps_rate (default)
       - EDLI rate 0.50%, wage ceiling Rs.15,000 —
         apps/payroll/models.py: PayrollSettings.edli_rate / edli_wage_ceiling (default)
       - EPF admin charge 0.50% — apps/payroll/models.py: PayrollSettings.epf_admin_rate (default)
       - Gratuity provision 4.81% of Basic+DA —
         apps/payroll/models.py: PayrollSettings.gratuity_rate (default)

  2. Real StatutoryConfig rows in this database (one per state) — PT/LWF/
     ESI are genuinely state-scoped today, so each existing StatutoryConfig
     row becomes its own StatutoryRate, cited by state name + row id.

VERIFY EVERY SEEDED VALUE WITH A QUALIFIED PROFESSIONAL BEFORE GO-LIVE —
these are a faithful copy of what this codebase already computes, not an
independent legal confirmation that the current rates/ceilings are
statutorily correct today.

Idempotent (update_or_create by scheme+state+effective_from=None).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payroll.models import PayrollSettings, StatutoryConfig, StatutoryRate, StatutoryScheme


_SCHEME_DEFS = [
    (StatutoryScheme.CODE_EPF, 'Provident Fund',
     '{"employee_rate": "%", "employer_rate": "%", "wage_ceiling": "monthly Rs."}'),
    (StatutoryScheme.CODE_EPS, 'Employee Pension Scheme', '{"rate": "% of employer PF share"}'),
    (StatutoryScheme.CODE_EDLI, 'Employee Deposit Linked Insurance',
     '{"rate": "%", "wage_ceiling": "monthly Rs."}'),
    (StatutoryScheme.CODE_EPF_ADMIN, 'EPF Administrative Charges', '{"rate": "%"}'),
    (StatutoryScheme.CODE_ESI, 'Employee State Insurance',
     '{"employee_rate": "%", "employer_rate": "%", "wage_ceiling": "monthly Rs."}'),
    (StatutoryScheme.CODE_PT, 'Professional Tax', '{"slabs": "[{min,max,amount}, ...]"}'),
    (StatutoryScheme.CODE_LWF, 'Labour Welfare Fund',
     '{"employee_amount": "Rs.", "employer_amount": "Rs.", "frequency": "monthly|halfyearly|annual", "due_months": "[1-12,...]"}'),
    (StatutoryScheme.CODE_GRATUITY, 'Gratuity Provision', '{"rate": "% of Basic+DA (standard 15/26/12 formula)"}'),
]


class Command(BaseCommand):
    help = 'Phase 7A Task F — seed StatutoryScheme/StatutoryRate from real current data (cited, verify-before-go-live).'

    def handle(self, *args, **options):
        schemes = {}
        for code, name, notes in _SCHEME_DEFS:
            scheme, _ = StatutoryScheme.objects.update_or_create(
                code=code, defaults={'name': name, 'parameter_notes': notes},
            )
            schemes[code] = scheme

        settings_row = PayrollSettings.objects.first()
        rate_rows_written = 0

        def _write_rate(scheme_code, state, parameters, citation):
            nonlocal rate_rows_written
            StatutoryRate.objects.update_or_create(
                scheme=schemes[scheme_code], state=state, effective_from=None,
                defaults={'parameters': parameters, 'source_citation': citation},
            )
            rate_rows_written += 1

        # ── Company-wide default rates (no state scope) ────────────────
        _write_rate(StatutoryScheme.CODE_EPF, None,
                    {'employee_rate': '12.00', 'employer_rate': '12.00', 'wage_ceiling': '15000.00'},
                    'apps/payroll/engine/legacy.py: _PF_DEFAULT_RATE, _PF_DEFAULT_CEILING (fallback when no BranchPayrollConfig override)')

        eps_rate = str(settings_row.eps_rate) if settings_row else '8.33'
        _write_rate(StatutoryScheme.CODE_EPS, None, {'rate': eps_rate},
                    'apps/payroll/models.py: PayrollSettings.eps_rate (current DB value)')

        if settings_row:
            _write_rate(StatutoryScheme.CODE_EDLI, None,
                        {'rate': str(settings_row.edli_rate), 'wage_ceiling': str(settings_row.edli_wage_ceiling)},
                        'apps/payroll/models.py: PayrollSettings.edli_rate, edli_wage_ceiling (current DB value)')
            _write_rate(StatutoryScheme.CODE_EPF_ADMIN, None, {'rate': str(settings_row.epf_admin_rate)},
                        'apps/payroll/models.py: PayrollSettings.epf_admin_rate (current DB value)')
            _write_rate(StatutoryScheme.CODE_GRATUITY, None, {'rate': str(settings_row.gratuity_rate)},
                        'apps/payroll/models.py: PayrollSettings.gratuity_rate (current DB value)')

        # ── Per-state rates: ESI/PT/LWF genuinely vary by state, copied
        #    from whatever StatutoryConfig rows actually exist today ──────
        for config in StatutoryConfig.objects.select_related('state').all():
            citation = f'apps/payroll/models.py: StatutoryConfig row id={config.id} for state={config.state.name}'

            if config.esi_applicable:
                _write_rate(StatutoryScheme.CODE_ESI, config.state, {
                    'employee_rate': str(config.esi_employee_rate),
                    'employer_rate': str(config.esi_employer_rate),
                    'wage_ceiling': str(config.esi_wage_ceiling),
                }, citation)

            if config.pt_applicable:
                _write_rate(StatutoryScheme.CODE_PT, config.state, {'slabs': config.pt_slabs}, citation)

            if config.lwf_applicable:
                _write_rate(StatutoryScheme.CODE_LWF, config.state, {
                    'employee_amount': str(config.lwf_employee_amount),
                    'employer_amount': str(config.lwf_employer_amount),
                    'frequency': config.lwf_frequency,
                    'due_months': config.lwf_due_months,
                }, citation)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(schemes)} StatutoryScheme rows and {rate_rows_written} StatutoryRate rows. '
            'VERIFY EVERY VALUE WITH A QUALIFIED PROFESSIONAL BEFORE GO-LIVE.'
        ))
