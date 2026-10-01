"""
Management command: dry_run_employee_id_conversion

READ-ONLY preview of what converting every existing employee's old
Employee ID to the new prefix+DDMM+initials format would look like.
Makes ZERO database writes — computes the proposed mapping in memory and
prints a report. Does not implement the actual conversion.

Reuses the real EmployeeCodeSettings._initials() helper (the exact same
code new-employee generation already calls) rather than re-implementing
the initials rule, so this preview can never silently drift from actual
generation behavior.

Deterministic ordering (see _sort_key() below): employees are processed
in ascending (date_of_joining, date_joined, employee_id) order, so within
any collision group, whoever joined earliest keeps the bare id and later
joiners receive the numeric suffix. date_of_joining is the primary key
because it is the real-world, business-meaningful "who was here first";
date_joined (account-creation timestamp, always present, never null) is
the tiebreaker for same-day joiners or anyone missing date_of_joining;
employee_id (the OLD code) is the final tiebreaker for full reproducibility
if the first two are ever identical. Re-running this command against an
unchanged database always produces an identical mapping.

Active AND inactive employees are both included and both count toward
collision detection — an old ID must never be reused, including one that
belonged to someone who has since exited.

Usage:
    python manage.py dry_run_employee_id_conversion --schema tenant_royalhrms
    python manage.py dry_run_employee_id_conversion --company-code ROYALHRMS
    python manage.py dry_run_employee_id_conversion --all
"""
from datetime import date

from apps.accounts.models import EmployeeCodeSettings, User
from core.tenant_command import TenantCommand


def _sort_key(user: User):
    has_doj = user.date_of_joining is not None
    return (
        0 if has_doj else 1,
        user.date_of_joining or date.max,
        user.date_joined,
        user.employee_id,
    )


class Command(TenantCommand):
    help = (
        'READ-ONLY dry run: preview the old-ID -> new-ID mapping for converting '
        'every existing employee to the new Employee ID format. Makes no database '
        'writes. Requires --schema/--company-code/--all.'
    )

    def handle_tenant(self, client, *args, **options):
        cfg = EmployeeCodeSettings.get()
        prefix = cfg.prefix or 'EMP'

        # Candidates with no employee_id yet (not-yet-approved portal
        # onboarding) are not real employees for this purpose — same
        # .exclude(employee_id='') convention EmployeeListCreateView.get()
        # already uses.
        employees = list(
            User.objects.exclude(employee_id='').order_by('employee_id')
        )

        valid: list[User] = []
        invalid: list[tuple[User, str]] = []
        for u in employees:
            full_name = (u.full_name or '').strip()
            if not full_name:
                invalid.append((u, 'missing/blank name'))
                continue
            if u.date_of_joining is None:
                invalid.append((u, 'missing date of joining'))
                continue
            valid.append(u)

        valid.sort(key=_sort_key)

        # ── Compute proposed ids + collisions, in deterministic order ──────
        base_to_users: dict[str, list[User]] = {}
        mapping: list[dict] = []
        for u in valid:
            parts = full_name_parts = (u.full_name or '').strip().split(' ', 1)
            first_name = parts[0]
            last_name  = parts[1] if len(parts) > 1 else ''
            initials = EmployeeCodeSettings._initials(first_name, last_name)
            ddmm = u.date_of_joining.strftime('%d%m')
            base = f'{prefix}{ddmm}{initials}'
            base_to_users.setdefault(base, []).append(u)

        for base, users_in_group in base_to_users.items():
            group_size = len(users_in_group)
            for idx, u in enumerate(users_in_group):
                new_id = base if idx == 0 else f'{base}{idx + 1}'
                mapping.append({
                    'user': u,
                    'old_id': u.employee_id,
                    'new_id': new_id,
                    'base': base,
                    'group_size': group_size,
                    'position': idx + 1,
                })

        # Stable, reproducible print order: by old employee_id.
        mapping.sort(key=lambda m: m['old_id'])

        self._print_report(client, employees, mapping, invalid, base_to_users)

    # ── Reporting ────────────────────────────────────────────────────────

    def _print_report(self, client, employees, mapping, invalid, base_to_users):
        w = self.stdout.write
        w(self.style.WARNING(
            'READ-ONLY DRY RUN — no database writes will be made.\n'
        ))

        w(f'Tenant: {client.company_code} ({client.schema_name})')
        w(f'Total employee rows considered: {len(employees)}')
        w(f'Total with usable name + date of joining: {len(mapping)}')
        w(f'Total missing/invalid data (excluded from mapping): {len(invalid)}')

        collision_groups = {b: us for b, us in base_to_users.items() if len(us) > 1}
        suffixed_count = sum(len(us) - 1 for us in collision_groups.values())
        changed_count = sum(1 for m in mapping if m['old_id'] != m['new_id'])

        w(f'Total collision groups (2+ employees sharing DDMM+initials): {len(collision_groups)}')
        w(f'Total employees that would receive a numeric suffix: {suffixed_count}')
        w(f'Total IDs that would actually change: {changed_count}')
        w('')

        # ── Full mapping ────────────────────────────────────────────────
        w(self.style.NOTICE('--- Full mapping (old -> new) ---'))
        for m in mapping:
            u = m['user']
            doj = u.date_of_joining.strftime('%d/%m/%Y')
            status = (
                'No collision' if m['group_size'] == 1
                else f'Collision group of {m["group_size"]} (position {m["position"]}, base {m["base"]})'
            )
            changed = '' if m['old_id'] == m['new_id'] else '  [CHANGES]'
            active = '' if u.is_active else '  [INACTIVE]'
            w(f'{m["old_id"]:>12}  ->  {m["new_id"]:<14}  {u.full_name:<30} '
              f'DOJ {doj}  {status}{changed}{active}')
        w('')

        # ── Collision groups, separately ───────────────────────────────
        if collision_groups:
            w(self.style.NOTICE('--- Collision groups ---'))
            for base, users_in_group in collision_groups.items():
                w(f'Base id {base}:')
                ordered = sorted(users_in_group, key=_sort_key)
                for idx, u in enumerate(ordered):
                    new_id = base if idx == 0 else f'{base}{idx + 1}'
                    doj = u.date_of_joining.strftime('%d/%m/%Y')
                    w(f'    {u.employee_id:>12}  ->  {new_id:<14}  {u.full_name}  (DOJ {doj})')
            w('')
        else:
            w('No collision groups found.\n')

        # ── Missing/invalid data ────────────────────────────────────────
        if invalid:
            w(self.style.NOTICE('--- Employees excluded (missing/invalid data) ---'))
            for u, reason in invalid:
                w(f'{u.employee_id:>12}  {u.full_name or "(no name)":<30}  reason: {reason}')
            w('')
        else:
            w('No employees with missing/invalid data.\n')

        # ── Sample ──────────────────────────────────────────────────────
        w(self.style.NOTICE('--- Sample (first 10 rows of full mapping) ---'))
        for m in mapping[:10]:
            u = m['user']
            doj = u.date_of_joining.strftime('%d/%m/%Y')
            status = 'No collision' if m['group_size'] == 1 else f'Collision (suffix {m["position"]} of {m["group_size"]})'
            w(f'{m["old_id"]} -> {m["new_id"]} -> {u.full_name} -> {doj} -> {status}')

        w('')
        w(self.style.SUCCESS('Dry run complete. Zero database writes were made.'))
