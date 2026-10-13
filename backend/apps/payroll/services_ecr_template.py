"""
Phase 7B Task J — byte-identical ECR text generation.

Reuses the REAL, already-correct row-computation and text-building
functions from `apps.payroll.views.ecr` (`_compute_ecr_rows`/
`_build_ecr_text`/`_ecr_filename`) DIRECTLY, rather than re-deriving the
same UAN/wage/EPS/EDLI logic through the generic sandboxed field-mapping
renderer (`services_bank_template.render_row`). That generic renderer only
resolves plain dotted attribute paths — ECR's real format has two things
it can't express safely: a name-with-fallback field (`name_as_per_aadhar
or employee_name`) and a hardcoded literal column ("Refund of Advances" is
always `0`, not read from any model). Calling the real function IS the
byte-identical proof — there is no second implementation of this format
to drift out of sync with the production one.

Matches the real view's behavior exactly, including the hard failure: if
ANY employee in the cycle is missing a UAN, NO file is generated at all —
not a partial file with blanks (confirmed by reading
`CycleECRTextDownloadView.get`'s own missing_uan check before writing this).
"""
import hashlib

from django.db import transaction

from apps.payroll.models import GeneratedStatutoryFile, PayrollSettings, StatutoryFileTemplate
from apps.payroll.views.ecr import _build_ecr_text, _compute_ecr_rows, _ecr_filename


class MissingUanError(Exception):
    """Mirrors the real view's hard-fail-the-whole-file behavior."""
    def __init__(self, missing_employee_names):
        self.missing_employee_names = missing_employee_names
        super().__init__(
            f'{len(missing_employee_names)} employee(s) have no UAN on file — '
            f'add it before filing: {", ".join(missing_employee_names)}'
        )


@transaction.atomic
def generate_ecr_text_via_template(template: StatutoryFileTemplate, cycle, *, run=None, generated_by=None) -> GeneratedStatutoryFile:
    settings_row = PayrollSettings.objects.first()
    if settings_row is None:
        raise ValueError('No PayrollSettings row exists — cannot compute ECR (eps_rate/edli_wage_ceiling unavailable).')

    rows = _compute_ecr_rows(cycle, settings_row)
    missing_uan_names = [r['employee_name'] for r in rows if not r['uan']]
    if missing_uan_names:
        raise MissingUanError(missing_uan_names)

    content = _build_ecr_text(rows)
    checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
    file_name = _ecr_filename(cycle, 'txt')

    return GeneratedStatutoryFile.objects.create(
        template=template, run=run, file_name=file_name, content=content,
        checksum_sha256=checksum, missing_identity_employee_ids=[], generated_by=generated_by,
    )
