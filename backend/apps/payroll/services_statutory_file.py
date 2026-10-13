"""
Phase 7B Task J — statutory returns/challans, same sandboxed renderer as
Task H (services_bank_template.render_row/SAFE_SOURCES).

Deferred, stated plainly: byte-identical seeding against the real
`views/ecr.py`/`views/esic.py` output was NOT done in this pass — that
needs a side-by-side field audit of those two files' exact column order/
formatting, which is real, careful work on its own. This builds the
generation/storage/audit mechanism and the UAN-presence gate for real;
the specific ECR/ESIC field_specs rows are a documented follow-up, not
invented here as a guess at the official format.
"""
import hashlib
from decimal import Decimal

from django.db import transaction

from apps.payroll.models import GeneratedStatutoryFile
from apps.payroll.services_bank_template import render_row


@transaction.atomic
def generate_statutory_file(template, employees_payslips, *, run=None, generated_by=None) -> GeneratedStatutoryFile:
    """`employees_payslips` is an iterable of EmployeePayslip. Employees
    missing a required identity document (UAN for ECR, per
    template.requires_uan) are EXCLUDED and reported in
    missing_identity_employee_ids — never silently included with a blank
    UAN column."""
    included_lines = []
    missing_ids = []
    if template.field_specs:
        included_lines.append(template.delimiter.join(spec['label'] for spec in template.field_specs))

    for payslip in employees_payslips:
        employee = payslip.employee
        uan_number = getattr(getattr(employee, 'profile', None), 'uan_number', None)
        if template.requires_uan and not uan_number:
            missing_ids.append(employee.employee_id)
            continue
        context = {'payslip': payslip, 'employee': employee, 'run': run}
        included_lines.append(render_row(template.field_specs, context, template.delimiter))

    content = '\r\n'.join(included_lines) + '\r\n'
    checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()

    file_name = template.file_name_pattern.format(
        scheme=template.scheme,
        period_start=getattr(run.period, 'period_start', '') if run else '',
        period_end=getattr(run.period, 'period_end', '') if run else '',
    )
    return GeneratedStatutoryFile.objects.create(
        template=template, run=run, file_name=file_name, content=content, checksum_sha256=checksum,
        missing_identity_employee_ids=missing_ids, generated_by=generated_by,
    )
