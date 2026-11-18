"""Employees: same people, same rule as the Employee directory (see scope.employee_scope)."""
from django.db.models import Q

from apps.accounts.models import EmployeeProfile, User
from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register
from apps.global_search.scope import employee_scope

from ._helpers import choices_of

_SENSITIVE = 'employees.view_sensitive'


def _branch_filter(operator: str, value) -> Q:
    """A Company Code by its CURRENT name, or the text copy older employees carry (same reasoning as the directory's filter)."""
    suffix = {'eq': '__iexact', 'contains': '__icontains', 'starts_with': '__istartswith', 'ends_with': '__iendswith', 'in': '__in'}[operator]
    return Q(**{f'branch_fk__branch_name{suffix}': value}) | Q(**{f'branch{suffix}': value})


def _queryset(user):
    return (
        User.objects.filter(employee_scope(user)).exclude(employee_id='')
        .select_related('profile', 'branch_fk', 'reporting_manager')
    )


def _describe(user: User) -> dict:
    return {
        'id': str(user.pk),
        'title': user.full_name,
        'subtitle': ' · '.join(part for part in (user.employee_id, user.designation) if part),
        'meta': {
            'Department': user.department, 'Company code': user.branch_fk.branch_name if user.branch_fk_id else user.branch,
            'Email': user.email, 'Status': 'Active' if user.is_active else 'Inactive',
        },
        'url': f'/dashboard/employees?open={user.pk}',
    }


FIELDS = (
    FieldSpec('full_name', 'Name', f.TEXT, 'full_name', searchable=True),
    FieldSpec('employee_id', 'Employee ID', f.TEXT, 'employee_id', searchable=True),
    FieldSpec('email', 'Email', f.TEXT, 'email', searchable=True),
    FieldSpec('phone', 'Mobile number', f.TEXT, 'phone', searchable=True),
    FieldSpec('designation', 'Designation', f.TEXT, 'designation', searchable=True),
    FieldSpec('department', 'Department', f.TEXT, 'department', searchable=True),
    FieldSpec('branch', 'Company code', f.TEXT, 'branch', build=_branch_filter, searchable=False,
              operators=('eq', 'contains', 'starts_with', 'ends_with', 'in')),
    FieldSpec('gender', 'Gender', f.CHOICE, 'profile__gender', choices=choices_of(EmployeeProfile, 'gender')),
    FieldSpec('employment_status', 'Employment status', f.CHOICE, 'employment_status', choices=choices_of(User, 'employment_status')),
    FieldSpec('employee_type', 'Employee type', f.CHOICE, 'employee_type', choices=choices_of(User, 'employee_type')),
    FieldSpec('work_mode', 'Work mode', f.CHOICE, 'work_mode', choices=choices_of(User, 'work_mode')),
    FieldSpec('work_location', 'Work location', f.TEXT, 'work_location'),
    FieldSpec('is_active', 'Active account', f.BOOLEAN, 'is_active'),
    FieldSpec('date_of_joining', 'Date of joining', f.DATE, 'date_of_joining'),
    FieldSpec('reporting_manager', 'Reporting manager', f.TEXT, 'reporting_manager__full_name'),
    # Personal details: only for people who may see sensitive employee data.
    FieldSpec('date_of_birth', 'Date of birth', f.DATE, 'profile__date_of_birth', permission=_SENSITIVE),
    FieldSpec('marital_status', 'Marital status', f.CHOICE, 'profile__marital_status', choices=choices_of(EmployeeProfile, 'marital_status'), permission=_SENSITIVE),
    FieldSpec('blood_group', 'Blood group', f.CHOICE, 'profile__blood_group', choices=choices_of(EmployeeProfile, 'blood_group'), permission=_SENSITIVE),
    FieldSpec('personal_email', 'Personal email', f.TEXT, 'profile__personal_email', permission=_SENSITIVE),
    FieldSpec('current_state', 'State', f.TEXT, 'profile__current_state', permission=_SENSITIVE),
    FieldSpec('current_district', 'District', f.TEXT, 'profile__current_district', permission=_SENSITIVE),
)

EMPLOYEES = register(SearchModule(
    key='employees', label='Employees', icon='ti-id-badge', permission='employees.view', queryset=_queryset, fields=FIELDS,
    describe=_describe, order_by=('full_name', 'pk'), default_url='/dashboard/employees',
))
