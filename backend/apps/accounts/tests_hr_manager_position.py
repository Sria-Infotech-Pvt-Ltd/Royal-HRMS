"""
Position-based permissions for an HR Manager seat.

Access follows the seat a person holds today. An administrator sets what the HR Manager POSITION may do
(PUT /org-structure/positions/<id>/permissions/) and assigns an employee to it (POST .../placements/); the employee then
gets those capabilities, only while the placement covers today. Nothing here is role based and nothing looks at a title.

Capabilities mapped to the EXISTING keys: view / create (hire) / edit employees, manage / approve onboarding, view
attendance, approve leave. "Manage leave policies" has no dedicated key: policy writes accept `leave.approve` today.
Payroll, system settings and permission administration are NOT part of the set.
"""
from __future__ import annotations

from datetime import timedelta

from django.apps import apps
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Permission, Placement, Position, PositionPermission, User
from apps.accounts.models_permission_template import PermissionTemplate
from core.permissions import effective_permission_codenames

HR_MANAGER_KEYS = [
    'employees.view', 'employees.create', 'employees.edit', 'onboarding.edit', 'onboarding.approve',
    'attendance.view', 'leave.approve',
]
NEVER_BY_DEFAULT = ['payroll.view', 'payroll.edit', 'settings.edit', 'settings.view', 'org_structure.edit', 'audit.view']
ZERO = '00000000-0000-0000-0000-000000000001'
BRANCH_A, BRANCH_B = 'HRM Branch A', 'HRM Branch B'


def capability_probes(target: User) -> list[tuple]:
    """(capability, method, url, payload): each endpoint answers 403 without the capability and anything else with it."""
    return [
        ('employees.view', 'get', '/api/employees/', None),
        ('employees.create', 'post', '/api/hire-actions/', {}),
        ('employees.edit', 'post', f'/api/employees/{target.employee_id}/bank-change/approve/', {}),
        ('onboarding.edit', 'get', f'/api/onboarding/employees/{target.pk}/', None),
        ('onboarding.approve', 'get', '/api/onboarding/approvals/', None),
        ('attendance.view', 'get', '/api/attendance/records/', None),
        ('leave.approve', 'post', f'/api/leave/requests/{ZERO}/approve/', {'action': 'approve'}),
        ('manage leave policies', 'put', '/api/leave/policy/casual/', {}),
    ]


DENIED_FOR_HR_MANAGER = [  # not part of the set: payroll, system settings, audit
    ('payroll', 'get', '/api/payroll/cycles/'), ('system settings', 'get', '/api/settings/smtp/'),
    ('audit log', 'get', '/api/settings/audit/'),
]


