"""
Management command: convert_employee_ids

Converts existing employees' Employee IDs to the prefix + DDMM + initials
format (e.g. RSS0308TG) for ONE company. PREVIEW BY DEFAULT — nothing is
written unless --apply is passed.

Rules:
- New id = <--prefix> + date_of_joining as DDMM + EmployeeCodeSettings._initials()
  (first word + last word of full_name — the same rule new-employee
  generation uses, so the two can never drift apart).
- --skip <old ids...> leaves those employees completely untouched; their
  current ids stay reserved so nobody is converted onto them.
- Same base id for several employees: ACTIVE employees first, then
  date_of_joining, date_joined, old id — the earliest gets the bare id,
  the rest get 2, 3, ... (same suffix style as generate_employee_id()).
- An employee with no name or no date_of_joining makes --apply refuse to
  run: fill the data in, or list them in --skip.

On --apply, inside ONE transaction:
- every employee_id is updated, and EmployeeCodeSettings.prefix is set to
  --prefix so employees created afterwards get the same format;
- one AuditLog row (action 'employee_id_bulk_conversion') records the full
  old -> new mapping;
- a CSV of the mapping (user uuid, old id, new id) is written to
  --mapping-file BEFORE the transaction commits — if the file can't be
  written, nothing is changed.

--revert <csv> restores old ids from such a CSV (only for employees whose
id is still the converted one) and puts the previous prefix back.

Usage:
    python manage.py convert_employee_ids --company-code RIS --prefix RSS --skip RIS00049 RIS00050
    python manage.py convert_employee_ids --company-code RIS --prefix RSS --skip ... --apply --mapping-file /path/map.csv
    python manage.py convert_employee_ids --company-code RIS --revert /path/to/mapping.csv --apply
"""
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime

from django.core.management.base import CommandError
from django.db import transaction

from apps.accounts.models import AuditLog, EmployeeCodeSettings, User
from core.tenant_command import TenantCommand


@dataclass
class Candidate:
    pk: object
    old_id: str
    full_name: str
    date_of_joining: date | None
    date_joined: datetime
    is_active: bool


def plan_conversion(candidates, prefix, skip_ids):
    """Pure planning step (no DB access) — returns (mapping, skipped, invalid).

    mapping: list of dicts {pk, old_id, new_id, base, suffixed, candidate}
    skipped: candidates whose old id is in skip_ids (left untouched)
    invalid: list of (candidate, reason) — missing name / date of joining
    """
    skip_ids = set(skip_ids)
    skipped = [c for c in candidates if c.old_id in skip_ids]
    invalid, valid = [], []
    for c in candidates:
        if c.old_id in skip_ids:
            continue
        name = ' '.join((c.full_name or '').split())
        if not name:
            invalid.append((c, 'missing/blank name'))
        elif c.date_of_joining is None:
            invalid.append((c, 'missing date of joining'))
        else:
            valid.append(c)

    # Ids that stay as they are can't be handed to anyone else.
    taken = {c.old_id for c in skipped} | {c.old_id for c, _ in invalid}

    valid.sort(key=lambda c: (not c.is_active, c.date_of_joining, c.date_joined, c.old_id))
    mapping = []
    for c in valid:
        words = ' '.join(c.full_name.split()).split(' ')
        initials = EmployeeCodeSettings._initials(words[0], ' '.join(words[1:]))
        base = f'{prefix}{c.date_of_joining.strftime("%d%m")}{initials}'
        new_id, suffix = base, 2
        while new_id in taken:
            new_id = f'{base}{suffix}'
            suffix += 1
        taken.add(new_id)
        mapping.append({
            'pk': c.pk, 'old_id': c.old_id, 'new_id': new_id,
            'base': base, 'suffixed': new_id != base, 'candidate': c,
        })
    return mapping, skipped, invalid


