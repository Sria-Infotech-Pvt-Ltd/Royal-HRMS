"""Phase 7A Task H — read-only report of declared_investments keys that
don't map to a known TaxSection code. Never writes anything."""
from django.core.management.base import BaseCommand

from apps.payroll.services_tax_declaration import report_unmapped_keys_across_all_declarations


class Command(BaseCommand):
    help = 'Phase 7A Task H — report EmployeeTaxDeclaration rows with unmapped declared_investments keys (read-only).'

    def handle(self, *args, **options):
        report = report_unmapped_keys_across_all_declarations()
        if not report:
            self.stdout.write(self.style.SUCCESS('Every declared_investments key across every declaration maps cleanly to a known TaxSection code.'))
            return
        for declaration_id, info in report.items():
            self.stdout.write(self.style.WARNING(
                f'Declaration {declaration_id} (employee {info["employee_id"]}): unmapped keys {info["unmapped"]}'
            ))
        self.stdout.write(self.style.WARNING(f'{len(report)} declaration(s) with at least one unmapped key.'))