def _api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class HrManagerPositionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
        admin_profile = make_role('hrm_admin', permission_codenames=['settings.edit', 'settings.view', 'org_structure.edit', 'org_chart.view'])
        self.admin = make_user('hrm_admin@test.com', role=admin_profile, employee_id='HM001', branch=BRANCH_A)
        self.admin_seat = Placement.objects.get(employee=self.admin).position
        self.unit = OrgUnit.objects.create(name='HRM Test Unit')
        self.hr_position = Position.objects.create(org_unit=self.unit, title='HR Manager', grade='L4')
        self.plain_position = Position.objects.create(org_unit=self.unit, title='Support Analyst', grade='L2')
        self.hr_employee = make_user('hrm_employee@test.com', employee_id='HM010', branch=BRANCH_A)
        self.other_employee = make_user('hrm_other@test.com', employee_id='HM011', branch=BRANCH_A)
        self.target = make_user('hrm_target@test.com', employee_id='HM012', branch=BRANCH_A)
        self.far_employee = make_user('hrm_far@test.com', employee_id='HM013', branch=BRANCH_B)
        self.admin_client = _api(self.admin)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_permissions(self, position: Position, keys: list[str], client: APIClient | None = None):
        return (client or self.admin_client).put(f'/api/org-structure/positions/{position.pk}/permissions/', {'codenames': keys}, format='json')

    def _assign(self, employee: User, position: Position, start=None, end=None, client: APIClient | None = None):
        payload = {'employee': str(employee.pk), 'effective_from': (start or self.today).isoformat()}
        if end:
            payload['effective_to'] = end.isoformat()
        return (client or self.admin_client).post(f'/api/org-structure/positions/{position.pk}/placements/', payload, format='json')

    def _hr_manager(self, employee: User | None = None, keys: list[str] | None = None) -> User:
        """The administrator configures the HR Manager position and assigns the employee, through the real endpoints."""
        employee = employee or self.hr_employee
        self.assertEqual(self._set_permissions(self.hr_position, keys or HR_MANAGER_KEYS).status_code, 200)
        self.assertEqual(self._assign(employee, self.hr_position, start=self.today - timedelta(days=5)).status_code, 200)
        return employee

    def _status(self, user: User, method: str, url: str, payload=None) -> int:
        return getattr(_api(user), method)(url, payload or {}, format='json').status_code

    def _assert_capabilities(self, user: User, allowed: set[str]):
        for capability, method, url, payload in capability_probes(self.target):
            status_code = self._status(user, method, url, payload)
            if capability in allowed:
                self.assertNotIn(status_code, (401, 403), f'{capability} should be allowed ({method} {url})')
            else:
                self.assertEqual(status_code, 403, f'{capability} should be denied ({method} {url})')

    def _holds_hr_access(self, user: User) -> bool:
        return self._status(user, 'get', '/api/onboarding/approvals/') != 403

    # ── configure, assign, receive ────────────────────────────────────────────

    def test_the_employee_receives_exactly_the_configured_capabilities_through_the_assignment(self):
        self._assert_capabilities(self.hr_employee, set())  # before the assignment: nothing
        employee = self._hr_manager()
        self._assert_capabilities(employee, {'employees.view', 'employees.create', 'employees.edit', 'onboarding.edit',
                                             'onboarding.approve', 'attendance.view', 'leave.approve', 'manage leave policies'})
        granted = set(effective_permission_codenames(employee))
        self.assertTrue(set(HR_MANAGER_KEYS) <= granted)
        for key in NEVER_BY_DEFAULT:
            self.assertNotIn(key, granted, key)
        for label, method, url in DENIED_FOR_HR_MANAGER:
            self.assertEqual(self._status(employee, method, url), 403, label)

    def test_a_seat_missing_one_capability_is_denied_only_that_capability(self):
        keys = [key for key in HR_MANAGER_KEYS if key != 'onboarding.approve']
        employee = self._hr_manager(keys=keys)
        self._assert_capabilities(employee, {'employees.view', 'employees.create', 'employees.edit', 'onboarding.edit',
                                             'attendance.view', 'leave.approve', 'manage leave policies'})

    def test_an_employee_without_an_assignment_is_denied_everywhere(self):
        self._hr_manager()  # the seat is configured and held by somebody else
        self._assert_capabilities(self.other_employee, set())

    def test_the_hr_manager_cannot_use_the_permission_administration_screens(self):
        employee = self._hr_manager()
        self.assertEqual(self._set_permissions(self.hr_position, HR_MANAGER_KEYS + ['payroll.edit'], client=_api(employee)).status_code, 403)
        self.assertEqual(self._assign(self.other_employee, self.hr_position, client=_api(employee)).status_code, 403)
        self.assertEqual(self._status(employee, 'put', f'/api/employees/{self.other_employee.pk}/permissions/', {'codenames': ['payroll.view']}), 403)
        self.assertNotIn('payroll.edit', effective_permission_codenames(employee))

    # ── nobody grants themselves anything ─────────────────────────────────────

    def test_nobody_can_place_themselves_on_a_seat(self):
        placer = make_user('hrm_placer@test.com', role=make_role('hrm_placer', permission_codenames=['org_structure.edit', 'org_chart.view']), employee_id='HM020', branch=BRANCH_A)
        before = Placement.objects.count()
        self.assertEqual(self._assign(placer, self.hr_position, client=_api(placer)).status_code, 403)
        self.assertEqual(self._assign(self.admin, self.hr_position, client=self.admin_client).status_code, 403)
        self.assertEqual(Placement.objects.count(), before)

    def test_a_placer_may_still_assign_other_people(self):
        placer = make_user('hrm_placer2@test.com', role=make_role('hrm_placer2', permission_codenames=['org_structure.edit', 'org_chart.view']), employee_id='HM021', branch=BRANCH_A)
        self.assertEqual(self._assign(self.hr_employee, self.hr_position, client=_api(placer)).status_code, 200)

    def test_a_seat_that_carries_full_access_can_only_be_filled_by_a_full_access_user(self):
        placer = make_user('hrm_placer3@test.com', role=make_role('hrm_placer3', permission_codenames=['org_structure.edit', 'org_chart.view']), employee_id='HM022', branch=BRANCH_A)
        backup_admin_seat = Position.objects.create(org_unit=self.unit, title='Backup Administrator', grade='L5')
        PositionPermission.objects.create(position=backup_admin_seat, permission=Permission.objects.get(codename='settings.edit'))
        self.assertEqual(self._assign(self.other_employee, backup_admin_seat, client=_api(placer)).status_code, 403)
        self.assertFalse(Placement.objects.filter(employee=self.other_employee, position=backup_admin_seat).exists())
        self.assertEqual(self._assign(self.other_employee, backup_admin_seat, client=self.admin_client).status_code, 200)

    def test_an_administrator_cannot_change_the_permissions_of_the_seat_they_hold(self):
        self.assertEqual(self._set_permissions(self.admin_seat, ['settings.edit', 'org_structure.edit', 'payroll.edit']).status_code, 403)
        self.assertNotIn('payroll.edit', set(self.admin_seat.position_permissions.values_list('permission__codename', flat=True)))
        self.assertEqual(self._set_permissions(self.hr_position, HR_MANAGER_KEYS).status_code, 200)  # another seat is fine
        template = PermissionTemplate.objects.create(name='HRM template')
        applied_to_own_seat = self.admin_client.post(f'/api/settings/permission-templates/{template.pk}/apply/', {'position_ids': [str(self.admin_seat.pk)]}, format='json')
        self.assertEqual(applied_to_own_seat.status_code, 403)
        applied_elsewhere = self.admin_client.post(f'/api/settings/permission-templates/{template.pk}/apply/', {'position_ids': [str(self.hr_position.pk)]}, format='json')
        self.assertEqual(applied_elsewhere.status_code, 200)

    def test_an_administrator_cannot_edit_their_own_extra_permissions_only_other_peoples(self):
        self.assertEqual(self._status(self.admin, 'put', f'/api/employees/{self.admin.pk}/permissions/', {'codenames': ['payroll.view']}), 403)
        self.assertEqual(self._status(self.admin, 'put', f'/api/employees/{self.other_employee.pk}/permissions/', {'codenames': ['leave.view']}), 200)

    # ── effective dates and changes ───────────────────────────────────────────

    def test_an_expired_assignment_grants_nothing(self):
        self._set_permissions(self.hr_position, HR_MANAGER_KEYS)
        self.assertEqual(self._assign(self.hr_employee, self.hr_position, start=self.today - timedelta(days=10), end=self.today - timedelta(days=1)).status_code, 200)
        self.assertFalse(self._holds_hr_access(self.hr_employee))
        self.assertEqual(set(effective_permission_codenames(self.hr_employee)) & set(HR_MANAGER_KEYS), set())

    def test_a_future_dated_assignment_grants_nothing_yet(self):
        self._set_permissions(self.hr_position, HR_MANAGER_KEYS)
        self.assertEqual(self._assign(self.hr_employee, self.hr_position, start=self.today + timedelta(days=3)).status_code, 200)
        self.assertFalse(self._holds_hr_access(self.hr_employee))

    def test_ending_an_assignment_removes_the_access_immediately(self):
        employee = self._hr_manager()
        self.assertTrue(self._holds_hr_access(employee))
        ended = self.admin_client.post(f'/api/org-structure/positions/{self.hr_position.pk}/placements/end/', {'effective_to': (self.today - timedelta(days=1)).isoformat()}, format='json')
        self.assertEqual(ended.status_code, 200, ended.json())
        self.assertFalse(self._holds_hr_access(employee))
        self._assert_capabilities(employee, set())

    def test_reassigning_the_seat_moves_the_access_to_the_new_holder(self):
        first = self._hr_manager(self.hr_employee)
        self.assertEqual(self._assign(self.other_employee, self.hr_position, start=self.today).status_code, 200)
        self.assertFalse(self._holds_hr_access(first))
        self.assertTrue(self._holds_hr_access(self.other_employee))

    def test_moving_the_employee_to_another_seat_replaces_their_access(self):
        employee = self._hr_manager()
        self.assertEqual(self._assign(employee, self.plain_position, start=self.today).status_code, 200)
        self.assertFalse(self._holds_hr_access(employee))
        self.assertEqual(set(effective_permission_codenames(employee)) & set(HR_MANAGER_KEYS), set())

    def test_an_inactive_position_grants_nothing(self):
        employee = self._hr_manager()
        Position.objects.filter(pk=self.hr_position.pk).update(is_active=False)
        self.assertFalse(self._holds_hr_access(employee))

    def test_changing_an_assignment_signs_the_affected_holders_out(self):
        for user in (self.hr_employee, self.other_employee):
            self.assertEqual(APIClient().post('/api/login/', {'email': user.email, 'password': 'TestPass123!'}, format='json').status_code, 200)
        self._set_permissions(self.hr_position, HR_MANAGER_KEYS)
        self.assertEqual(self._assign(self.hr_employee, self.hr_position, start=self.today - timedelta(days=5)).status_code, 200)
        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.hr_employee).exists(), 'the new holder picks up the new access')
        self.assertEqual(self._assign(self.other_employee, self.hr_position, start=self.today).status_code, 200)
        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.other_employee).exists())

    # ── scope and everything else keeps working ───────────────────────────────

    def test_branch_scope_still_applies_to_the_hr_manager(self):
        employee = self._hr_manager()
        self.assertEqual(self._status(employee, 'get', f'/api/employees/{self.target.employee_id}/'), 200)  # same branch
        self.assertEqual(self._status(employee, 'get', f'/api/employees/{self.far_employee.employee_id}/'), 404)  # other branch
        self.assertEqual(self._status(employee, 'post', f'/api/employees/{self.far_employee.employee_id}/bank-change/approve/'), 404)

    def test_existing_non_hr_seats_keep_working_and_stay_limited(self):
        lead = make_user('hrm_lead@test.com', role=make_role('hrm_lead', permission_codenames=['leave.approve', 'leave.view'], can_manage_team=True), employee_id='HM030', branch=BRANCH_A)
        self._assert_capabilities(lead, {'leave.approve', 'manage leave policies'})
        self._assert_capabilities(self.other_employee, set())

    def test_a_title_alone_grants_nothing_and_a_non_hr_title_with_the_rows_works(self):
        titled_hr_without_rows = Position.objects.create(org_unit=self.unit, title='Chief HR Manager', grade='L5')
        self.assertEqual(self._assign(self.hr_employee, titled_hr_without_rows, start=self.today - timedelta(days=2)).status_code, 200)
        self._assert_capabilities(self.hr_employee, set())
        talent_seat = Position.objects.create(org_unit=self.unit, title='Talent Coordinator', grade='L3')
        self._set_permissions(talent_seat, HR_MANAGER_KEYS)
        self.assertEqual(self._assign(self.other_employee, talent_seat, start=self.today - timedelta(days=2)).status_code, 200)
        self.assertTrue(self._holds_hr_access(self.other_employee))

    def test_no_role_model_or_role_field_exists_any_more(self):
        with self.assertRaises(LookupError):
            apps.get_model('accounts', 'Role')
        self.assertNotIn('role', {field.name for field in User._meta.get_fields()})