class Command(TenantCommand):
    help = (
        'Convert existing Employee IDs to prefix+DDMM+initials for one company. '
        'Preview only unless --apply is given.'
    )

    def add_tenant_arguments(self, parser):
        parser.add_argument('--prefix', help='Target prefix, e.g. RSS.')
        parser.add_argument('--skip', nargs='*', default=[],
                            help='Old employee ids to leave untouched.')
        parser.add_argument('--apply', action='store_true',
                            help='Actually write the changes (default: preview only).')
        parser.add_argument('--mapping-file', default=None,
                            help='Where to write the old->new CSV on --apply (required with --apply; '
                                 'must not already exist).')
        parser.add_argument('--revert', default=None,
                            help='Restore old ids from a mapping CSV written by a previous --apply.')

    def handle(self, *args, **options):
        # Fail closed: this command is for exactly one company at a time.
        if options.get('all'):
            raise CommandError('--all is not allowed; pass --company-code or --schema.')
        super().handle(*args, **options)

    def handle_tenant(self, client, *args, **options):
        if options.get('revert'):
            return self._revert(client, options['revert'], options['apply'])

        prefix = (options.get('prefix') or '').strip().upper()
        if not prefix or not prefix.isalnum() or len(prefix) > 10:
            raise CommandError('--prefix is required (letters/digits, max 10), e.g. --prefix RSS.')

        users = list(User.objects.exclude(employee_id='').order_by('employee_id'))
        unknown = set(options['skip']) - {u.employee_id for u in users}
        if unknown:
            raise CommandError(f'--skip ids not found in {client.company_code}: {sorted(unknown)}')

        dupes = sorted({u.employee_id for u in users if sum(v.employee_id == u.employee_id for v in users) > 1})
        if dupes:
            raise CommandError(f'Duplicate current ids, fix these first: {dupes}')

        candidates = [
            Candidate(u.pk, u.employee_id, u.full_name, u.date_of_joining, u.date_joined, u.is_active)
            for u in users
        ]
        mapping, skipped, invalid = plan_conversion(candidates, prefix, options['skip'])
        self._print_plan(client, prefix, users, mapping, skipped, invalid)

        if not options['apply']:
            self.stdout.write(self.style.WARNING('PREVIEW ONLY — no changes were made. Re-run with --apply to convert.'))
            return
        if invalid:
            raise CommandError('Refusing to --apply: some employees have missing data (listed above). '
                               'Fill it in, or add their ids to --skip.')

        if not options.get('mapping_file'):
            raise CommandError('--apply needs --mapping-file <path> (where the old->new CSV is saved for revert).')
        path = os.path.abspath(options['mapping_file'])
        changes = [m for m in mapping if m['old_id'] != m['new_id']]

        with transaction.atomic():
            cfg = EmployeeCodeSettings.objects.select_for_update().get_or_create(
                pk=1, defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 1},
            )[0]
            old_prefix = cfg.prefix
            # Re-check under the lock that nobody's id changed since planning.
            current = dict(User.objects.filter(pk__in=[m['pk'] for m in mapping])
                           .values_list('pk', 'employee_id'))
            moved = [m['old_id'] for m in mapping if current.get(m['pk']) != m['old_id']]
            if moved:
                raise CommandError(f'Employee ids changed while running, nothing written: {moved}')

            with open(path, 'x', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(['user_id', 'old_employee_id', 'new_employee_id', 'old_prefix', 'new_prefix'])
                for m in changes:
                    w.writerow([m['pk'], m['old_id'], m['new_id'], old_prefix, prefix])
            os.chmod(path, 0o600)

            for m in changes:
                User.objects.filter(pk=m['pk']).update(employee_id=m['new_id'])
            cfg.prefix = prefix
            cfg.save(update_fields=['prefix', 'updated_at'])

            AuditLog.objects.create(
                user=None,
                action='employee_id_bulk_conversion',
                module='employees',
                changes={
                    'old_prefix': old_prefix, 'new_prefix': prefix,
                    'converted': {m['old_id']: m['new_id'] for m in changes},
                    'skipped': [c.old_id for c in skipped],
                    'mapping_file': path,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'APPLIED: {len(changes)} employee ids converted, prefix {old_prefix} -> {prefix}. '
            f'Mapping saved to {path}'
        ))

    # ── Revert ───────────────────────────────────────────────────────────

    def _revert(self, client, path, apply):
        with open(path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise CommandError(f'{path} has no rows.')
        old_prefix = rows[0]['old_prefix']

        by_pk = {str(u.pk): u for u in User.objects.filter(pk__in=[r['user_id'] for r in rows])}
        revertable, mismatched = [], []
        for r in rows:
            u = by_pk.get(r['user_id'])
            if u and u.employee_id == r['new_employee_id']:
                revertable.append(r)
            else:
                mismatched.append((r, u.employee_id if u else '(user missing)'))

        in_use = set(User.objects.exclude(pk__in=[r['user_id'] for r in revertable])
                     .values_list('employee_id', flat=True))
        clash = [r['old_employee_id'] for r in revertable if r['old_employee_id'] in in_use]

        self.stdout.write(f'Tenant: {client.company_code} ({client.schema_name})')
        self.stdout.write(f'Would restore: {len(revertable)}   prefix -> {old_prefix}')
        for r in revertable:
            self.stdout.write(f'{r["new_employee_id"]:>14}  ->  {r["old_employee_id"]}')
        for r, cur in mismatched:
            self.stdout.write(self.style.WARNING(
                f'NOT restoring {r["old_employee_id"]}: id is now {cur}, not {r["new_employee_id"]}'))
        if clash:
            raise CommandError(f'Old ids already used by someone else, nothing written: {clash}')
        if not apply:
            self.stdout.write(self.style.WARNING('PREVIEW ONLY — no changes were made. Re-run with --apply to revert.'))
            return

        with transaction.atomic():
            for r in revertable:
                User.objects.filter(pk=r['user_id'], employee_id=r['new_employee_id']) \
                    .update(employee_id=r['old_employee_id'])
            EmployeeCodeSettings.objects.filter(pk=1).update(prefix=old_prefix)
            AuditLog.objects.create(
                user=None,
                action='employee_id_bulk_conversion_reverted',
                module='employees',
                changes={'restored': {r['new_employee_id']: r['old_employee_id'] for r in revertable},
                         'prefix': old_prefix, 'mapping_file': path},
            )
        self.stdout.write(self.style.SUCCESS(f'REVERTED: {len(revertable)} ids restored, prefix -> {old_prefix}.'))

    # ── Reporting ────────────────────────────────────────────────────────

    def _print_plan(self, client, prefix, users, mapping, skipped, invalid):
        w = self.stdout.write
        changed = [m for m in mapping if m['old_id'] != m['new_id']]
        w(f'Tenant: {client.company_code} ({client.schema_name})   target prefix: {prefix}')
        w(f'Employees: {len(users)}   to convert: {len(changed)}   skipped: {len(skipped)}   '
          f'missing data: {len(invalid)}   with numeric suffix: {sum(m["suffixed"] for m in mapping)}')
        w('')
        w(f'{"old id":<12}  {"new id":<14}  {"DOJ":<10}  status')
        for m in sorted(mapping, key=lambda m: m['old_id']):
            c = m['candidate']
            notes = [] if c.is_active else ['INACTIVE']
            if m['suffixed']:
                notes.append(f'SUFFIX (base {m["base"]} taken)')
            w(f'{m["old_id"]:<12}  {m["new_id"]:<14}  {c.date_of_joining:%d/%m/%Y}  {" ".join(notes)}')
        for c in skipped:
            w(f'{c.old_id:<12}  {"(unchanged)":<14}  {"":<10}  SKIPPED{"" if c.is_active else " INACTIVE"}')
        for c, reason in invalid:
            w(self.style.ERROR(f'{c.old_id:<12}  {"(cannot)":<14}  {"":<10}  {reason}'))
        w('')
