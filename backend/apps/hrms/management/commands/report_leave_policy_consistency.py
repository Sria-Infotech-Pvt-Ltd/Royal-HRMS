"""
READ-ONLY: every leave type's configured values next to its policy note, with likely contradictions flagged for HR to decide.

    python manage.py report_leave_policy_consistency [--csv file.csv]

Nothing is changed. HR confirms which side (the note or the configuration) is correct and edits it in Settings > Leave policy.
"""
import csv

from django.core.management.base import BaseCommand

from apps.hrms.models import LeavePolicy
from apps.hrms.services_leave_policy_report import build_policy_report


class Command(BaseCommand):
    help = 'List leave policy values beside their notes and flag mismatches (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='', help='Also write the report to this CSV file.')

    def handle(self, *args, **options):
        rows = build_policy_report(LeavePolicy.objects.order_by('leave_type'))
        flagged = 0
        for row in rows:
            values = ', '.join(f'{key}={value}' for key, value in row['values'].items())
            self.stdout.write(f'{row["leave_type"]}: {values}')
            self.stdout.write(f'    note: {row["note"] or "(none)"}')
            for problem in row['mismatches']:
                self.stdout.write(f'    CHECK: {problem}')
            flagged += bool(row['mismatches'])
        self.stdout.write(f'{len(rows)} leave type(s), {flagged} with a possible mismatch. Nothing was changed.')
        if options['csv']:
            with open(options['csv'], 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['leave_type', 'policy_note', 'configured_values', 'possible_mismatches'])
                for row in rows:
                    writer.writerow([row['leave_type'], row['note'], row['values'], ' | '.join(row['mismatches'])])
