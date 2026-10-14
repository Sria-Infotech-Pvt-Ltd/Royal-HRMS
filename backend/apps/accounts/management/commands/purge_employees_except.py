"""
Management command: purge_employees_except

DESTRUCTIVE. Deletes every employee (User row) except the one whose email
you pass with --keep-email, along with every real record that references
those employees (payroll, attendance, leave, documents, family, assets,
goals/reviews, etc.) via Django's own on_delete=CASCADE relationships.

This does NOT selectively wipe "employee data" while leaving User rows
behind — it deletes the User rows themselves, which is what actually
removes them from the Employee Directory, login, everywhere. Reference
data this app would need to keep working (Branch, Role, Permission,
LeaveType, SalaryStructure, holidays, etc.) is left untouched — only
User rows and everything that points at a User get removed.

A handful of relations are on_delete=PROTECT (deleting the referenced row
raises instead of cascading) rather than CASCADE, so they're cleared by
hand first, in dependency order, before the User rows themselves are
deleted:
  1. SalaryTransferItem   (employee + payslip are both PROTECT)
  2. EmployeePayslip      (employee is PROTECT)
  3. PayslipQuery         (raised_by is PROTECT)
  4. Placement            (employee is PROTECT — this employee's position
                           history)
  5. PayrollCycle.created_by — reassigned to whoever you're keeping,
     rather than deleted, since a cycle usually still has OTHER
     (kept) employees' payslips on it; deleting the whole cycle would
     destroy their payroll history too.

Everything else (AttendanceRecord, LeaveRequest, EmployeeDocumentSubmission,
FamilyMember, CompanyAsset, Goal, PerformanceReview, Expense, HRHelpRequest,
...) is on_delete=CASCADE on its employee FK, so it's removed automatically
the moment the User row is deleted — no need to touch those tables by hand.

Usage:
    python manage.py purge_employees_except --keep-email admin@sriainfotech.com --dry-run
    python manage.py purge_employees_except --keep-email admin@sriainfotech.com --confirm

--dry-run prints exactly what would be deleted/reassigned and touches
nothing. --confirm is required for the real run — plain
`purge_employees_except --keep-email ...` with neither flag does nothing
and tells you to pick one, so this can never run by accident.

Take a real database backup/snapshot before running this for real — it is
not reversible from inside the app.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Placement, User
from apps.payroll.models import EmployeePayslip, PayrollCycle, PayslipQuery, SalaryTransferItem


class Command(BaseCommand):
    help = 'DESTRUCTIVE. Deletes every employee except --keep-email. Use --dry-run first.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-email', required=True,
            help='Email of the one account to keep (e.g. admin@sriainfotech.com). Everyone else is deleted.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Print the plan; change nothing.')
        parser.add_argument('--confirm', action='store_true', help='Actually perform the deletion.')

    def handle(self, *args, **options):
        from django.conf import settings
        self.stdout.write(f"Database: {settings.DATABASES['default'].get('NAME')} @ "
                           f"{settings.DATABASES['default'].get('HOST')}")

        keep_email = options['keep_email']
        try:
            keep_user = User.objects.get(email__iexact=keep_email)
        except User.DoesNotExist as exc:
            raise CommandError(
                f'No user with email={keep_email!r} found in this database — '
                f'refusing to run (this would delete every employee, including the one you meant to keep).'
            ) from exc

        to_delete = User.objects.exclude(pk=keep_user.pk)
        count = to_delete.count()

        if not options['dry_run'] and not options['confirm']:
            raise CommandError('Pass --dry-run to preview, or --confirm to actually delete. Neither was given.')

        self.stdout.write(f'Keeping: {keep_user.email} ({keep_user.full_name or "no name"}, employee_id={keep_user.employee_id or "—"})')
        self.stdout.write(f'Deleting {count} other employee(s):')
        for u in to_delete.order_by('email'):
            self.stdout.write(f'  - {u.email}  ({u.full_name or "no name"}, employee_id={u.employee_id or "—"})')

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Nothing to delete — this is already the only account.'))
            return

        cycles_to_reassign = PayrollCycle.objects.filter(created_by__in=to_delete).exclude(created_by=keep_user)
        self.stdout.write(f'Would reassign {cycles_to_reassign.count()} payroll cycle(s)\' created_by to {keep_user.email}.')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('--dry-run: nothing was changed.'))
            return

        with transaction.atomic():
            # Clear PROTECT relations first, in dependency order, before the
            # User rows themselves can be deleted.
            SalaryTransferItem.objects.filter(employee__in=to_delete).delete()
            PayslipQuery.objects.filter(raised_by__in=to_delete).delete()
            EmployeePayslip.objects.filter(employee__in=to_delete).delete()
            Placement.objects.filter(employee__in=to_delete).delete()
            cycles_to_reassign.update(created_by=keep_user)

            deleted_count, _ = to_delete.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Deleted {deleted_count} row(s) total (User rows + everything CASCADE-linked to them). '
                f'Only {keep_user.email} remains.'
            ))
