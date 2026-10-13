"""
Phase 7B Task J — seed the ECR text StatutoryFileTemplate row.

IMPORTANT: `field_specs` here is DOCUMENTATION of the real field order
(confirmed by reading apps.payroll.views.ecr._compute_ecr_rows/
_build_ecr_text line-by-line) for an admin UI to display — it is NOT
consumed by the generic sandboxed renderer (services_bank_template
.render_row). Actual generation goes through
services_ecr_template.generate_ecr_text_via_template(), which calls the
real view's own row/text-building functions directly. Two of ECR's real
fields can't be expressed as a plain dotted source at all: field 2 is a
fallback ("name_as_per_aadhar if set, else employee_name") and field 11
is a hardcoded literal (0, always) — both noted explicitly below rather
than misrepresented as resolvable `source` paths.

ESIC is NOT seeded here — confirmed (via direct code reading) to be an
xlsx-only internal reconciliation report with no delimited-text format at
all, so it doesn't fit StatutoryFileTemplate's field_specs/delimiter shape
the way ECR's text export does. Left as a documented gap, not forced into
a shape that doesn't match its real format.
"""
from django.core.management.base import BaseCommand

from apps.payroll.models import StatutoryFileTemplate

_ECR_TEXT_FIELD_SPECS = [
    {'source': 'profile.uan_number', 'label': 'UAN'},
    {'source': 'FALLBACK: profile.name_as_per_aadhar, else employee.full_name', 'label': 'Member Name'},
    {'source': 'COMPUTED: round(gross_earnings)', 'label': 'Gross Wages'},
    {'source': 'COMPUTED: round(basic)', 'label': 'EPF Wages'},
    {'source': 'COMPUTED: round(pf_wage_base, capped at BranchPayrollConfig ceiling)', 'label': 'EPS Wages'},
    {'source': 'COMPUTED: round(min(basic, PayrollSettings.edli_wage_ceiling))', 'label': 'EDLI Wages'},
    {'source': 'COMPUTED: round(pf_employee)', 'label': 'EPF Contribution Remitted'},
    {'source': 'COMPUTED: round(pf_wage_base * PayrollSettings.eps_rate / 100)', 'label': 'EPS Contribution Remitted'},
    {'source': 'COMPUTED: max(0, epf_contribution - eps_contribution)', 'label': 'EPF-EPS Difference Remitted'},
    {'source': 'COMPUTED: round(lop_days)', 'label': 'NCP Days'},
    {'source': 'LITERAL: 0 (Refund of Advances — not tracked in this system)', 'label': 'Refund of Advances'},
]


class Command(BaseCommand):
    help = 'Phase 7B Task J — seed the ECR text StatutoryFileTemplate (documentation only; real generation reuses apps.payroll.views.ecr directly).'

    def handle(self, *args, **options):
        template, created = StatutoryFileTemplate.objects.update_or_create(
            code='ECR_TEXT_V1',
            defaults={
                'scheme': StatutoryFileTemplate.SCHEME_ECR,
                'field_specs': _ECR_TEXT_FIELD_SPECS,
                'delimiter': '#~#',
                'file_name_pattern': 'ECR_{period}_{branch}.txt',
                'requires_uan': True,
                'note': (
                    'Reproduces apps.payroll.views.ecr._build_ecr_text()/_compute_ecr_rows() '
                    'byte-for-byte via services_ecr_template.generate_ecr_text_via_template() — '
                    'field_specs above are documentation of the real field order, not executable '
                    'by the generic sandboxed renderer. #~# delimiter, trailing delimiter per row, '
                    '\\r\\n row separator, no header/footer. Verify against the current official '
                    'EPFO Unified Portal ECR specification before go-live.'
                ),
            },
        )
        self.stdout.write(self.style.SUCCESS(f'ECR text template {"created" if created else "updated"}: {template.code}'))
