"""
Employee-wise salary components — shared by Assign CTC (preview + save) and
payroll processing, so both always calculate the same way.

Concepts
  * SalaryStructure / SalaryComponent — shared template.
  * EmployeeSalaryConfig — one effective-dated salary revision (CTC).
  * EmployeeSalaryComponent — that revision's own copy of its components.
    Revisions without rows (older records, onboarding / bulk-import
    configs) keep using the live structure, exactly as before.

Calculation (monthly, Decimal throughout, no rounding until the payslip is saved):
  * % of CTC   → monthly CTC × value / 100
  * % of Basic → Basic × value / 100 (Basic is calculated first, whatever the display order)
  * Fixed      → value (monthly rupees)
  * Role Basic / HRA / Special Allowance fill those payslip lines; other
    earnings/allowances go to other_earnings; components of type
    "deduction" go to other_deductions and are subtracted, never added to gross.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.payroll.models import EmployeeSalaryComponent, EmployeeSalaryConfig, SalaryComponent, SalaryStructure

ZERO = Decimal('0')
MAX_COMPONENTS = 50
_NAMED_ROLES = (SalaryComponent.ROLE_BASIC, SalaryComponent.ROLE_HRA, SalaryComponent.ROLE_SPECIAL_ALLOWANCE)
_ROLE_BY_NAME = {'basic': SalaryComponent.ROLE_BASIC, 'hra': SalaryComponent.ROLE_HRA,
                 'special allowance': SalaryComponent.ROLE_SPECIAL_ALLOWANCE}
_TYPES = {c for c, _ in SalaryComponent.COMPONENT_TYPE_CHOICES}
_CALCS = {c for c, _ in SalaryComponent.CALCULATION_TYPE_CHOICES}
_ROLES = {c for c, _ in SalaryComponent.ROLE_CHOICES}


def role_for_name(name: str) -> str:
    """The role payroll has always given a component by its name (exact, case-insensitive)."""
    return _ROLE_BY_NAME.get((name or '').lower(), SalaryComponent.ROLE_OTHER)


@dataclass
class ComponentSpec:
    name: str
    component_type: str
    calculation_type: str
    role: str
    value: Decimal
    order: int = 0
    is_taxable: bool = True
    is_enabled: bool = True
    source_component_id: object = None
    amount: Decimal = ZERO          # filled by calculate()

    @property
    def is_deduction(self) -> bool:
        return self.component_type == SalaryComponent.TYPE_DEDUCTION


def specs_from_structure(components) -> list[ComponentSpec]:
    return [ComponentSpec(
        name=c.name, component_type=c.component_type, calculation_type=c.calculation_type, role=c.role,
        value=c.value, order=c.order, is_taxable=c.is_taxable, is_enabled=c.is_active, source_component_id=c.id,
    ) for c in components]


def specs_from_config(config: EmployeeSalaryConfig) -> list[ComponentSpec]:
    return [ComponentSpec(
        name=c.name, component_type=c.component_type, calculation_type=c.calculation_type, role=c.role,
        value=c.value, order=c.order, is_taxable=c.is_taxable, is_enabled=c.is_enabled,
        source_component_id=c.source_component_id,
    ) for c in config.components.all()]


@dataclass
class Breakdown:
    basic: Decimal = ZERO
    hra: Decimal = ZERO
    special_allowance: Decimal = ZERO
    other_earnings: dict = field(default_factory=dict)
    other_deductions: dict = field(default_factory=dict)

    @property
    def other_earnings_total(self) -> Decimal:
        return sum(self.other_earnings.values(), ZERO)

    @property
    def other_deductions_total(self) -> Decimal:
        return sum(self.other_deductions.values(), ZERO)

    @property
    def gross(self) -> Decimal:
        return self.basic + self.hra + self.special_allowance + self.other_earnings_total


def _amount(spec: ComponentSpec, monthly_ctc: Decimal, basic: Decimal) -> Decimal:
    if spec.calculation_type == SalaryComponent.CALC_PCT_CTC:
        return monthly_ctc * spec.value / 100
    if spec.calculation_type == SalaryComponent.CALC_PCT_BASIC:
        return basic * spec.value / 100
    return spec.value


def calculate(specs: list[ComponentSpec], monthly_ctc: Decimal) -> Breakdown:
    """Monthly amounts for the enabled components; sets spec.amount on every spec (0 when disabled)."""
    ordered = sorted(specs, key=lambda s: s.order)
    for spec in ordered:
        spec.amount = ZERO
    enabled = [s for s in ordered if s.is_enabled]
    out = Breakdown()

    # Basic first, so % of Basic works whatever the display order. A Basic
    # that is itself "% of Basic" has nothing to be a percentage of → 0.
    for spec in enabled:
        if spec.role == SalaryComponent.ROLE_BASIC and not spec.is_deduction:
            spec.amount = _amount(spec, monthly_ctc, ZERO)
            out.basic = spec.amount          # one Basic expected; the last one wins, as before
    for spec in enabled:
        if spec.role == SalaryComponent.ROLE_BASIC and not spec.is_deduction:
            continue
        spec.amount = _amount(spec, monthly_ctc, out.basic)
        if spec.is_deduction:
            out.other_deductions[spec.name] = out.other_deductions.get(spec.name, ZERO) + spec.amount
        elif spec.role == SalaryComponent.ROLE_HRA:
            out.hra = spec.amount
        elif spec.role == SalaryComponent.ROLE_SPECIAL_ALLOWANCE:
            out.special_allowance = spec.amount
        else:
            out.other_earnings[spec.name] = spec.amount
    return out


# ─── Which structure / which revision ────────────────────────────────────────

_UNSET = object()


def resolve_template_structure(employee, salary_structure=None, *, branch_config=_UNSET, default_structure=_UNSET):
    """Same precedence payroll uses: employee pick → branch structure → company default.

    Payroll passes branch_config / default_structure it already fetched (None = none exists)."""
    if salary_structure is not None:
        return salary_structure
    if branch_config is _UNSET:
        from apps.branch.models import Branch
        branch = Branch.objects.filter(branch_name=employee.branch).select_related(
            'payroll_config__salary_structure').first() if employee.branch else None
        branch_config = getattr(branch, 'payroll_config', None) if branch else None
    if branch_config is not None and branch_config.salary_structure:
        return branch_config.salary_structure
    if default_structure is not _UNSET:
        return default_structure
    return SalaryStructure.objects.filter(is_default=True, is_active=True).first()


def _applicable(revisions: list[EmployeeSalaryConfig], on_or_before) -> EmployeeSalaryConfig | None:
    """
    The revision in force for a period ending `on_or_before`.

    A revision is replaced (never used again) when a later-saved revision
    starts on or before it — that is how a correction is entered. Otherwise
    it stays in force until the next revision's effective date, so saving a
    future-dated revision no longer leaves the months before it without a
    salary. Same effective date: the latest saved wins.
    """
    if not any(r.is_active for r in revisions):
        return None                      # deliberately switched off — skipped, as before
    in_force = []
    for r in revisions:
        replaced = any(o.created_at > r.created_at and o.effective_from <= r.effective_from for o in revisions)
        if not replaced and r.effective_from <= on_or_before:
            in_force.append(r)
    if not in_force:
        return None
    return max(in_force, key=lambda r: (r.effective_from, r.created_at))


def applicable_configs(employee_ids, on_or_before) -> dict:
    """{employee_id: revision in force for a cycle ending on `on_or_before`} (components prefetched)."""
    by_employee: dict = {}
    for cfg in (
        EmployeeSalaryConfig.objects
        .filter(employee_id__in=employee_ids)
        .select_related('salary_structure', 'template_structure')
        .prefetch_related('components')
        .order_by('created_at')
    ):
        by_employee.setdefault(cfg.employee_id, []).append(cfg)
    out = {}
    for employee_id, revisions in by_employee.items():
        chosen = _applicable(revisions, on_or_before)
        if chosen is not None:
            out[employee_id] = chosen
    return out


def specs_for_revision(config: EmployeeSalaryConfig, employee, *, branch_config=_UNSET, default_structure=_UNSET,
                       structure_specs=None):
    """(specs, structure used) — the revision's own components, else the live structure (older revisions)."""
    if config.components.all():
        return specs_from_config(config), config.salary_structure or config.template_structure
    structure = resolve_template_structure(employee, config.salary_structure, branch_config=branch_config,
                                           default_structure=default_structure)
    if structure is None:
        return None, None
    if structure_specs is not None:
        return structure_specs(structure), structure
    return specs_from_structure(structure.components.filter(is_active=True).order_by('order')), structure


