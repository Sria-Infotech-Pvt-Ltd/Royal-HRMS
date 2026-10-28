"""
Map the employment types stored on leave policies ("Full-time", "Part-time") to the one master list ("Permanent", "Part-Time").

    python manage.py remap_policy_employment_types           # dry run: prints the mapping, changes nothing
    python manage.py remap_policy_employment_types --apply   # writes it, once the printed mapping is approved

Eligibility compares a policy's list with each employee's own employment type, so a value that is not in the master list never
matched anyone. A value that cannot be mapped is reported and left exactly as it is.
"""
from django.core.management.base import BaseCommand

from apps.accounts.employment_types import normalize_employment_type
from apps.hrms.models import LeavePolicy


class Command(BaseCommand):
    help = 'Map leave policy employment types to the master list (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the mapping (default is a dry run).')

    def handle(self, *args, **options):
        changes = 0
        for policy in LeavePolicy.objects.order_by('leave_type'):
            before = list(policy.applicable_employment_types or [])
            after, unmapped = [], []
            for raw in before:
                matched = normalize_employment_type(raw)
                if matched is None:
                    unmapped.append(raw)
                    after.append(raw)  # left as it is
                elif matched not in after:
                    after.append(matched)
            if after != before:
                changes += 1
                self.stdout.write(f'{policy.leave_type}: {before} -> {after}')
                if options['apply']:
                    policy.applicable_employment_types = after
                    policy.save(update_fields=['applicable_employment_types', 'updated_at'])
            for raw in unmapped:
                self.stdout.write(f'{policy.leave_type}: "{raw}" has no match in the master list and was left alone.')
        verb = 'Updated' if options['apply'] else 'Would update (dry run)'
        self.stdout.write(f'{verb}: {changes} policy(ies).')
