"""
Phase 7A Task J — run the shadow-run sweep against every real
EmployeePayslip and report the result. Never writes to EmployeePayslip
itself — only to PayslipShadowRunResult. Run `seed_pay_components`,
`seed_statutory_schemes`, and `seed_tax_year_config` first.
"""
from django.core.management.base import BaseCommand

from apps.payroll.services_shadow_run import run_shadow_sweep


class Command(BaseCommand):
    help = 'Phase 7A Task J — shadow-recompute every historical payslip and report matches/mismatches/errors.'

    def handle(self, *args, **options):
        summary = run_shadow_sweep()
        self.stdout.write(self.style.SUCCESS(
            f"Shadow run complete — {summary['total']} payslip(s): "
            f"{summary['matched']} matched, {summary['mismatched']} mismatched, {summary['errored']} errored."
        ))
        if summary['mismatched'] or summary['errored']:
            self.stdout.write(self.style.WARNING(
                'payroll.v2 cannot be enabled until every payslip has a clean shadow-run result — '
                'see PayslipShadowRunResult.diffs/error per payslip for root-cause detail.'
            ))
