"""
Phase 7A Task E — backfill PayslipLine rows from already-computed
EmployeePayslip rows, oldest cycle first (required for YTD correctness —
see services_payslip_lines.persist_lines_for_payslip's own docstring).

Purely additive: reads EmployeePayslip, writes PayslipLine. Never touches
EmployeePayslip itself, PayrollCycle, or anything the legacy engine owns.
"""
from django.core.management.base import BaseCommand

from apps.payroll.models import EmployeePayslip
from apps.payroll.services_payslip_lines import persist_lines_for_payslip


class Command(BaseCommand):
    help = 'Phase 7A Task E — derive PayslipLine rows from every existing EmployeePayslip (idempotent, additive).'

    def handle(self, *args, **options):
        total_lines = 0
        payslips = EmployeePayslip.objects.select_related('cycle').order_by('cycle__cycle_start', 'employee_id')
        count = payslips.count()
        for payslip in payslips:
            lines = persist_lines_for_payslip(payslip)
            total_lines += len(lines)
        self.stdout.write(self.style.SUCCESS(
            f'Backfilled {total_lines} PayslipLine rows across {count} payslips.'
        ))
