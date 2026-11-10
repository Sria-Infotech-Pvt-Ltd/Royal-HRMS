"""
Salary setup import (Payroll → Salary Setup → Import salaries).

One row per employee:
  Employee Code, Employee Name (check only), Structure Name (optional),
  Effective From, one column per salary component (monthly amount),
  Annual CTC (optional check), PF Eligible / ESI Eligible / PT Applicable.

The salary structure is the authority for each component's type, role and
taxability; the file only gives the monthly amount. Structure Name blank →
the structure Assign CTC would use (branch → company default). Components
left blank (or 0) are saved switched off — only components with an amount
are paid or deducted. Each valid row saves a NEW salary revision through
save_revision (fixed monthly amounts, CTC = monthly earnings × 12), exactly
as Assign CTC does: earlier revisions stay as history and shared salary
structures are never changed.

A revision with the same Effective From as the employee's current one is
only replaced when the caller explicitly allows it; an identical one is
"no change". The preview saves nothing; the confirm request re-reads and
re-validates the file and saves nothing if any row has an error.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models.functions import Upper

from apps.accounts.models import User
from apps.payroll.models import EmployeeSalaryConfig, SalaryComponent, SalaryStructure
from apps.payroll.services_salary_components import (
    ELIGIBILITY_FIELDS, RevisionNotAllowed, _terms, parse_components, resolve_template_structure,
    revision_problem, save_revision, specs_from_config,
)
from apps.payroll.services_structure_import import _FALSE, _TRUE, parse_date

COLUMNS = {
    'employee code': 'employee_id', 'employee id': 'employee_id', 'employee_id': 'employee_id',
    'emp id': 'employee_id', 'emp code': 'employee_id',
    'employee name': 'employee_name', 'name': 'employee_name',
    'structure name': 'structure', 'structure': 'structure', 'salary structure': 'structure',
    'effective from': 'effective_from', 'effective date': 'effective_from', 'effective_from': 'effective_from',
    'annual ctc': 'annual_ctc', 'annual_ctc': 'annual_ctc', 'ctc': 'annual_ctc',
    'pf eligible': 'pf_eligible', 'esi eligible': 'esi_eligible', 'pt applicable': 'pt_applicable',
}
REQUIRED = {'employee_id': 'Employee Code', 'effective_from': 'Effective From'}

CREATE, UPDATE, NO_CHANGE, ERROR = 'create', 'update', 'no_change', 'error'
_MAX_AMOUNT = Decimal('1000000')            # component value is max_digits=10, decimal_places=4
_LABELS = {'pf_eligible': 'PF Eligible', 'esi_eligible': 'ESI Eligible', 'pt_applicable': 'PT Applicable'}


class ImportAborted(Exception):
    """A row became invalid between validation and saving; nothing was saved."""


def _amount(header: str, raw: str) -> tuple[Decimal | None, str | None]:
    try:
        value = Decimal(raw.replace(',', '').strip())
        if not value.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return None, f'{header}: "{raw}" is not a number.'
    if value < 0:
        return None, f'{header}: cannot be negative.'
    if value != value.quantize(Decimal('0.01')):
        return None, f'{header}: use at most 2 decimal places.'
    if value >= _MAX_AMOUNT:
        return None, f'{header}: too large for a monthly amount.'
    return value, None


def _money(d: Decimal) -> str:
    return str(d.quantize(Decimal('0.01')))


def plan(rows: list[dict], *, in_scope, replace_same_date: bool) -> list[dict]:
    """in_scope(employee) -> bool: the requester's Assign CTC scope."""
    codes = [(r.get('employee_id') or '').strip().upper() for r in rows]
    counts = {c: codes.count(c) for c in codes if c}
    matches: dict = {}
    for u in User.objects.annotate(u=Upper('employee_id')).filter(u__in=[c for c in codes if c]):
        matches.setdefault(u.employee_id.upper(), []).append(u)
    named = {(r.get('structure') or '').strip().upper() for r in rows} - {''}
    structures = {s.name.upper(): s for s in SalaryStructure.objects.annotate(u=Upper('name'))
                  .filter(u__in=named, is_active=True)}
    current = {}
    for cfg in (EmployeeSalaryConfig.objects.filter(is_active=True, employee__in=[u for us in matches.values()
                                                                                for u in us])
                .select_related('template_structure', 'salary_structure').prefetch_related('components')
                .order_by('created_at')):
        current[cfg.employee_id] = cfg
    components_cache: dict = {}

    def components_of(structure):
        if structure.pk not in components_cache:
            components_cache[structure.pk] = list(structure.components.filter(is_active=True).order_by('order'))
        return components_cache[structure.pk]

    out = []
    for idx, (row, code) in enumerate(zip(rows, codes), start=2):
        p = {'row': idx, 'employee_id': (row.get('employee_id') or '').strip(), 'name': '',
             'structure': (row.get('structure') or '').strip(), 'effective_from': row.get('effective_from', ''),
             'current_ctc': None, 'annual_ctc': None, 'monthly_earnings': None, 'components': [],
             'status': ERROR, 'message': ''}
        out.append(p)
        problems, notes = [], []

        # ── Employee ──
        employee = None
        found = matches.get(code, [])
        if not code:
            problems.append('Employee Code: required.')
        elif counts.get(code, 0) > 1:
            problems.append('Employee Code: appears more than once in the file — keep one row per employee.')
        elif len(found) > 1:
            problems.append(f'Employee Code: "{p["employee_id"]}" matches more than one employee — '
                            'fix the employee records first.')
        elif not found or not in_scope(found[0]):
            problems.append(f'Employee Code: "{p["employee_id"]}" doesn\'t match any employee you can manage.')
        elif not found[0].is_active:
            problems.append(f'Employee Code: "{p["employee_id"]}" is an inactive employee.')
        else:
            employee = found[0]
            p.update(employee_id=employee.employee_id, name=employee.full_name)
            given = ' '.join((row.get('employee_name') or '').split()).lower()
            if given and given != ' '.join(employee.full_name.split()).lower():
                notes.append(f'Employee Name in the file ("{row["employee_name"]}") differs from the employee '
                             f'record ({employee.full_name}) — check the code.')

        # ── Date ──
        effective = parse_date(row.get('effective_from', ''))
        if effective is None:
            problems.append('Effective From: required, as a date (YYYY-MM-DD).' if not row.get('effective_from')
                            else f'Effective From: "{row["effective_from"]}" is not a date (use YYYY-MM-DD).')
        else:
            p['effective_from'] = effective.isoformat()

        # ── Structure ──
        structure, explicit = None, bool(p['structure'])
        if explicit:
            structure = structures.get(p['structure'].upper())
            if structure is None:
                problems.append(f'Structure Name: "{p["structure"]}" not found (or inactive).')
        elif employee is not None:
            structure = resolve_template_structure(employee, None)
            if structure is None:
                problems.append('Structure Name: required — no branch or company default salary structure is set.')
        if structure is not None:
            p['structure'] = structure.name

        # ── Eligibility ──
        flags = {}
        for f in ELIGIBILITY_FIELDS:
            raw = (row.get(f) or '').strip().lower()
            if raw in _TRUE:
                flags[f] = True
            elif raw in _FALSE:
                flags[f] = False
            elif raw:
                problems.append(f'{_LABELS[f]}: must be yes, no or blank (blank keeps the current setting).')

        # ── Components ──
        specs = None
        if structure is None:
            # Still report badly formatted amounts, so one upload shows every problem.
            for header, raw in (row.get('_other') or {}).items():
                if raw:
                    problems.extend(filter(None, [_amount(header, raw)[1]]))
        else:
            by_name = {c.name.lower(): c for c in components_of(structure)}
            amounts = {}
            for header, raw in (row.get('_other') or {}).items():
                if not raw:
                    continue
                comp = by_name.get(header.lower())
                if comp is None:
                    problems.append(f'Column "{header}": not a component of salary structure "{structure.name}".')
                    continue
                value, problem = _amount(header, raw)
                if problem:
                    problems.append(problem)
                else:
                    amounts[comp.pk] = value
            basics = [c for c in by_name.values()
                      if c.role == SalaryComponent.ROLE_BASIC and c.component_type != SalaryComponent.TYPE_DEDUCTION]
            if not basics:
                problems.append(f'Salary structure "{structure.name}" has no Basic component.')
            elif not any(amounts.get(c.pk) for c in basics):
                problems.append(f'{basics[0].name}: required — enter the monthly amount.')
            if not problems:
                specs, errors = parse_components([{
                    'name': c.name, 'component_type': c.component_type, 'calculation_type': SalaryComponent.CALC_FIXED,
                    'role': c.role, 'value': str(amounts.get(c.pk, 0)), 'order': c.order, 'is_taxable': c.is_taxable,
                    'is_enabled': bool(amounts.get(c.pk)), 'source_component': str(c.pk),
                } for c in by_name.values()])
                problems.extend(errors)

        annual = None
        if specs is not None and not problems:
            monthly = sum((s.value for s in specs if s.is_enabled and not s.is_deduction), Decimal('0'))
            annual = monthly * 12
            p.update(annual_ctc=_money(annual), monthly_earnings=_money(monthly),
                     components=[{'name': s.name, 'amount': _money(s.value), 'deduction': s.is_deduction}
                                 for s in sorted(specs, key=lambda s: s.order) if s.is_enabled])
            raw_ctc = (row.get('annual_ctc') or '').strip()
            if raw_ctc:
                try:
                    given = Decimal(raw_ctc.replace(',', ''))
                    if not given.is_finite():
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    given = None
                    problems.append(f'Annual CTC: "{raw_ctc}" is not a number.')
                if given is not None and abs(given - annual) > 1:
                    problems.append(f'Annual CTC: {raw_ctc} doesn\'t match the components '
                                    f'(monthly earnings {_money(monthly)} × 12 = {_money(annual)}).')
            if annual <= 0:
                problems.append('The components add up to 0 — enter the monthly amounts.')

        # ── Against the current revision ──
        if employee is not None and effective is not None and not problems:
            cfg = current.get(employee.pk)
            if cfg is not None:
                p['current_ctc'] = _money(cfg.annual_ctc)
            if cfg is not None and cfg.effective_from == effective:
                same = (
                    _money(cfg.annual_ctc) == _money(annual)
                    and (cfg.template_structure_id or cfg.salary_structure_id) == structure.pk
                    and cfg.components.all() and _terms(specs_from_config(cfg)) == _terms(specs)
                    and all(getattr(cfg, f) == v for f, v in flags.items())
                )
                if same:
                    p.update(status=NO_CHANGE, message='Already saved with these amounts from this date.')
                    continue
                if not replace_same_date:
                    problems.append(f'A salary revision from {effective.isoformat()} already exists. Tick "Replace '
                                    'revisions with the same Effective From" to replace it, or use a later date.')
                else:
                    notes.insert(0, f'Replaces the revision from {effective.isoformat()} '
                                    '(it stays in the history).')
                    p['status'] = UPDATE
            if not problems:
                problem = revision_problem(employee, effective)
                if problem:
                    problems.append(problem)

        if problems:
            p.update(status=ERROR, message=' '.join(problems))
            continue
        if p['status'] != UPDATE:
            p['status'] = CREATE
            notes.insert(0, f'New salary revision from {effective.isoformat()}.')
        p['message'] = ' '.join(notes)
        p.update(_employee=employee, _structure=structure, _explicit=explicit, _specs=specs, _annual=annual,
                 _effective=effective, _flags=flags)
    return out


