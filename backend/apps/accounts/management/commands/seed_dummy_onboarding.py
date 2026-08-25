"""
Management command: seed_dummy_onboarding

Fills EmployeeProfile placeholder data (education, bank details, emergency
contact) and marks onboarding complete for employees stuck at "pending" after
a bulk import.

DEMO / TEST DATA ONLY. Never run this against real employees — bank account
numbers, IFSC codes, and identity documents are fabricated here and cannot
stand in for real employee data (wrong bank details would misdirect payroll;
document uploads are skipped entirely since a real PAN/Aadhaar/degree file
cannot be faked). Approval does not require documents, so onboarding_status
is set straight to "complete" without creating any EmployeeDocument rows.

Run:  python manage.py seed_dummy_onboarding --dry-run
      python manage.py seed_dummy_onboarding
      python manage.py seed_dummy_onboarding --department "Sales" --branch "Hyderabad"
      python manage.py seed_dummy_onboarding --emails a@x.com b@x.com
"""
import random
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import AuditLog, EmployeeProfile, User

FATHER_NAMES = [
    'Ramesh Kumar', 'Suresh Babu', 'Mahesh Reddy', 'Venkat Rao', 'Anil Sharma',
    'Prakash Singh', 'Ravi Shankar', 'Krishna Murthy', 'Srinivas Rao', 'Naresh Gupta',
]
EMERGENCY_NAMES = [
    'Lakshmi Devi', 'Sita Devi', 'Padma Rao', 'Anitha Reddy', 'Kavitha Singh',
]
QUALIFICATIONS = [
    ('B.Tech', 'JNTU Hyderabad'),
    ('B.Com', 'Osmania University'),
    ('MBA', 'Andhra University'),
    ('B.Sc', 'Sri Venkateswara University'),
    ('Diploma', 'State Board of Technical Education'),
    ('M.Tech', 'IIT Madras'),
]
BANKS = [
    ('State Bank of India', 'SBIN0'),
    ('HDFC Bank', 'HDFC0'),
    ('ICICI Bank', 'ICIC0'),
    ('Axis Bank', 'UTIB0'),
    ('Punjab National Bank', 'PUNB0'),
]
RELATIONSHIPS = ['Father', 'Mother', 'Spouse', 'Brother', 'Sister']


def _seeded_random(user) -> random.Random:
    # Seeded per user so re-runs regenerate identical placeholder values
    # instead of drifting on every invocation.
    return random.Random(str(user.id))


def _placeholder_dob(rng, joining_date):
    age_years = rng.randint(22, 45)
    base_year = (joining_date or date.today()).year - age_years
    return date(base_year, rng.randint(1, 12), rng.randint(1, 28))


def _fill_profile(user, rng) -> list:
    """Fills only currently-blank profile fields — never overwrites real data
    that may already exist from bulk-import's optional gender/DOB/address columns."""
    profile, _ = EmployeeProfile.objects.get_or_create(user=user)
    changed = []

    def set_if_blank(field, value):
        if not getattr(profile, field, None):
            setattr(profile, field, value)
            changed.append(field)

    set_if_blank('date_of_birth', _placeholder_dob(rng, user.date_of_joining))
    set_if_blank('gender', rng.choice([EmployeeProfile.GENDER_MALE, EmployeeProfile.GENDER_FEMALE]))
    set_if_blank('marital_status', EmployeeProfile.MARITAL_SINGLE)
    set_if_blank('father_name', rng.choice(FATHER_NAMES))
    set_if_blank('blood_group', rng.choice([c[0] for c in EmployeeProfile.BLOOD_CHOICES]))
    address = f'{user.branch or "Head Office"}, India (placeholder — bulk import)'
    set_if_blank('current_address', address)
    set_if_blank('permanent_address', address)

    qualification, institution = rng.choice(QUALIFICATIONS)
    set_if_blank('highest_qualification', qualification)
    set_if_blank('institution', institution)
    set_if_blank(
        'year_of_passing',
        (user.date_of_joining or date.today()).year - rng.randint(1, 3),
    )

    bank_name, ifsc_prefix = rng.choice(BANKS)
    set_if_blank('account_holder_name', user.full_name)
    set_if_blank('account_type', EmployeeProfile.ACCOUNT_SAVINGS)
    set_if_blank('account_number', ''.join(str(rng.randint(0, 9)) for _ in range(11)))
    set_if_blank('ifsc_code', f'{ifsc_prefix}{rng.randint(100000, 999999)}')
    set_if_blank('bank_name', bank_name)
    set_if_blank('bank_branch_name', f'{user.branch or "Main"} Branch')

    relationship = rng.choice(RELATIONSHIPS)
    set_if_blank('emergency_relationship', relationship)
    set_if_blank(
        'emergency_name',
        rng.choice(FATHER_NAMES) if relationship in ('Father', 'Brother') else rng.choice(EMERGENCY_NAMES),
    )
    set_if_blank('emergency_phone', f'9{rng.randint(100000000, 999999999)}')

    if changed:
        profile.save()
    return changed


class Command(BaseCommand):
    help = (
        'Fills placeholder EmployeeProfile data and marks onboarding complete for '
        'employees stuck at "pending" after a bulk import. DEMO/TEST DATA ONLY.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                             help='Report what would change without saving anything.')
        parser.add_argument('--emails', nargs='*', default=None,
                             help='Restrict to these email addresses only.')
        parser.add_argument('--emails-file', default=None,
                             help='Path to a text file with one email address per line.')
        parser.add_argument('--department', default=None,
                             help='Restrict to employees in this department.')
        parser.add_argument('--branch', default=None,
                             help='Restrict to employees in this branch.')

    def handle(self, *args, **options):
        emails = list(options['emails'] or [])
        if options['emails_file']:
            with open(options['emails_file'], encoding='utf-8') as fh:
                emails += [line.strip() for line in fh if line.strip()]

        queryset = User.objects.filter(onboarding_status=User.ONBOARDING_PENDING)
        if emails:
            queryset = queryset.filter(email__in=emails)
        if options['department']:
            queryset = queryset.filter(department__iexact=options['department'])
        if options['branch']:
            queryset = queryset.filter(branch__iexact=options['branch'])

        users = list(queryset)
        if not users:
            self.stdout.write(self.style.WARNING(
                'No pending-onboarding employees match the given filters.'
            ))
            return

        dry_run = options['dry_run']
        self.stdout.write(
            f'{"[DRY RUN] " if dry_run else ""}Processing {len(users)} employee(s)...'
        )

        with transaction.atomic():
            for user in users:
                rng = _seeded_random(user)
                changed = _fill_profile(user, rng)
                self.stdout.write(
                    f'  {user.employee_id or user.email}: {user.full_name} '
                    f'— {len(changed)} profile field(s) filled'
                )
                if not dry_run:
                    user.onboarding_status = User.ONBOARDING_COMPLETE
                    user.must_change_password = False
                    user.save(update_fields=['onboarding_status', 'must_change_password', 'updated_at'])

                    from apps.hrms.views.leave import _allocate_leaves_for_employee
                    _allocate_leaves_for_employee(user, user.date_of_joining)

            if dry_run:
                transaction.set_rollback(True)
            else:
                AuditLog.objects.create(
                    user=None,
                    action='bulk_onboarding_autocomplete',
                    module='accounts',
                    changes={
                        'employee_ids': [u.employee_id for u in users],
                        'count': len(users),
                    },
                )

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no changes were saved.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done. {len(users)} employee(s) marked onboarding complete.'
            ))
