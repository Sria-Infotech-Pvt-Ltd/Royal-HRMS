"""
Management command: seed_company_structure

Sets up the company, its branches ("Company Codes" in the UI) and its service / department structure from a JSON file
(default: apps/accounts/seed_data/sri_infotech_setup.json). It goes through the app's own serializers, so every value is
validated by the same rules as the Company Settings, Branches and Org Structure screens, and branch codes come from the
same generator.

Idempotent: running it again creates nothing new. Matching is by name
  - company : the single Company row (an existing company with a different name is left alone and reported);
  - branch  : branch name, case-insensitive;
  - unit    : name (or a listed alias) under the same parent, case-insensitive. An existing unit is REUSED, never duplicated
              or renamed, and only marked as a department (is_department_level).

Run:  python manage.py seed_company_structure [--file PATH] [--actor-email EMAIL] [--dry-run]
`--actor-email` names an existing user to record in the audit log, exactly as the screens do. Without it no audit rows are written.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import AuditLog, Company, OrgUnit, User
from apps.accounts.serializers import CompanySerializer, OrgUnitSerializer
from apps.branch.models import Branch, City, State
from apps.branch.serializers import BranchSerializer
from core.responses import first_error

DEFAULT_FILE = Path(__file__).resolve().parents[2] / 'seed_data' / 'sri_infotech_setup.json'


@dataclass
class Report:
    created: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Command(BaseCommand):
    help = 'Create the company, branches and service/department structure from a JSON file (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE), help='JSON file to read (default: the Sri Infotech setup).')
        parser.add_argument('--actor-email', default='', help='Existing user to record in the audit log.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be created; write nothing.')

    def handle(self, *args, **options):
        spec = self._load(options['file'])
        actor = self._actor(options['actor_email'])
        dry_run = options['dry_run']
        report = Report()
        with transaction.atomic():
            self._company(spec.get('company'), actor, dry_run, report)
            self._branches(spec.get('branches', []), actor, dry_run, report)
            self._departments(spec.get('departments'), actor, dry_run, report)
            if dry_run:
                transaction.set_rollback(True)
        self._print(report, dry_run)

    # ── input ────────────────────────────────────────────────────────────────
    @staticmethod
    def _load(path: str) -> dict:
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Could not read {path}: {exc}') from exc

    @staticmethod
    def _actor(email: str):
        if not email:
            return None
        actor = User.objects.filter(email__iexact=email).first()
        if actor is None:
            raise CommandError('--actor-email does not match an existing user.')
        return actor

    @staticmethod
    def _audit(actor, action: str, module: str, obj, changes: dict) -> None:
        if actor is not None:
            AuditLog.objects.create(user=actor, action=action, module=module, object_id=str(obj.pk), changes=changes)

    # ── company ──────────────────────────────────────────────────────────────
    def _company(self, spec, actor, dry_run: bool, report: Report) -> None:
        if not spec:
            return
        existing = Company.objects.first()
        if existing is not None:
            if existing.company_name.strip().lower() == spec['company_name'].strip().lower():
                report.reused.append(f'Company: {existing.company_name}')
            else:
                report.warnings.append(f'A different company already exists ({existing.company_name}); left unchanged.')
            return
        # is_draft: the profile is saved with just name, address and city; the legal details are completed in Company Settings.
        serializer = CompanySerializer(data={**spec, 'is_draft': True})
        if not serializer.is_valid():
            raise CommandError(f'Company: {first_error(serializer.errors)}')
        report.created.append(f'Company: {spec["company_name"]}')
        if dry_run:
            return
        instance = serializer.save(**({'updated_by': actor} if actor else {}))
        from core.cache_service import CompanyCacheService, FinancialYearCacheService
        CompanyCacheService.invalidate()
        FinancialYearCacheService.invalidate()
        self._audit(actor, 'create', 'company', instance, {})

    # ── branches ─────────────────────────────────────────────────────────────
    def _branches(self, specs: list, actor, dry_run: bool, report: Report) -> None:
        for spec in specs:
            name = spec['branch_name']
            existing = Branch.objects.filter(branch_name__iexact=name).first()
            if existing is not None:
                report.reused.append(f'Branch: {existing.branch_name} ({existing.branch_code})')
                continue
            state = State.objects.filter(name__iexact=spec['state']).first()
            if state is None:
                raise CommandError(f'Branch {name}: state "{spec["state"]}" does not exist.')
            city = City.objects.filter(state=state, name__iexact=spec['city']).first()
            data = {'branch_name': name, 'address': spec['address'], 'state': state.pk}
            data.update({'city': city.pk} if city else {'new_city_name': spec['city']})  # same fallback the Branch screen offers
            serializer = BranchSerializer(data=data)
            if not serializer.is_valid():
                raise CommandError(f'Branch {name}: {first_error(serializer.errors)}')
            if dry_run:
                report.created.append(f'Branch: {name} ({spec["city"]}, {state.name})')
                continue
            branch = serializer.save()
            report.created.append(f'Branch: {branch.branch_name} ({branch.branch_code}) - {branch.city.name}, {branch.state.name}')
            self._audit(actor, 'branch_created', 'branch', branch, {'branch_code': branch.branch_code, 'branch_name': branch.branch_name})

    # ── services / departments ───────────────────────────────────────────────
    def _departments(self, spec, actor, dry_run: bool, report: Report) -> None:
        if not spec:
            return
        parent = None
        for name in spec.get('parent_path', []):
            parent = OrgUnit.objects.filter(parent=parent, name__iexact=name).first()
            if parent is None:
                raise CommandError(f'Org unit "{name}" (under "{"/".join(spec["parent_path"])}") does not exist.')
        for unit_spec in spec['units']:
            self._unit(unit_spec, parent, actor, dry_run, report, [])

    def _unit(self, spec: dict, parent, actor, dry_run: bool, report: Report, trail: list) -> None:
        names = [spec['name'], *spec.get('aliases', [])]
        match = Q()
        for name in names:
            match |= Q(name__iexact=name)
        unit = OrgUnit.objects.filter(match, parent=parent).first() if (parent is not None or not trail) else None
        path = ' / '.join([*trail, spec['name']])
        if unit is not None:
            note = '' if unit.name == spec['name'] else f' (existing "{unit.name}" reused)'
            self._mark_department(unit, dry_run)
            report.reused.append(f'Department: {path}{note}')
        else:
            unit = self._create_unit(spec['name'], parent, actor, dry_run, report, path)
        for child in spec.get('children', []):
            self._unit(child, unit, actor, dry_run, report, [*trail, spec['name']])

    @staticmethod
    def _mark_department(unit: OrgUnit, dry_run: bool) -> None:
        if unit.is_department_level or dry_run:
            return
        serializer = OrgUnitSerializer(unit, data={'is_department_level': True}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

    def _create_unit(self, name: str, parent, actor, dry_run: bool, report: Report, path: str):
        if dry_run:
            report.created.append(f'Department: {path}')
            return None
        serializer = OrgUnitSerializer(data={'name': name, 'parent': parent.pk if parent else None, 'is_department_level': True})
        if not serializer.is_valid():
            raise CommandError(f'Department {path}: {first_error(serializer.errors)}')
        unit = serializer.save()
        report.created.append(f'Department: {path}')
        self._audit(actor, 'create', 'org_structure', unit, {'name': unit.name})
        return unit

    # ── output ───────────────────────────────────────────────────────────────
    def _print(self, report: Report, dry_run: bool) -> None:
        label = 'DRY RUN - nothing was written. Would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(f'{label} {len(report.created)}; reused {len(report.reused)}.'))
        for line in report.created:
            self.stdout.write(f'  + {line}')
        for line in report.reused:
            self.stdout.write(f'  = {line}')
        for line in report.warnings:
            self.stdout.write(self.style.WARNING(f'  ! {line}'))
