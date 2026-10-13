"""
Phase 7B Task H — template-driven bank files. A sandboxed field-mapping
language: `source` strings are DOTTED ATTRIBUTE PATHS resolved via
`getattr()` only (never `eval()`/`exec()`), restricted to a context dict
the caller builds explicitly (SAFE_SOURCES below) — a template cannot walk
to an arbitrary object graph, only whatever the context exposes.
"""
import hashlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import GeneratedBankFile


# The only top-level names a template's `source` may start with. Anything
# else raises — this is the "no code execution, variables only" sandbox
# boundary the master prompt requires.
SAFE_SOURCES = {'instruction', 'payslip', 'employee', 'bank_account', 'run'}


class TemplateSandboxError(Exception):
    pass


def _resolve(source: str, context: dict):
    parts = source.split('.')
    if parts[0] not in SAFE_SOURCES:
        raise TemplateSandboxError(f'Source {source!r} does not start with an allowed name ({sorted(SAFE_SOURCES)}).')
    value = context.get(parts[0])
    for part in parts[1:]:
        if value is None:
            return ''
        value = getattr(value, part, '')
    return value


def _format_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return f'{value:.2f}'
    return str(value)


def render_row(field_specs: list, context: dict, delimiter: str) -> str:
    cells = [_format_value(_resolve(spec['source'], context)) for spec in field_specs]
    return delimiter.join(cells)


@transaction.atomic
def generate_bank_file(template, run, instructions, *, generated_by=None, reason: str = '') -> GeneratedBankFile:
    """`instructions` is an iterable of PaymentInstruction rows already
    filtered to this run's finalised payslips (the caller's job — this
    function only renders and stores). Regenerating for the same
    (run, template) creates a new VERSION, never overwrites a prior one —
    immutability per the master prompt's own rule."""
    lines = []
    if template.include_header_row:
        lines.append(template.delimiter.join(spec['label'] for spec in template.field_specs))

    control_total = Decimal('0')
    control_count = 0
    for instruction in instructions:
        context = {
            'instruction': instruction, 'payslip': instruction.payslip,
            'employee': instruction.payslip.employee, 'bank_account': instruction.bank_account, 'run': run,
        }
        lines.append(render_row(template.field_specs, context, template.delimiter))
        control_total += instruction.amount
        control_count += 1

    content = '\r\n'.join(lines) + '\r\n'  # CRLF per the master prompt's own "preserve CRLF" rule
    checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()

    existing_version_count = GeneratedBankFile.objects.filter(run=run, template=template).count()
    if existing_version_count > 0 and not reason.strip():
        raise ValueError('Regenerating an existing bank file requires a reason.')

    file_name = template.file_name_pattern.format(run_reference=run.reference_number)
    return GeneratedBankFile.objects.create(
        template=template, run=run, version=existing_version_count + 1, file_name=file_name,
        content=content, checksum_sha256=checksum, control_total_amount=control_total,
        control_total_count=control_count, regeneration_reason=reason, generated_by=generated_by,
    )


def log_download(generated_file, downloaded_by):
    from apps.payroll.models import BankFileDownloadLog
    return BankFileDownloadLog.objects.create(generated_file=generated_file, downloaded_by=downloaded_by)