# ─── Validation (HR-entered components) ──────────────────────────────────────

def parse_components(raw) -> tuple[list[ComponentSpec], list[str]]:
    """Validate the components submitted from Assign CTC. Returns (specs, errors)."""
    if not isinstance(raw, list):
        return [], ['Components must be a list.']
    if len(raw) > MAX_COMPONENTS:
        return [], [f'At most {MAX_COMPONENTS} components are allowed.']
    errors, specs, seen = [], [], set()
    source_ids = {str(r.get('source_component')) for r in raw if isinstance(r, dict) and r.get('source_component')}
    known_sources = {str(pk) for pk in SalaryComponent.objects.filter(pk__in=_valid_uuids(source_ids))
                     .values_list('pk', flat=True)}
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(f'Component {i}: invalid entry.')
            continue
        name = str(item.get('name') or '').strip()
        label = f'"{name}"' if name else f'Component {i}'
        if not name:
            errors.append(f'Component {i}: name is required.')
        elif len(name) > 100:
            errors.append(f'{label}: name must be at most 100 characters.')
        elif name.lower() in seen:
            errors.append(f'{label}: appears more than once.')
        seen.add(name.lower())
        ctype = item.get('component_type')
        calc = item.get('calculation_type')
        role = item.get('role') or role_for_name(name)
        if ctype not in _TYPES:
            errors.append(f'{label}: unsupported component type.')
        if calc not in _CALCS:
            errors.append(f'{label}: unsupported calculation method.')
        if role not in _ROLES:
            errors.append(f'{label}: unsupported role.')
        try:
            value = Decimal(str(item.get('value', '')).replace(',', '').strip())
            if not value.is_finite():
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            errors.append(f'{label}: value must be a number.')
            value = None
        if value is not None:
            if value < 0:
                errors.append(f'{label}: value cannot be negative.')
            elif calc == SalaryComponent.CALC_PCT_CTC and value > 100:
                errors.append(f'{label}: % of CTC cannot exceed 100.')
            elif value >= Decimal('1000000'):
                errors.append(f'{label}: value is too large.')
            elif value != value.quantize(Decimal('0.0001')):
                errors.append(f'{label}: use at most 4 decimal places.')
        source = item.get('source_component') or None
        if source and str(source) not in known_sources:
            errors.append(f'{label}: the template component no longer exists.')
            source = None
        try:
            order = int(item.get('order', i))
            if not 0 <= order <= 32767:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f'{label}: order must be a whole number.')
            order = i
        specs.append(ComponentSpec(
            name=name, component_type=ctype, calculation_type=calc, role=role, value=value or ZERO,
            order=order, is_taxable=bool(item.get('is_taxable', True)), is_enabled=bool(item.get('is_enabled', True)),
            source_component_id=source,
        ))
    if errors:
        return specs, errors

    enabled = [s for s in specs if s.is_enabled]
    for role in _NAMED_ROLES:
        holders = [s for s in enabled if s.role == role]
        label = dict(SalaryComponent.ROLE_CHOICES)[role]
        if len(holders) > 1:
            errors.append(f'Only one enabled component can be {label}.')
        if any(s.is_deduction for s in holders):
            errors.append(f'{label} must be an earning or allowance, not a deduction.')
    basic = [s for s in enabled if s.role == SalaryComponent.ROLE_BASIC]
    if any(s.calculation_type == SalaryComponent.CALC_PCT_BASIC for s in basic):
        errors.append('Basic cannot be a percentage of Basic.')
    if not basic and any(s.calculation_type == SalaryComponent.CALC_PCT_BASIC for s in enabled):
        errors.append('A component is a % of Basic, but there is no enabled Basic component.')
    if not any(not s.is_deduction for s in enabled):
        errors.append('Add at least one enabled earning or allowance component.')
    return specs, errors


