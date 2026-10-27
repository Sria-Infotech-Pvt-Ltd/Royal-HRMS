from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.payroll.models import (
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    PayrollSettings,
    SalaryComponent,
    SalaryComponentRevision,
    SalaryStructure,
)


def next_pay_cycle_start(today=None):
    today = today or date.today()
    settings = PayrollSettings.objects.first()
    start_day = settings.cycle_start_day if settings else 1

    year, month = today.year, today.month
    candidate = date(year, month, min(start_day, _days_in_month(year, month)))
    if candidate <= today:
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        candidate = date(year, month, min(start_day, _days_in_month(year, month)))
    return candidate


def _days_in_month(year, month):
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def component_configuration(component, as_of=None, include_future=False):
    revisions = list(component.revisions.order_by('-effective_from', '-created_at')[:1]) if include_future else list(
        component.revisions.filter(effective_from__lte=as_of or date.today())
        .order_by('-effective_from', '-created_at')[:1]
    )
    revision = revisions[0] if revisions else None
    return _configuration_from_revision(component, revision)


def _configuration_from_revision(component, revision):
    if revision is None:
        if component.revisions.exists():
            return None
        configuration = _component_fields(component)
        effective_from = component.created_at.date()
        reset_override = False
    else:
        configuration = revision.configuration
        effective_from = revision.effective_from
        reset_override = revision.reset_override

    return {
        'id': str(component.pk),
        **configuration,
        'effective_from': effective_from.isoformat(),
        'reset_override': reset_override,
        'created_at': component.created_at,
        'updated_at': component.updated_at,
    }


def structure_component_configurations(structure, as_of=None, include_future=False):
    components = list(structure.components.all())
    component_ids = [component.pk for component in components]
    revisions = SalaryComponentRevision.objects.filter(component_id__in=component_ids)
    if not include_future:
        revisions = revisions.filter(effective_from__lte=as_of or date.today())
    latest_by_component = {}
    for revision in revisions.order_by('component_id', '-effective_from', '-created_at'):
        latest_by_component.setdefault(revision.component_id, revision)
    revisions_exist = set(
        SalaryComponentRevision.objects.filter(component_id__in=component_ids)
        .values_list('component_id', flat=True)
    )
    configs = []
    for component in components:
        revision = latest_by_component.get(component.pk)
        if revision is None and component.pk in revisions_exist:
            continue
        config = _configuration_from_revision(component, revision)
        if config is not None:
            configs.append(config)
    return sorted(configs, key=lambda item: (item['order'], item['name'].casefold()))


def effective_components(structure, as_of):
    components = []
    for config in structure_component_configurations(structure, as_of):
        if not config['is_active']:
            continue
        components.append(SimpleNamespace(
            **{
                **config,
                'value': Decimal(str(config['value'])),
                'effective_from': date.fromisoformat(config['effective_from']),
                'reset_override': config['reset_override'],
            },
        ))
    return components


def component_fields(component):
    return _component_fields(component)


def _component_fields(component):
    return {
        'code': component.code,
        'name': component.name,
        'component_type': component.component_type,
        'calculation_type': component.calculation_type,
        'value': str(component.value),
        'is_taxable': component.is_taxable,
        'is_active': component.is_active,
        'order': component.order,
    }


def create_component_code(structure, name):
    base = slugify(name).replace('-', '_').upper().strip('_') or 'COMPONENT'
    base = base[:40]
    candidate = base
    suffix = 2
    while structure.components.filter(code=candidate).exists():
        ending = f'_{suffix}'
        candidate = f'{base[:40 - len(ending)]}{ending}'
        suffix += 1
    return candidate


def affected_employee_count(structure):
    User = get_user_model()
    explicitly_assigned = EmployeeSalaryConfig.objects.filter(
        employee__is_active=True,
        salary_structure=structure,
        is_active=True,
    )
    branch_names = list(
        BranchPayrollConfig.objects.filter(salary_structure=structure)
        .values_list('branch__branch_name', flat=True)
    )
    fallback = EmployeeSalaryConfig.objects.filter(
        is_active=True,
        salary_structure__isnull=True,
        employee__is_active=True,
        employee__branch__in=branch_names,
    )
    if structure.is_default:
        branches_with_override = BranchPayrollConfig.objects.exclude(
            salary_structure__isnull=True,
        ).values_list('branch__branch_name', flat=True)
        fallback = fallback | EmployeeSalaryConfig.objects.filter(
            is_active=True,
            salary_structure__isnull=True,
            employee__is_active=True,
        ).exclude(employee__branch__in=branches_with_override)
    assigned_ids = explicitly_assigned.values_list('employee_id', flat=True)
    fallback_ids = fallback.values_list('employee_id', flat=True)
    return User.objects.filter(pk__in=assigned_ids.union(fallback_ids)).distinct().count()
