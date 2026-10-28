"""
READ-ONLY report: employees whose UAN / ESI number is empty now but was entered at some point.

Background: Edit full record used to send a blank UAN and ESI number on every save (the employee API never returned them), which
overwrote the stored values; separately, the hire wizard never copied the ESI number onto the employee. This command changes
nothing and restores nothing. It lists where evidence of the lost value still exists (the completed hire's draft payload) so the
values can be restored from backup by a person.

    python manage.py report_wiped_statutory_ids                  # counts only
    python manage.py report_wiped_statutory_ids --csv out.csv    # the list: employee id, field, evidence, last 4 digits only

Only the last four digits are written, never the full number and never a name.
"""
import csv

from django.core.management.base import BaseCommand

from apps.accounts.models import EmployeeProfile, HireAction

FIELDS = {
    'uan_number': 'Edit full record wiped it, or it was never stored',
    'esi_number': 'never copied at hire (fixed), or wiped by Edit full record',
}
COLUMNS = ['employee_id', 'field', 'evidence_source', 'value_last4', 'profile_last_updated', 'hire_effective_from', 'likely_cause']


def _last4(value) -> str:
    text = str(value or '').strip()
    return f'...{text[-4:]}' if len(text) >= 4 else '...'


class Command(BaseCommand):
    help = 'List employees whose UAN/ESI is empty but was set in their hire draft (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default='', help='Write the list to this CSV file.')

    def handle(self, *args, **options):
        rows = []
        hires = HireAction.objects.filter(status=HireAction.STATUS_COMPLETED, created_employee__isnull=False).select_related('created_employee')
        for hire in hires:
            employee = hire.created_employee
            profile = EmployeeProfile.objects.filter(user=employee).first()
            for field, cause in FIELDS.items():
                entered = str((hire.draft_data or {}).get(field) or '').strip()
                if entered and not (getattr(profile, field, '') if profile else ''):
                    rows.append({
                        'employee_id': employee.employee_id, 'field': field, 'evidence_source': 'hire draft payload',
                        'value_last4': _last4(entered),
                        'profile_last_updated': profile.updated_at.isoformat() if profile else '',
                        'hire_effective_from': str(hire.effective_from), 'likely_cause': cause,
                    })
        by_field = {field: sum(1 for row in rows if row['field'] == field) for field in FIELDS}
        self.stdout.write(f'{len(rows)} case(s) found: {by_field}. Nothing was changed.')
        self.stdout.write(
            'Limit: values entered anywhere other than the hire wizard (bulk import, self-service onboarding, an earlier Edit) leave '
            'no history here; those can only be recovered from a database backup.'
        )
        if options['csv']:
            with open(options['csv'], 'w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            self.stdout.write(f'List written to {options["csv"]}.')
