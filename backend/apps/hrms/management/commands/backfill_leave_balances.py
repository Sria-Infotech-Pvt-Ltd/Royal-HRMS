"""
Preview or apply a one-time LeaveBalance backfill/sync for existing
LeavePolicy rows, against every currently-eligible active employee.

Exists for LeavePolicy rows that predate the automatic sync built into
LeavePolicyView.post()/put() (apps/hrms/views/leave.py) — a policy created
or edited before that sync existed never had its eligible employees
reconciled, and would otherwise wait for the next annual reset
(apps/hrms/tasks.py: reset_annual_leave_balances) to get a balance. Safe
to re-run for any policy at any time afterward too — idempotent via
get_or_create, same as every other LeaveBalance-creating path in this
codebase, so running it against a policy that's already fully synced is a
harmless no-op.

Defaults to dry-run (no database writes at all) — pass --apply to
actually create the missing LeaveBalance rows. The dry-run preview and the
real apply path share the exact same employee queryset and the same
_eligible_for_policy() check the apply path's _allocate_new_policy_for_
existing_employees() uses internally, so the preview's numbers are exactly
what --apply will do, never an approximation.

Usage:
    python manage.py backfill_leave_balances --schema tenant_demo2026
    python manage.py backfill_leave_balances --schema tenant_demo2026 --policy pink_leave
    python manage.py backfill_leave_balances --schema tenant_demo2026 --policy pink_leave --apply
    python manage.py backfill_leave_balances --company-code DEMO2026 --apply
    python manage.py backfill_leave_balances --all
"""
from datetime import date

from core.tenant_command import TenantCommand


class Command(TenantCommand):
    help = (
        'Preview (default) or apply a LeaveBalance backfill for existing LeavePolicy '
        'rows against every currently-eligible active employee. Requires --schema/'
        '--company-code/--all. Pass --apply to actually write; without it, this is a '
        'read-only dry-run — no database writes are made.'
    )

    def add_tenant_arguments(self, parser):
        parser.add_argument(
            '--policy', default=None,
            help='Limit to one LeavePolicy by its leave_type key (e.g. pink_leave). Omit to run every active policy.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually create the missing LeaveBalance rows. Without this flag, nothing is written.',
        )

    def handle_tenant(self, client, *args, **options):
        from apps.accounts.models import User
        from apps.hrms.models import LeaveBalance, LeavePolicy
        from apps.hrms.views.leave import _allocate_new_policy_for_existing_employees, _eligible_for_policy

        policy_key    = options.get('policy')
        apply_changes = options.get('apply', False)
        today = date.today()
        year  = today.year

        policies = LeavePolicy.objects.filter(is_active=True)
        if policy_key:
            policies = policies.filter(leave_type=policy_key)
        if not policies.exists():
            self.stdout.write('    No matching active LeavePolicy found.')
            return

        # Same queryset _allocate_new_policy_for_existing_employees() uses
        # internally — keeps the dry-run preview and the real --apply run
        # from ever disagreeing about who counts as "an active employee".
        employees = list(
            User.objects.filter(is_active=True).exclude(employee_id='').select_related('profile')
        )

        for policy in policies:
            label    = policy.leave_type_label or policy.leave_type
            eligible = [e for e in employees if _eligible_for_policy(e, policy, today)]

            existing_ids = set(
                LeaveBalance.objects.filter(
                    employee__in=eligible, leave_type=policy.leave_type, year=year,
                ).values_list('employee_id', flat=True)
            )
            missing = [e for e in eligible if e.pk not in existing_ids]

            self.stdout.write(f'  Policy "{label}" ({policy.leave_type}):')
            self.stdout.write(f'    Eligible employees:  {len(eligible)}')
            self.stdout.write(f'    Missing balance:     {len(missing)}')
            for e in missing:
                self.stdout.write(f'      - {e.employee_id or e.pk} {e.email} ({e.full_name})')

            if not apply_changes:
                if missing:
                    self.stdout.write(self.style.WARNING(
                        '    [DRY RUN] No balances written. Re-run with --apply to create them.'
                    ))
                continue

            created = _allocate_new_policy_for_existing_employees(policy, today)
            self.stdout.write(self.style.SUCCESS(f'    Created {created} LeaveBalance row(s).'))