def _valid_uuids(values):
    import uuid
    out = []
    for v in values:
        try:
            out.append(uuid.UUID(v))
        except (ValueError, TypeError):
            continue
    return out


def summary(specs: list[ComponentSpec], annual_ctc: Decimal) -> dict:
    """Calculated amounts + reconciliation against CTC (for preview and history)."""
    monthly_ctc = annual_ctc / 12
    b = calculate(specs, monthly_ctc)
    q = lambda d: d.quantize(Decimal('0.01'))
    warnings = []
    if not any(s.is_enabled and s.role == SalaryComponent.ROLE_BASIC and not s.is_deduction for s in specs):
        warnings.append('No Basic component: Basic, PF on Basic and every % of Basic component will be 0.')
    difference = q(annual_ctc - b.gross * 12)
    if difference != 0:
        warnings.append(
            f'Annual earnings ({q(b.gross * 12)}) do not equal the annual CTC ({q(annual_ctc)}); '
            f'difference {difference}. Nothing is balanced automatically.'
        )
    return {
        'components': [{
            'source_component': str(s.source_component_id) if s.source_component_id else None,
            'name': s.name, 'component_type': s.component_type, 'calculation_type': s.calculation_type,
            'role': s.role, 'value': str(s.value), 'order': s.order, 'is_taxable': s.is_taxable,
            'is_enabled': s.is_enabled, 'monthly_amount': str(q(s.amount)), 'annual_amount': str(q(s.amount * 12)),
        } for s in sorted(specs, key=lambda s: s.order)],
        'totals': {
            'annual_ctc': str(q(annual_ctc)), 'monthly_ctc': str(q(monthly_ctc)),
            'monthly_earnings': str(q(b.gross)), 'annual_earnings': str(q(b.gross * 12)),
            'monthly_deductions': str(q(b.other_deductions_total)),
            'annual_deductions': str(q(b.other_deductions_total * 12)),
            'annual_difference': str(difference),
        },
        'warnings': warnings,
    }


