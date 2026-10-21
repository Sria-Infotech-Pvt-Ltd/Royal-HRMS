"""
Copy salary components onto existing salary revisions that have none.

Revisions saved before employee-wise components existed (and those created by
onboarding approval or employee bulk import) are still calculated from the
live structure. This copies that same structure — resolved exactly as payroll
does today: employee pick → branch → company default — onto each revision, so
the calculation is unchanged but later structure edits no longer affect it.

Dry run by default. Nothing is recalculated and no payslip is touched.
Revisions whose structure is unclear are reported and skipped, never guessed.

    python manage.py tenant_command backfill_salary_components --schema=<tenant>            # report only
    python manage.py tenant_command backfill_salary_components --schema=<tenant> --apply    # write
"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.accounts.models import AuditLog
from apps.branch.models import Branch
from apps.payroll.models import EmployeePayslip, EmployeeSalaryConfig, SalaryStructure
from apps.payroll.services_salary_components import (
    resolve_template_structure, snapshot_existing, specs_from_structure,
)


class Command(BaseCommand):
    help = 'Copy structure components onto salary revisions that have no component snapshot (dry run by default).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the snapshots (default: report only).')

    def handle(self, *args, apply=False, **options):
        default_structure = SalaryStructure.objects.filter(is_default=True, is_active=True).first()
        branches = {b.branch_name: b for b in Branch.objects.select_related('payroll_config__salary_structure')}
        configs = (EmployeeSalaryConfig.objects.filter(components__isnull=True)
                   .select_related('employee', 'salary_structure').order_by('employee_id', 'effective_from'))
        ready, flagged, written = [], [], 0
        # Histories that can't be ordered reliably are reported, not guessed.
        active_count = Counter(EmployeeSalaryConfig.objects.filter(is_active=True).values_list('employee_id', flat=True))
        date_count = Counter(EmployeeSalaryConfig.objects.values_list('employee_id', 'effective_from'))
        for cfg in configs:
            employee = cfg.employee
            who = f'revision {cfg.pk} (employee {employee.employee_id or employee.pk}, from {cfg.effective_from})'
            if active_count[employee.pk] > 1:
                flagged.append(f'{who}: the employee has {active_count[employee.pk]} revisions marked current.')
                continue
            if date_count[(employee.pk, cfg.effective_from)] > 1:
                flagged.append(f'{who}: another revision has the same effective date.')
                continue
            branch = branches.get(employee.branch)
            if cfg.salary_structure is None and employee.branch and branch is None:
                flagged.append(f'{who}: employee branch is not a known branch.')
                continue
            structure = resolve_template_structure(
                employee, cfg.salary_structure,
                branch_config=getattr(branch, 'payroll_config', None) if branch else None,
                default_structure=default_structure,
            )
            if structure is None:
                flagged.append(f'{who}: no structure applies (no employee, branch or default structure).')
                continue
            components = list(structure.components.filter(is_active=True).order_by('order'))
            if not components:
                flagged.append(f'{who}: structure "{structure.name}" has no active components.')
                continue
            used = set(EmployeePayslip.objects.filter(
                employee=employee, cycle__cycle_end__gte=cfg.effective_from, salary_structure__isnull=False,
            ).exclude(salary_structure=structure).values_list('salary_structure__name', flat=True))
            if used:
                flagged.append(f'{who}: earlier payslips used a different structure ({", ".join(sorted(used))}) '
                               f'than the one that applies now ("{structure.name}").')
                continue
            ready.append((cfg, structure, components))

        for cfg, structure, components in ready:
            line = f'revision {cfg.pk} (employee {cfg.employee.employee_id or cfg.employee.pk}): ' \
                   f'{len(components)} components from "{structure.name}"'
            if apply:
                rows = snapshot_existing(cfg, specs_from_structure(components), structure)
                if rows:
                    AuditLog.objects.create(
                        user=None, action='salary_components_backfilled', module='payroll', object_id=str(cfg.pk),
                        changes={'employee_code': cfg.employee.employee_id or str(cfg.employee_id),
                                 'template_structure': structure.name, 'components': [c.name for c in components]},
                        branch=cfg.employee.branch or '',
                    )
                written += rows
                self.stdout.write(f'  copied  {line}')
            else:
                self.stdout.write(f'  ready   {line}')
        for line in flagged:
            self.stdout.write(self.style.WARNING(f'  skipped {line}'))
        mode = 'Applied' if apply else 'Dry run'
        self.stdout.write(self.style.SUCCESS(
            f'{mode}: {len(ready)} revision(s) ready, {len(flagged)} skipped for review'
            + (f', {written} component row(s) written.' if apply else '. Re-run with --apply to write.')
        ))
