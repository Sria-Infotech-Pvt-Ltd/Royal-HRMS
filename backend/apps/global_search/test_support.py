"""A small two-branch company for the global-search tests (imported by the test modules only)."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile, User
from apps.branch.models import Branch, City, State


def make_branch(code: str, name: str) -> Branch:
    state, _ = State.objects.get_or_create(name='Telangana', defaults={'code': 'TS'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.get_or_create(branch_code=code, defaults={'branch_name': name, 'state': state, 'city': city})[0]


def person(email: str, name: str, employee_id: str, *, branch: Branch, gender: str = '', department: str = '', designation: str = '',
           manager=None, perms=(), can_manage_team: bool = False, **extra) -> User:
    role = make_role(f'r_{employee_id}', permission_codenames=list(perms), can_manage_team=can_manage_team) if (perms or can_manage_team) else None
    user = make_user(
        email, role, full_name=name, employee_id=employee_id, branch=branch.branch_name, branch_fk=branch, department=department,
        designation=designation, reporting_manager=manager, onboarding_status=User.ONBOARDING_COMPLETE, **extra,
    )
    if gender:
        EmployeeProfile.objects.update_or_create(user=user, defaults={'gender': gender})
    return user


def build_world() -> SimpleNamespace:
    hyd, blr = make_branch('HY01', 'Hyderabad'), make_branch('BL01', 'Bengaluru')
    admin = person('admin@gs.test', 'Admin Root', 'EMP900', branch=hyd, perms=[
        'settings.edit', 'employees.view', 'employees.view_sensitive', 'attendance.view', 'branches.view', 'org_chart.view',
        'announcements.edit', 'leave.approve', 'wfh.approve', 'onboarding.edit',
    ])
    hr = person('hr@gs.test', 'Hema Hr', 'EMP901', branch=hyd, perms=['employees.view', 'attendance.view', 'leave.approve', 'wfh.approve', 'onboarding.edit', 'branches.view'])
    manager = person('manager@gs.test', 'Maya Manager', 'EMP902', branch=hyd, perms=['employees.view', 'attendance.view', 'leave.approve', 'wfh.approve'], can_manage_team=True)
    anita = person('anita@gs.test', 'Anita Rao', 'EMP001', branch=hyd, gender='female', department='Development', designation='Developer', manager=manager)
    bharat = person('bharat@gs.test', 'Bharat Kumar', 'EMP002', branch=hyd, gender='male', department='Development', designation='Developer', manager=manager)
    chitra = person('chitra@gs.test', 'Chitra Devi', 'EMP003', branch=hyd, gender='female', department='Sales', designation='Executive')
    deepak = person('deepak@gs.test', 'Deepak Shah', 'EMP004', branch=blr, gender='male', department='Development', designation='Developer')
    esha = person('esha@gs.test', 'Esha Verma', 'EMP005', branch=blr, gender='female', department='Sales', designation='Executive')
    return SimpleNamespace(hyd=hyd, blr=blr, admin=admin, hr=hr, manager=manager, anita=anita, bharat=bharat, chitra=chitra, deepak=deepak, esha=esha)


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def search(client: APIClient, module: str, *, q: str = '', filters=None, **params):
    """GET /search/<module>/ with the filter tree as the JSON the browser would send."""
    query = {'q': q, **params}
    if filters is not None:
        query['filters'] = json.dumps(filters)
    return client.get(reverse('global-search-module', kwargs={'module': module}), query)


def names(response, key: str = 'title') -> set[str]:
    assert response.status_code == 200, response.data
    return {row[key] for row in response.data['data']['results']}


def leaf(field: str, operator: str, value=None) -> dict:
    node = {'field': field, 'operator': operator}
    if value is not None:
        node['value'] = value
    return node


def all_of(*items) -> dict:
    return {'op': 'and', 'items': list(items)}


def any_of(*items) -> dict:
    return {'op': 'or', 'items': list(items)}


TODAY = date(2026, 11, 18)
