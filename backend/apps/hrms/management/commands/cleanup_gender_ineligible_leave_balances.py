"""
Preview or remove LeaveBalance rows that employees should never have received
because of a leave type's gender rule (e.g. a female-only "Pink Leave" balance
held by a male employee).

How these rows appeared: a leave type created with gender "All" gives every
employee a balance at once; narrowing it to one gender later never removes the
balances already given (by design — see _allocate_new_policy_for_existing_employees()).

Only rows that are completely unused are removed. A row is skipped — and listed
for HR to review — when ANY of these is true:
  * days have been used (used_days > 0);
  * it has credit history (LeaveCreditTransaction rows would be deleted with it);
  * the employee has a leave request of that type in that year (any status);
  * the employee has no gender recorded (eligibility can't be decided).

Defaults to a dry run (no database writes). Pass --apply to delete. Prints
employee IDs only.

Usage:
    python manage.py cleanup_gender_ineligible_leave_balances --schema tenant_ris
    python manage.py cleanup_gender_ineligible_leave_balances --schema tenant_ris --policy menstrual_leave
    python manage.py cleanup_gender_ineligible_leave_balances --schema tenant_ris --policy menstrual_leave --apply
    python manage.py cleanup_gender_ineligible_leave_balances --all --year 2026
"""
from datetime import date

from core.tenant_command import TenantCommand


class Command(TenantCommand):
    help = (
        'Preview (default) or remove unused LeaveBalance rows held by employees whose gender '
        'the leave type does not allow. Requires --schema/--company-code/--all. Pass --apply '
        'to delete; without it nothing is written.'
    )

    def add_tenant_arguments(self, parser):
        parser.add_argument('--policy', default=None,
                            help='Limit to one leave type by its key (e.g. menstrual_leave).')
        parser.add_argument('--year', type=int, default=None,
                            help='Leave year to clean (default: the current year).')
        parser.add_argument('--apply', action='store_true',
                            help='Actually delete the rows. Without this flag, nothing is written.')

    def handle_tenant(self, client, *args, **options):
        from django.core.cache import cache
        from django.db import transaction

        from apps.hrms.models import LeaveBalance, LeavePolicy, LeaveRequest

        policy_key = options.get('policy')
        year = options.get('year') or date.today().year
        apply_changes = options.get('apply', False)

        policies = LeavePolicy.objects.exclude(applicable_gender__in=('', 'all')).order_by('leave_type')
        if policy_key:
            policies = policies.filter(leave_type=policy_key)
        if not policies.exists():
            self.stdout.write('    No gender-restricted leave type found.')
            return

        total_removed = 0
        for policy in policies:
            label = policy.leave_type_label or policy.leave_type
            rows = (LeaveBalance.objects.filter(leave_type=policy.leave_type, year=year)
                    .select_related('employee', 'employee__profile'))
            removable, review = [], []
            for b in rows:
                profile = getattr(b.employee, 'profile', None)
                gender = ((profile.gender if profile else '') or '').lower()
                if gender == policy.applicable_gender:
                    continue                                        # eligible — not touched
                emp = b.employee.employee_id or str(b.employee_id)
                reasons = []
                if not gender:
                    reasons.append('no gender recorded')
                if b.used_days:
                    reasons.append(f'{b.used_days} day(s) used')
                if b.credit_transactions.exists():
                    reasons.append('has credit history')
                if LeaveRequest.objects.filter(employee_id=b.employee_id, leave_type=policy.leave_type,
                                               start_date__year=year).exists():
                    reasons.append('has a leave request')
                (review if reasons else removable).append((b, emp, gender, reasons))

            self.stdout.write(f'  Leave type "{label}" ({policy.leave_type}), only for: {policy.applicable_gender}, '
                              f'year {year}:')
            self.stdout.write(f'    Unused balances to remove: {len(removable)}')
            for b, emp, gender, _ in removable:
                self.stdout.write(f'      - {emp} (gender: {gender}) {b.total_days} day(s) credited, 0 used')
            self.stdout.write(f'    Kept for HR review:        {len(review)}')
            for b, emp, gender, reasons in review:
                self.stdout.write(f'      - {emp} (gender: {gender or "-"}): {", ".join(reasons)}')

            if not apply_changes:
                if removable:
                    self.stdout.write(self.style.WARNING('    [DRY RUN] Nothing deleted. Re-run with --apply to remove them.'))
                continue

            with transaction.atomic():
                ids = [b.pk for b, *_ in removable]
                # Re-check inside the transaction: still unused, no credit history.
                _, per_model = (LeaveBalance.objects.filter(pk__in=ids, used_days=0, credit_transactions__isnull=True)
                                .delete())
                deleted = per_model.get(LeaveBalance._meta.label, 0)
            for b, *_ in removable:
                cache.delete(f'dashboard:employee:leave_balance:{b.employee_id}:{year}')
            total_removed += deleted
            self.stdout.write(self.style.SUCCESS(f'    Removed {deleted} LeaveBalance row(s).'))

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f'  Total removed: {total_removed}'))
