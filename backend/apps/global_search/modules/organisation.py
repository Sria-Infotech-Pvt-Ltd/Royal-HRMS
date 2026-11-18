"""Organisation: company codes (branches), org units (departments) and positions."""
from apps.accounts.models import OrgUnit, Position
from apps.branch.models import Branch
from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register
from core.permissions import has_perm

from ._helpers import choices_of, label_of


def _branches(user):
    """Mirrors the Company Codes page: settings.edit sees every code, anyone else only their own (and, unlike the page, nobody
    when they have no branch)."""
    rows = Branch.objects.select_related('state', 'city')
    if has_perm(user, 'settings.edit'):
        return rows
    branch = (getattr(user, 'branch', '') or '').strip()
    return rows.filter(branch_name__iexact=branch) if branch else rows.none()


def _describe_branch(branch: Branch) -> dict:
    place = ', '.join(part for part in (branch.city.name if branch.city_id else '', branch.state.name if branch.state_id else '') if part)
    return {
        'id': str(branch.pk), 'title': branch.branch_name, 'subtitle': ' · '.join(part for part in (branch.branch_code, place) if part),
        'meta': {'Status': label_of(branch, 'status'), 'Headquarter': 'Yes' if branch.is_headquarter else 'No'},
        'url': '/dashboard/branches',
    }


BRANCHES = register(SearchModule(
    key='branches', label='Company codes', icon='ti-building-skyscraper', permission='branches.view', queryset=_branches,
    fields=(
        FieldSpec('branch_name', 'Name', f.TEXT, 'branch_name', searchable=True),
        FieldSpec('branch_code', 'Code', f.TEXT, 'branch_code', searchable=True),
        FieldSpec('state', 'State', f.TEXT, 'state__name', searchable=True),
        FieldSpec('city', 'City', f.TEXT, 'city__name', searchable=True),
        FieldSpec('status', 'Status', f.CHOICE, 'status', choices=choices_of(Branch, 'status')),
        FieldSpec('is_headquarter', 'Headquarter', f.BOOLEAN, 'is_headquarter'),
        FieldSpec('is_metro', 'Metro city', f.BOOLEAN, 'is_metro'),
    ),
    describe=_describe_branch, order_by=('branch_name', 'pk'), default_url='/dashboard/branches',
))


def _org_units(user):
    return OrgUnit.objects.select_related('parent')


def _describe_unit(unit: OrgUnit) -> dict:
    return {
        'id': str(unit.pk), 'title': unit.name, 'subtitle': ' · '.join(part for part in (unit.code, unit.parent.name if unit.parent_id else '') if part),
        'meta': {'Status': 'Active' if unit.is_active else 'Inactive', 'Level': 'Department' if unit.is_department_level else 'Unit'},
        'url': '/dashboard/org-chart',
    }


ORG_UNITS = register(SearchModule(
    key='org_units', label='Departments and units', icon='ti-sitemap', permission='org_chart.view', queryset=_org_units,
    fields=(
        FieldSpec('name', 'Name', f.TEXT, 'name', searchable=True),
        FieldSpec('code', 'Code', f.TEXT, 'code', searchable=True),
        FieldSpec('parent', 'Parent unit', f.TEXT, 'parent__name', searchable=True),
        FieldSpec('is_active', 'Active', f.BOOLEAN, 'is_active'),
        FieldSpec('is_department_level', 'Department level', f.BOOLEAN, 'is_department_level'),
    ),
    describe=_describe_unit, order_by=('name', 'pk'), default_url='/dashboard/org-chart',
))


def _positions(user):
    return Position.objects.select_related('org_unit', 'branch')


def _describe_position(position: Position) -> dict:
    return {
        'id': str(position.pk), 'title': position.title,
        'subtitle': ' · '.join(part for part in (position.org_unit.name if position.org_unit_id else '', position.grade) if part),
        'meta': {'Company code': position.branch.branch_name if position.branch_id else '', 'Status': 'Active' if position.is_active else 'Inactive'},
        'url': '/dashboard/org-chart',
    }


POSITIONS = register(SearchModule(
    key='positions', label='Positions', icon='ti-briefcase', permission='org_chart.view', queryset=_positions,
    fields=(
        FieldSpec('title', 'Title', f.TEXT, 'title', searchable=True),
        FieldSpec('grade', 'Grade', f.TEXT, 'grade', searchable=True),
        FieldSpec('org_unit', 'Department / unit', f.TEXT, 'org_unit__name', searchable=True),
        FieldSpec('branch', 'Company code', f.TEXT, 'branch__branch_name'),
        FieldSpec('is_active', 'Active', f.BOOLEAN, 'is_active'),
        FieldSpec('is_chief', 'Head of unit', f.BOOLEAN, 'is_chief'),
        FieldSpec('can_manage_team', 'Manages a team', f.BOOLEAN, 'can_manage_team'),
        FieldSpec('can_manage_branch', 'Manages a branch', f.BOOLEAN, 'can_manage_branch'),
    ),
    describe=_describe_position, order_by=('title', 'pk'), default_url='/dashboard/org-chart',
))
