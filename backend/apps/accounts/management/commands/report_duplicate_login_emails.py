"""
READ-ONLY: login emails that differ only by letter case (the database unique index is case-sensitive, so these slip through).

    python manage.py report_duplicate_login_emails

Prints how many groups exist and the employee ids involved, never the email addresses. Changes nothing. A case-insensitive unique
constraint should only be added once this reports zero.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = 'List login emails that are duplicates apart from letter case (read-only).'

    def handle(self, *args, **options):
        groups = defaultdict(list)
        for employee_id, email in User.objects.values_list('employee_id', 'email'):
            groups[email.strip().lower()].append(employee_id or '(no employee id)')
        duplicates = [ids for ids in groups.values() if len(ids) > 1]
        for ids in duplicates:
            self.stdout.write('  same email (ignoring case): ' + ', '.join(ids))
        self.stdout.write(f'{len(duplicates)} duplicate group(s) found. Nothing was changed.')