def summarise(plan_rows: list[dict]) -> dict:
    out = {s: sum(1 for p in plan_rows if p['status'] == s) for s in (CREATE, UPDATE, NO_CHANGE, ERROR)}
    for done in ('created', 'updated'):          # after saving
        count = sum(1 for p in plan_rows if p['status'] == done)
        if count:
            out[done] = count
    return out | {'total': len(plan_rows)}


def public(plan_rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in p.items() if not k.startswith('_')} for p in plan_rows]


@transaction.atomic
def apply(plan_rows: list[dict], *, user, ip_address) -> int:
    """Saves every create/update row (the caller has checked there are no errors).
    All or nothing: if any row can no longer be saved, nothing is."""
    saved = 0
    for p in plan_rows:
        if p['status'] not in (CREATE, UPDATE):
            continue
        try:
            save_revision(
                employee=p['_employee'], annual_ctc=p['_annual'], effective_from=p['_effective'],
                salary_structure=p['_structure'] if p['_explicit'] else None, template_structure=p['_structure'],
                specs=p['_specs'], user=user, ip_address=ip_address, source='salary_import', eligibility=p['_flags'],
            )
        except RevisionNotAllowed as exc:             # changed after validation
            p['status'], p['message'] = ERROR, str(exc)
            raise ImportAborted(f'Row {p["row"]}: {exc}') from exc
        p['status'] = 'created' if p['status'] == CREATE else 'updated'
        saved += 1
    return saved


def sample(today: date | None = None) -> tuple[list[str], list[list[str]]]:
    """Headers and two example rows, with the company default structure's components."""
    structure = SalaryStructure.objects.filter(is_default=True, is_active=True).first()
    components = list(structure.components.filter(is_active=True).order_by('order')) if structure else []
    names = [c.name for c in components] or ['Basic', 'HRA', 'Special Allowance']
    roles = [c.role for c in components] or ['basic', 'hra', 'special_allowance']
    example = {'basic': ('20000', '15000'), 'hra': ('8000', '6000'), 'special_allowance': ('4000', '3000')}
    month = ((today or date.today()).replace(day=1) + timedelta(days=32)).replace(day=1).isoformat()
    headers = ['Employee Code', 'Employee Name', 'Structure Name', 'Effective From', *names,
               'Annual CTC', 'PF Eligible', 'ESI Eligible', 'PT Applicable']
    rows = []
    for i in (0, 1):
        amounts = [example.get(r, ('1000', '500'))[i] for r in roles]
        rows.append([f'EMP00{i + 1}', f'Sample Employee {i + 1}', structure.name if structure else 'Staff Standard',
                     month, *amounts, '', '', '', ''])
    return headers, rows
