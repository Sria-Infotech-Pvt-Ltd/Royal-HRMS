"""
Salary structure import and structure-assignment import (Settings → Payroll →
Salary Structures).

Structures: one row per component —
  Structure Name, Description, Component, Type, Calculation, Value, Role, Taxable, Order
Rows are grouped by structure name and validated with the same rules as
Assign CTC (services_salary_components.parse_components) plus: exactly one
Basic, and % of CTC components totalling at most 100. A name that already
exists is an error unless the caller explicitly allows updating existing
structures; an update matches components by name, adds new ones and
deactivates the ones no longer listed. Existing employee salary revisions
keep their own component copies and are never touched.

Assignments: Employee ID, Structure Name, Effective From — each valid row
saves a NEW salary revision through save_revision (same CTC as the
employee's current revision, the structure's components copied), exactly as
Assign CTC does. Nothing is written by a preview; the confirm request
re-reads and re-validates the whole file.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models.functions import Upper

from apps.accounts.models import User
from apps.payroll.models import EmployeeSalaryConfig, SalaryComponent, SalaryStructure
from apps.payroll.services_salary_components import (
    RevisionNotAllowed, parse_components, resolve_template_structure, revision_problem, role_for_name,
    save_revision, specs_from_structure,
)

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 1000

STRUCTURE_HEADERS = ['Structure Name', 'Description', 'Component', 'Type', 'Calculation', 'Value',
                     'Role', 'Taxable', 'Order']
STRUCTURE_SAMPLE_ROWS = [
    ['Staff Standard', 'Basic 50% of CTC', 'Basic', 'earning', 'percentage_of_ctc', '50', 'basic', 'yes', '1'],
    ['Staff Standard', '', 'HRA', 'allowance', 'percentage_of_basic', '40', 'hra', 'yes', '2'],
    ['Staff Standard', '', 'Interim Bonus', 'earning', 'percentage_of_basic', '8.33', 'other', 'yes', '3'],
    ['Staff Standard', '', 'Special Allowance', 'allowance', 'percentage_of_ctc', '25', 'special_allowance', 'yes', '4'],
    ['Site Staff', '', 'Basic', 'earning', 'fixed', '13325', 'basic', 'yes', '1'],
    ['Site Staff', '', 'HRA', 'allowance', 'fixed', '899', 'hra', 'yes', '2'],
    ['Site Staff', '', 'Uniform', 'deduction', 'fixed', '0', 'other', 'no', '3'],
]
ASSIGN_HEADERS = ['Employee ID', 'Structure Name', 'Effective From']
ASSIGN_SAMPLE_ROWS = [['EMP001', 'Staff Standard', '2026-12-01'], ['EMP002', 'Site Staff', '2026-12-01']]

_STRUCTURE_COLUMNS = {
    'structure name': 'structure', 'structure': 'structure', 'salary structure': 'structure',
    'description': 'description',
    'component': 'component', 'component name': 'component',
    'type': 'type', 'component type': 'type',
    'calculation': 'calculation', 'calculation type': 'calculation', 'calculation method': 'calculation',
    'value': 'value', 'amount': 'value', 'percentage': 'value',
    'role': 'role',
    'taxable': 'taxable', 'is taxable': 'taxable',
    'order': 'order', 'display order': 'order',
}
_ASSIGN_COLUMNS = {
    'employee id': 'employee_id', 'employee_id': 'employee_id', 'employee code': 'employee_id', 'emp id': 'employee_id',
    'structure name': 'structure', 'structure': 'structure', 'salary structure': 'structure',
    'effective from': 'effective_from', 'effective date': 'effective_from', 'effective_from': 'effective_from',
}
_TYPE_ALIASES = {
    'earning': SalaryComponent.TYPE_EARNING, 'allowance': SalaryComponent.TYPE_ALLOWANCE,
    'deduction': SalaryComponent.TYPE_DEDUCTION,
}
_CALC_ALIASES = {
    'percentage_of_ctc': SalaryComponent.CALC_PCT_CTC, '% of ctc': SalaryComponent.CALC_PCT_CTC,
    'percent of ctc': SalaryComponent.CALC_PCT_CTC, 'percentage of ctc': SalaryComponent.CALC_PCT_CTC,
    'percentage_of_basic': SalaryComponent.CALC_PCT_BASIC, '% of basic': SalaryComponent.CALC_PCT_BASIC,
    'percent of basic': SalaryComponent.CALC_PCT_BASIC, 'percentage of basic': SalaryComponent.CALC_PCT_BASIC,
    'fixed': SalaryComponent.CALC_FIXED, 'fixed amount': SalaryComponent.CALC_FIXED,
}
_ROLE_ALIASES = {
    'basic': SalaryComponent.ROLE_BASIC, 'hra': SalaryComponent.ROLE_HRA,
    'special_allowance': SalaryComponent.ROLE_SPECIAL_ALLOWANCE,
    'special allowance': SalaryComponent.ROLE_SPECIAL_ALLOWANCE, 'other': SalaryComponent.ROLE_OTHER,
}
_TRUE = {'yes', 'y', 'true', '1'}
_FALSE = {'no', 'n', 'false', '0'}

CREATE, UPDATE, NO_CHANGE, ERROR = 'create', 'update', 'no_change', 'error'


# ── File reading (same limits/parsers as the employee import) ────────────────

def read_rows(uploaded, columns: dict, required: dict, *, keep_other: bool = False
              ) -> tuple[list[dict] | None, str | None]:
    """Rows as {key: value} using `columns` aliases; `required` maps key -> header
    shown in the error when that column is missing. keep_other=True also returns
    every other non-blank header under row['_other'] as {header: value}."""
    from apps.accounts.views import _parse_employee_csv_rows, _parse_employee_xlsx_rows
    if uploaded.size > MAX_IMPORT_BYTES:
        return None, 'File too large. Maximum allowed size is 5 MB.'
    name = (uploaded.name or '').lower()
    if name.endswith('.xlsx'):
        rows, problem = _parse_employee_xlsx_rows(uploaded)
    elif name.endswith('.csv'):
        rows, problem = _parse_employee_csv_rows(uploaded)
    else:
        return None, 'Unsupported file format. Please upload a CSV or XLSX file.'
    if problem:
        return None, problem
    if not rows:
        return None, 'The file contains no data rows.'
    if len(rows) > MAX_IMPORT_ROWS:
        return None, f'File contains {len(rows)} rows. Maximum allowed per import is {MAX_IMPORT_ROWS}.'
    out = [{columns[k.strip().lower()]: str(v if v is not None else '').strip()
            for k, v in row.items() if k and k.strip().lower() in columns} for row in rows]
    if keep_other:
        for parsed, row in zip(out, rows):
            parsed['_other'] = {' '.join(k.split()): str(v if v is not None else '').strip()
                                for k, v in row.items() if k and k.strip() and k.strip().lower() not in columns}
    for key, header in required.items():
        if not any(key in r for r in out):
            return None, f'The file needs a "{header}" column.'
    return out, None


# ── Structures ───────────────────────────────────────────────────────────────

def _component_dict(row: dict, position: int) -> tuple[dict, list[str]]:
    errors = []
    name = ' '.join(row.get('component', '').split())
    ctype = _TYPE_ALIASES.get(row.get('type', '').lower())
    if ctype is None:
        errors.append('Type must be earning, allowance or deduction.')
    calc = _CALC_ALIASES.get(row.get('calculation', '').lower())
    if calc is None:
        errors.append('Calculation must be percentage_of_ctc, percentage_of_basic or fixed.')
    raw_role = row.get('role', '').lower()
    role = _ROLE_ALIASES.get(raw_role) if raw_role else role_for_name(name)
    if role is None:
        errors.append('Role must be basic, hra, special_allowance or other.')
    raw_taxable = row.get('taxable', '').lower()
    if raw_taxable and raw_taxable not in _TRUE | _FALSE:
        errors.append('Taxable must be yes or no.')
    order = row.get('order', '') or str(position)
    return {
        'name': name, 'component_type': ctype, 'calculation_type': calc, 'role': role,
        'value': row.get('value', ''), 'order': order, 'is_taxable': raw_taxable not in _FALSE,
    }, errors


def _component_signature(c) -> tuple:
    return (c.component_type, c.calculation_type, c.role, Decimal(c.value).normalize(), c.order, c.is_taxable)


def _employees_following(structure) -> int:
    """Employees whose current revision has no component copy of its own and
    resolves to this structure — the ones whose next payroll would use an
    updated structure. (Revisions with their own copy are unaffected.)"""
    count = 0
    for cfg in (EmployeeSalaryConfig.objects.filter(is_active=True, components__isnull=True)
                .select_related('employee', 'salary_structure').distinct()):
        if resolve_template_structure(cfg.employee, cfg.salary_structure) == structure:
            count += 1
    return count


def plan_structures(rows: list[dict], *, allow_update: bool) -> list[dict]:
    groups: dict[str, dict] = {}
    for idx, row in enumerate(rows, start=2):
        name = ' '.join(row.get('structure', '').split())
        key = name.lower()
        group = groups.setdefault(key, {'name': name, 'rows': [], 'description': ''})
        group['rows'].append((idx, row))
        if not group['description'] and row.get('description'):
            group['description'] = row['description'][:500]

    existing = {s.name.lower(): s for s in SalaryStructure.objects.annotate(u=Upper('name'))
                .filter(u__in=[k.upper() for k in groups if k])}
    plan = []
    for key, group in groups.items():
        out = {'name': group['name'], 'description': group['description'], 'rows': [r for r, _ in group['rows']],
               'components': [], 'status': ERROR, 'errors': [], 'changes': None, 'employees_following': None}
        plan.append(out)
        if not key:
            out['name'] = '(blank)'
            out['errors'].append(f'Rows {", ".join(map(str, out["rows"]))}: Structure Name is required.')
            continue
        if len(group['name']) > 100:
            out['errors'].append('Structure name must be at most 100 characters.')
        dicts = []
        for position, (idx, row) in enumerate(group['rows'], start=1):
            comp, problems = _component_dict(row, position)
            out['errors'].extend(f'Row {idx}: {p}' for p in problems)
            dicts.append(comp)
        if out['errors']:
            continue
        specs, problems = parse_components(dicts)
        out['errors'].extend(problems)
        enabled_basic = [s for s in specs if s.role == SalaryComponent.ROLE_BASIC and not s.is_deduction]
        if len(enabled_basic) != 1:
            out['errors'].append('Each structure needs exactly one Basic component.')
        pct_ctc = sum((s.value for s in specs if s.calculation_type == SalaryComponent.CALC_PCT_CTC
                       and not s.is_deduction), Decimal('0'))
        if pct_ctc > 100:
            out['errors'].append(f'% of CTC components add up to {pct_ctc}%, more than 100%.')
        out['components'] = [{'name': s.name, 'component_type': s.component_type,
                              'calculation_type': s.calculation_type, 'role': s.role, 'value': str(s.value),
                              'order': s.order, 'is_taxable': s.is_taxable} for s in specs]
        if out['errors']:
            continue

        current = existing.get(key)
        if current is None:
            out['status'] = CREATE
            out['_specs'] = specs
            continue
        if not current.is_active:
            out['errors'].append('A deactivated structure already has this name — use a different name.')
            continue
        if not allow_update:
            out['errors'].append('A structure with this name already exists. Choose "Update existing '
                                 'structures" to update it, or use a different name.')
            continue
        now = {c.name.lower(): c for c in current.components.filter(is_active=True)}
        new = {s.name.lower(): s for s in specs}
        out['changes'] = {
            'added': sorted(s.name for k, s in new.items() if k not in now),
            'removed': sorted(c.name for k, c in now.items() if k not in new),
            'changed': sorted(s.name for k, s in new.items()
                              if k in now and _component_signature(now[k]) != _component_signature(s)),
        }
        description_changed = bool(group['description']) and group['description'] != current.description
        if not any(out['changes'].values()) and not description_changed:
            out['status'] = NO_CHANGE
            continue
        out['status'] = UPDATE
        out['_specs'] = specs
        out['_structure'] = current
        out['employees_following'] = _employees_following(current)
    return plan


def public_plan(plan: list[dict]) -> list[dict]:
    return [{k: v for k, v in p.items() if not k.startswith('_')} for p in plan]


def summarise(plan: list[dict]) -> dict:
    return {s: sum(1 for p in plan if p['status'] == s) for s in (CREATE, UPDATE, NO_CHANGE, ERROR)} | {
        'total': len(plan)}


def _component_fields(spec) -> dict:
    return {'component_type': spec.component_type, 'calculation_type': spec.calculation_type, 'role': spec.role,
            'value': spec.value, 'order': spec.order, 'is_taxable': spec.is_taxable}


@transaction.atomic
def apply_structures(plan: list[dict]) -> list[dict]:
    """Writes every create/update entry of a validated plan. Returns audit
    entries ({action, object_id, changes}) for the caller to record."""
    audits = []
    for p in plan:
        if p['status'] == CREATE:
            structure = SalaryStructure.objects.create(name=p['name'], description=p['description'])
            SalaryComponent.objects.bulk_create([
                SalaryComponent(structure=structure, name=s.name, **_component_fields(s)) for s in p['_specs']
            ])
            audits.append({'action': 'salary_structure_imported', 'object_id': structure.pk,
                           'changes': {'name': structure.name, 'components': [s.name for s in p['_specs']]}})
            p['status'], p['id'] = 'created', str(structure.pk)
        elif p['status'] == UPDATE:
            structure = SalaryStructure.objects.select_for_update().get(pk=p['_structure'].pk)
            if p['description']:
                structure.description = p['description']
                structure.save(update_fields=['description', 'updated_at'])
            now = {c.name.lower(): c for c in structure.components.filter(is_active=True)}
            listed = set()
            for spec in p['_specs']:
                listed.add(spec.name.lower())
                comp = now.get(spec.name.lower())
                if comp is None:
                    SalaryComponent.objects.create(structure=structure, name=spec.name, **_component_fields(spec))
                else:
                    for field, value in _component_fields(spec).items():
                        setattr(comp, field, value)
                    comp.save()
            for key, comp in now.items():
                if key not in listed:
                    comp.is_active = False
                    comp.save(update_fields=['is_active', 'updated_at'])
            audits.append({'action': 'salary_structure_import_updated', 'object_id': structure.pk,
                           'changes': {'name': structure.name, **p['changes']}})
            p['status'], p['id'] = 'updated', str(structure.pk)
    return audits


# ── Assignments ──────────────────────────────────────────────────────────────

_DATE_FORMATS = ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%d-%b-%Y', '%d %b %Y')


def parse_date(value: str) -> date | None:
    value = (value or '').strip()
    if ' ' in value and ':' in value:            # Excel datetime cell, e.g. "2026-12-01 00:00:00"
        value = value.split(' ')[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def plan_assignments(rows: list[dict], *, in_scope) -> list[dict]:
    """in_scope(employee) -> bool: the requester's usual salary-assignment scope."""
    codes = [(r.get('employee_id') or '').upper() for r in rows]
    counts = {c: codes.count(c) for c in codes if c}
    employees = {u.employee_id.upper(): u for u in User.objects.annotate(u=Upper('employee_id'))
                 .filter(u__in=[c for c in codes if c])}
    names = {(r.get('structure') or '').strip().upper() for r in rows}
    structures = {s.name.upper(): s for s in SalaryStructure.objects.annotate(u=Upper('name'))
                  .filter(u__in=names, is_active=True)}
    current = {c.employee_id: c for c in EmployeeSalaryConfig.objects
               .filter(is_active=True, employee__in=list(employees.values()))}

    plan = []
    for idx, row in enumerate(rows, start=2):
        code = (row.get('employee_id') or '').strip()
        out = {'row': idx, 'employee_id': code, 'name': '', 'structure': row.get('structure', ''),
               'current_structure': None, 'effective_from': row.get('effective_from', ''),
               'status': ERROR, 'message': ''}
        plan.append(out)
        if not code:
            out['message'] = 'Employee ID is required.'
            continue
        if counts.get(code.upper(), 0) > 1:
            out['message'] = 'This Employee ID appears more than once in the file.'
            continue
        emp = employees.get(code.upper())
        if emp is None or not in_scope(emp):
            out['message'] = 'Employee not found.'
            continue
        out.update(employee_id=emp.employee_id, name=emp.full_name)
        if not emp.is_active:
            out['message'] = 'Employee is inactive.'
            continue
        structure = structures.get((row.get('structure') or '').strip().upper())
        if structure is None:
            out['message'] = 'Salary structure not found (or inactive).'
            continue
        out['structure'] = structure.name
        effective = parse_date(row.get('effective_from', ''))
        if effective is None:
            out['message'] = 'Effective From must be a date (YYYY-MM-DD).'
            continue
        out['effective_from'] = effective.isoformat()
        cfg = current.get(emp.id)
        if cfg is None:
            out['message'] = 'No current salary (CTC) — assign a CTC first.'
            continue
        current_template = cfg.template_structure or cfg.salary_structure
        out['current_structure'] = current_template.name if current_template else None
        if cfg.salary_structure_id == structure.pk and cfg.effective_from == effective:
            out.update(status=NO_CHANGE, message='Already on this structure from this date.')
            continue
        problem = revision_problem(emp, effective)
        if problem:
            out['message'] = problem
            continue
        out.update(status=UPDATE, message='New salary revision will be saved.',
                   _employee=emp, _structure=structure, _config=cfg, _effective=effective)
    return plan


def apply_assignments(plan: list[dict], *, user, ip_address) -> int:
    saved = 0
    for p in plan:
        if p['status'] != UPDATE:
            continue
        structure = p['_structure']
        specs = specs_from_structure(structure.components.filter(is_active=True).order_by('order'))
        try:
            save_revision(
                employee=p['_employee'], annual_ctc=p['_config'].annual_ctc, effective_from=p['_effective'],
                salary_structure=structure, template_structure=structure, specs=specs,
                user=user, ip_address=ip_address, source='structure_assignment_import',
            )
        except RevisionNotAllowed as exc:          # changed after validation
            p['status'], p['message'] = ERROR, str(exc)
            continue
        p['status'], p['message'] = 'updated', 'Salary revision saved.'
        saved += 1
    return saved


def summarise_assignments(plan: list[dict]) -> dict:
    return {s: sum(1 for p in plan if p['status'] == s) for s in (UPDATE, NO_CHANGE, ERROR)} | {
        'total': len(plan)}