# ─── Saving a revision ───────────────────────────────────────────────────────

class RevisionNotAllowed(Exception):
    """The effective date would back-date a revision or reach into payroll already finalised."""


# Cycles whose payslips can no longer be re-processed (see process_payroll_cycle).
_LOCKED_CYCLE_STATUSES = ('query_window_open', 'paid', 'closed')


def revision_problem(employee, effective_from) -> str | None:
    """
    Why a new revision from `effective_from` isn't allowed, or None.

    Until back-dated revisions and arrears are defined with the client:
      * a revision may not start before the employee's latest revision
        (the same date is allowed — it replaces that revision);
      * it may not start inside a period the employee has already been paid
        for (finalised payslips are never recalculated).
    """
    latest = (EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True)
              .order_by('-effective_from').values_list('effective_from', flat=True).first())
    if latest and effective_from < latest:
        return (f'The effective date can\'t be before the current revision ({latest.isoformat()}). '
                'Back-dated revisions and arrears are not supported yet.')
    from apps.payroll.models import EmployeePayslip
    paid_until = (EmployeePayslip.objects
                  .filter(employee=employee, cycle__status__in=_LOCKED_CYCLE_STATUSES,
                          cycle__cycle_end__gte=effective_from)
                  .order_by('-cycle__cycle_end').values_list('cycle__cycle_end', flat=True).first())
    if paid_until:
        return (f'Payroll up to {paid_until.isoformat()} is already finalised for this employee. '
                'Choose an effective date after it; arrears are not supported yet.')
    return None


def _snapshot_rows(config, specs):
    calculate(specs, Decimal(config.annual_ctc) / 12)
    return [EmployeeSalaryComponent(
        salary_config=config, source_component_id=s.source_component_id, name=s.name,
        component_type=s.component_type, calculation_type=s.calculation_type, role=s.role, value=s.value,
        monthly_amount=s.amount.quantize(Decimal('0.01')), is_taxable=s.is_taxable, is_enabled=s.is_enabled,
        order=s.order,
    ) for s in specs]


def _terms(specs) -> dict:
    return {s.name: f'{s.calculation_type}:{format(s.value.normalize(), "f")}:{s.component_type}:{s.role}'
            + ('' if s.is_enabled else ':off') for s in specs}


