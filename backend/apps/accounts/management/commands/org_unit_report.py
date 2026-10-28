"""
Read-only report of every org unit: id, name, parent, employee / position / vacancy counts and probable duplicates (by name
similarity). Changes nothing; it is the list the business reviews before approving any merge.

    python manage.py org_unit_report
    python manage.py org_unit_report --csv org_units.csv
"""
import csv

from django.core.management.base import BaseCommand

from apps.accounts.services_org_units import build_org_unit_report

COLUMNS = ['id', 'name', 'parent', 'is_active', 'employee_count', 'position_count', 'vacancy_count', 'probable_duplicates']


class Command(BaseCommand):
    help = 'List all org units with counts and probable duplicates (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='', help='Also write the report to this CSV file.')

    def handle(self, *args, **options):
        rows = build_org_unit_report()
        for row in rows:
            duplicates = '; '.join(row['probable_duplicates']) or '-'
            self.stdout.write(
                f'{row["id"]}  {row["name"]}  | parent: {row["parent"] or "-"}  | employees {row["employee_count"]}, '
                f'positions {row["position_count"]}, vacancies {row["vacancy_count"]}  | looks like: {duplicates}'
                + ('' if row['is_active'] else '  [inactive]')
            )
        self.stdout.write(f'{len(rows)} org unit(s). Nothing was changed.')
        if options['csv']:
            with open(options['csv'], 'w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                for row in rows:
                    writer.writerow({**row, 'probable_duplicates': '; '.join(row['probable_duplicates'])})
            self.stdout.write(f'Written to {options["csv"]}.')