def _audit_revision(config, previous, specs, *, user, ip_address, source):
    """Audit entry for a saved revision: CTC, date and which components were added / removed / changed."""
    from apps.accounts.models import AuditLog
    now = _terms(specs)
    before = _terms(specs_from_config(previous)) if previous is not None and previous.components.all() else {}
    changes = {
        'source': source,
        'employee_code': config.employee.employee_id or str(config.employee_id),
        'annual_ctc': str(config.annual_ctc),
        'effective_from': config.effective_from.isoformat(),
        'template_structure': config.template_structure.name if config.template_structure else None,
        'components': now,
    }
    if previous is not None:
        changes['previous_revision'] = str(previous.pk)
        changes['previous_annual_ctc'] = str(previous.annual_ctc)
        if before:
            changes['components_added'] = sorted(set(now) - set(before))
            changes['components_removed'] = sorted(set(before) - set(now))
            changes['components_changed'] = {n: [before[n], now[n]] for n in sorted(set(now) & set(before))
                                             if before[n] != now[n]}
    AuditLog.objects.create(
        user=user, action='salary_revision_created', module='payroll', object_id=str(config.pk),
        changes=changes, branch=config.employee.branch or '', ip_address=ip_address,
    )


@transaction.atomic
def save_revision(*, employee, annual_ctc, effective_from, salary_structure, template_structure,
                  specs: list[ComponentSpec], user=None, ip_address=None, source='assign_ctc') -> EmployeeSalaryConfig:
    """New revision + its component snapshot + audit entry, in one transaction. Earlier revisions stay as history."""
    # Lock the employee row so two saves for the same employee can't interleave.
    type(employee).objects.select_for_update().filter(pk=employee.pk).first()
    problem = revision_problem(employee, effective_from)
    if problem:
        raise RevisionNotAllowed(problem)
    previous = (EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True)
                .prefetch_related('components').order_by('-effective_from', '-created_at').first())
    EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True).update(is_active=False)
    config = EmployeeSalaryConfig.objects.create(
        employee=employee, annual_ctc=annual_ctc, effective_from=effective_from,
        salary_structure=salary_structure, template_structure=template_structure, is_active=True,
        created_by=user,
    )
    EmployeeSalaryComponent.objects.bulk_create(_snapshot_rows(config, specs))
    _audit_revision(config, previous, specs, user=user, ip_address=ip_address, source=source)
    return config


def assign_salary(*, employee, annual_ctc, effective_from, source, user=None, ip_address=None):
    """
    Salary given outside Assign CTC (onboarding approval, employee bulk import):
    the template's components are copied like any other revision. Idempotent —
    repeating the same CTC and date for the employee returns the existing
    revision (adding its component copy if it has none) instead of a duplicate.
    Returns (config, created). Raises RevisionNotAllowed.
    """
    template = resolve_template_structure(employee, None)
    specs = specs_from_structure(template.components.filter(is_active=True).order_by('order')) if template else []
    with transaction.atomic():
        type(employee).objects.select_for_update().filter(pk=employee.pk).first()
        existing = (EmployeeSalaryConfig.objects
                    .filter(employee=employee, is_active=True, effective_from=effective_from, annual_ctc=annual_ctc)
                    .first())
        if existing is not None:
            if specs:
                snapshot_existing(existing, specs, template)
            return existing, False
        return save_revision(employee=employee, annual_ctc=annual_ctc, effective_from=effective_from,
                             salary_structure=None, template_structure=template, specs=specs,
                             user=user, ip_address=ip_address, source=source), True


def snapshot_existing(config: EmployeeSalaryConfig, specs: list[ComponentSpec], template_structure) -> int:
    """Backfill: copy components onto an existing revision that has none. Returns rows created."""
    with transaction.atomic():
        # Re-checked under a row lock so a concurrent backfill can't copy twice.
        EmployeeSalaryConfig.objects.select_for_update().filter(pk=config.pk).first()
        if config.components.exists():
            return 0
        EmployeeSalaryComponent.objects.bulk_create(_snapshot_rows(config, specs))
        if config.template_structure_id is None and template_structure is not None:
            EmployeeSalaryConfig.objects.filter(pk=config.pk).update(template_structure=template_structure)
    return len(specs)

