"""
Sensitive-assignment guard (services_access_guards.assignment_refusal) on the hiring / editing doors.

For each door: an everyday HR action still works, a seat carrying sensitive permissions the actor does not hold is refused
(403; the existing `settings.edit` refusals stay 400), and a full-access administrator may administer sensitive seats. Nobody
assigns themselves, and personal extras never count as authority to grant. The personnel-action engines and the "every
assign_position call site is guarded" scan are in tests_assignment_guards_actions.py.
"""
from __future__ import annotations

from datetime import date

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

import apps.accounts.tests_hire_wizard as wizard
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import (
    BaselinePermission, EmployeePermission, OrgUnit, Permission, Placement, Position, PositionPermission, User,
)
from apps.accounts.services_access_guards import SENSITIVE_PERMISSIONS
from apps.accounts.services_placement import assign_position
from apps.branch.models import Branch, City, State

BRANCH = 'Guard Branch'


def _api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _seat(unit: OrgUnit, title: str, keys: list[str], **flags) -> Position:
    position = Position.objects.create(org_unit=unit, title=title, grade='L3', **flags)
    for key in keys:
        PositionPermission.objects.create(position=position, permission=Permission.objects.get(codename=key))
    return position


class SensitivePermissionListTests(TestCase):
    def test_every_listed_key_exists_in_the_permission_catalogue(self):
        known = set(Permission.objects.values_list('codename', flat=True))
        self.assertEqual(sorted(SENSITIVE_PERMISSIONS - known), [])

    def test_the_list_is_explicit_and_keeps_everyday_hr_and_self_service_out(self):
        for everyday in ('employees.view', 'employees.create', 'employees.edit', 'employees.approve', 'employees.raise_action',
                         'onboarding.edit', 'onboarding.approve', 'attendance.view', 'leave.approve', 'payroll.view_own',
                         'org_chart.view', 'separation.approve'):
            self.assertNotIn(everyday, SENSITIVE_PERMISSIONS, everyday)
        for sensitive in ('settings.edit', 'settings.view', 'payroll.edit', 'org_structure.edit', 'employees.reset_password', 'audit.view', 'branches.edit'):
            self.assertIn(sensitive, SENSITIVE_PERMISSIONS, sensitive)

    def test_no_sensitive_key_is_in_the_baseline_every_employee_gets(self):
        baseline = set(BaselinePermission.objects.values_list('permission__codename', flat=True))
        self.assertEqual(baseline & SENSITIVE_PERMISSIONS, set())


class _GuardFixtures(TestCase):
    """HR users with different authority, seats with different power, and a full-access administrator."""

    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Guard Unit')
        self.ordinary = _seat(self.unit, 'Support Analyst', ['leave.view'])
        self.lead = _seat(self.unit, 'Team Lead', ['leave.approve'], can_manage_team=True)
        self.payroll_seat = _seat(self.unit, 'Payroll Executive', ['payroll.view', 'payroll.edit'])
        self.payroll_seat_2 = _seat(self.unit, 'Payroll Executive 2', ['payroll.view', 'payroll.edit'])  # a seat has one holder at a time
        self.branch_seat = _seat(self.unit, 'Branch Lead', ['leave.approve'], can_manage_branch=True)
        self.hr = self._hr('guard_hr@test.com', 'GD001', [])
        self.payroll_hr = self._hr('guard_payroll_hr@test.com', 'GD002', ['payroll.view', 'payroll.edit'])
        self.admin = self._hr('guard_admin@test.com', 'GD003', ['settings.edit'])

    def _hr(self, email: str, employee_id: str, extra_keys: list[str], perms=None) -> User:
        keys = perms or ['employees.view', 'employees.create', 'employees.edit', 'onboarding.approve']
        return make_user(email, role=make_role(f'role_{employee_id}', permission_codenames=keys + extra_keys), employee_id=employee_id, branch=BRANCH)


class EmployeeEditSensitiveSeatTests(_GuardFixtures):
    def setUp(self):
        super().setUp()
        self.person = make_user('guard_person@test.com', employee_id='GD010', branch=BRANCH)

    def _edit(self, actor, position) -> int:
        return _api(actor).put(f'/api/employees/{self.person.employee_id}/', {'position': str(position.pk)}, format='json').status_code

    def test_everyday_seats_including_a_team_lead_seat_are_still_assignable(self):
        self.assertEqual(self._edit(self.hr, self.ordinary), 200)
        self.assertEqual(self._edit(self.hr, self.lead), 200)

    def test_a_seat_with_sensitive_permissions_the_actor_lacks_is_refused_403(self):
        self.assertEqual(self._edit(self.hr, self.payroll_seat), 403)
        self.assertFalse(Placement.objects.filter(employee=self.person, position=self.payroll_seat).exists())

    def test_a_branch_managing_seat_needs_the_branch_flag(self):
        self.assertEqual(self._edit(self.hr, self.branch_seat), 403)

    def test_an_actor_whose_own_seat_holds_the_sensitive_keys_may_assign_the_seat(self):
        self.assertEqual(self._edit(self.payroll_hr, self.payroll_seat), 200)

    def test_personal_extras_are_not_authority_to_grant(self):
        EmployeePermission.objects.create(employee=self.hr, permission=Permission.objects.get(codename='payroll.edit'), granted_by=self.admin)
        EmployeePermission.objects.create(employee=self.hr, permission=Permission.objects.get(codename='payroll.view'), granted_by=self.admin)
        self.assertEqual(self._edit(self.hr, self.payroll_seat), 403)

    def test_a_full_access_administrator_may_administer_sensitive_seats(self):
        self.assertEqual(self._edit(self.admin, self.payroll_seat), 200)
        self.assertEqual(self._edit(self.admin, self.branch_seat), 200)


class HireDoorTests(wizard.HireWizardTestCase):
    def setUp(self):
        super().setUp()
        self.payroll_seat = _seat(self.unit, 'Payroll Executive', ['payroll.view', 'payroll.edit'])
        self.payroll_seat_2 = _seat(self.unit, 'Payroll Executive 2', ['payroll.view', 'payroll.edit'])
        self.ordinary = _seat(self.unit, 'Support Analyst', ['leave.view'])

    def _complete_as(self, actor, position, n: int = 0) -> int:
        action = self._create_draft(position=str(position.id))
        self._set_employment_type(action, 'Permanent')
        draft = self._valid_full_draft()
        draft.update(  # each hire is a different person: the duplicate checks look at email, mobile and PAN
            email=f'guard.hire{n}@test.com', phone=f'98765{n:05d}', pan_number=f'ABCDE{1000 + n}F', aadhaar_number=f'12345678{n:04d}',
        )
        self._patch(action, draft)
        self._upload_all_required_docs(action)
        self.client.force_authenticate(user=actor)
        return self._complete(action).status_code

    def _actor(self, email: str, extra: list[str]) -> User:
        return make_user(email, role=make_role(f'hire_{email[:8]}', permission_codenames=['employees.create'] + extra), employee_id=f'HD{abs(hash(email)) % 900 + 100}')

    def test_hiring_into_an_everyday_seat_still_works(self):
        self.assertEqual(self._complete_as(self.hr_user, self.ordinary), 201)

    def test_hiring_into_a_seat_with_sensitive_permissions_the_hirer_lacks_is_refused(self):
        before = User.objects.count()
        self.assertEqual(self._complete_as(self.hr_user, self.payroll_seat), 403)
        self.assertEqual(User.objects.count(), before)

    def test_a_hirer_whose_own_seat_holds_the_permissions_and_a_full_access_admin_may_hire_into_it(self):
        self.assertEqual(self._complete_as(self._actor('hirer_payroll@test.com', ['payroll.view', 'payroll.edit']), self.payroll_seat, 1), 201)
        self.assertEqual(self._complete_as(self._actor('hirer_admin@test.com', ['settings.edit']), self.payroll_seat_2, 2), 201)

    def test_the_existing_full_access_seat_refusal_stays_400_even_for_an_administrator(self):
        top = _seat(self.unit, 'Backup Administrator', ['settings.edit'])
        self.assertEqual(self._complete_as(self._actor('hirer_admin2@test.com', ['settings.edit']), top), 400)


class EmployeeCreateDoorTests(_GuardFixtures):
    def setUp(self):
        super().setUp()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.get_or_create(branch_code='GB01', defaults={'branch_name': BRANCH, 'state': state, 'city': city})

    def _create(self, actor, position, n: int) -> int:
        payload = {
            'first_name': 'New', 'last_name': f'Hire{n}', 'email': f'guard_new{n}@test.com', 'position': str(position.pk),
            'branch': BRANCH, 'date_of_joining': date.today().isoformat(), 'employee_type': 'Permanent',
        }
        response = _api(actor).post('/api/employees/', payload, format='json')
        return response.status_code

    def test_creating_into_an_everyday_seat_works_and_into_a_sensitive_seat_is_refused(self):
        self.assertEqual(self._create(self.hr, self.ordinary, 1), 201)
        before = User.objects.count()
        self.assertEqual(self._create(self.hr, self.payroll_seat, 2), 403)
        self.assertEqual(User.objects.count(), before)

    def test_the_holder_of_the_permissions_and_a_full_access_admin_may_create_into_the_seat(self):
        self.assertEqual(self._create(self.payroll_hr, self.payroll_seat, 3), 201)
        self.assertEqual(self._create(self.admin, self.payroll_seat_2, 4), 201)

    def test_the_existing_full_access_seat_refusal_stays_400(self):
        top = _seat(self.unit, 'Backup Administrator', ['settings.edit'])
        self.assertEqual(self._create(self.admin, top, 5), 400)


class BulkImportDoorTests(_GuardFixtures):
    def setUp(self):
        super().setUp()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        Branch.objects.get_or_create(branch_code='GB01', defaults={'branch_name': BRANCH, 'state': state, 'city': city})
        self.import_unit = OrgUnit.objects.create(name='Import Unit')
        self.import_ordinary = _seat(self.import_unit, 'Import Analyst', ['leave.view'])
        self.import_payroll = _seat(self.import_unit, 'Import Payroll', ['payroll.view', 'payroll.edit'])
        self.import_payroll_2 = _seat(self.import_unit, 'Import Payroll Two', ['payroll.view', 'payroll.edit'])

    def _import(self, actor, position, email: str) -> dict:
        header = 'First Name,Last Name,Work Email,Role,Org Unit,Position,Company Code,Date of Joining,Date of Birth\n'
        row = f'Bulk,Person,{email},Employee,Import Unit,{position.title},GB01,2024-01-01,1994-01-01'
        upload = SimpleUploadedFile('import.csv', (header + row).encode('utf-8'), content_type='text/csv')
        response = _api(actor).post(reverse('employee-bulk-import'), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['data']

    def test_an_everyday_row_is_created(self):
        self.assertEqual(self._import(self.hr, self.import_ordinary, 'bulk_ok@test.com')['created'], 1)

    def test_a_row_into_a_sensitive_seat_the_importer_lacks_fails_with_a_row_error_and_creates_nobody(self):
        data = self._import(self.hr, self.import_payroll, 'bulk_denied@test.com')
        self.assertEqual((data['created'], data['failed']), (0, 1))
        self.assertTrue(any('sensitive permissions' in error['message'] for error in data['errors']), data['errors'])
        self.assertFalse(User.objects.filter(email='bulk_denied@test.com').exists())

    def test_the_holder_and_a_full_access_admin_may_import_into_the_seat(self):
        self.assertEqual(self._import(self.payroll_hr, self.import_payroll, 'bulk_holder@test.com')['created'], 1)
        self.assertEqual(self._import(self.admin, self.import_payroll_2, 'bulk_admin@test.com')['created'], 1)


class OnboardingApprovalDoorTests(_GuardFixtures):
    def _submitted(self, email: str, employee_id: str) -> User:
        # A candidate whose onboarding was just submitted has no joining date yet: approval sets it (today) before placing them in
        # the seat. (make_user's default past joining date would make that placement overlap a seat the test already assigned.)
        user = make_user(email, employee_id=employee_id, branch=BRANCH, onboarding_status=User.ONBOARDING_SUBMITTED, date_of_joining=None)
        return user

    def _approve(self, actor, user, position) -> int:
        return _api(actor).post(reverse('onboarding-approve', args=[user.id]), {'decision': 'approve', 'position': str(position.pk)}, format='json').status_code

    def test_approving_into_an_everyday_seat_works(self):
        user = self._submitted('guard_cand1@test.com', 'GD020')
        self.assertEqual(self._approve(self.hr, user, self.ordinary), 200)

    def test_approving_into_a_sensitive_seat_the_approver_lacks_is_refused_and_nothing_changes(self):
        user = self._submitted('guard_cand2@test.com', 'GD021')
        self.assertEqual(self._approve(self.hr, user, self.payroll_seat), 403)
        user.refresh_from_db()
        self.assertEqual(user.onboarding_status, User.ONBOARDING_SUBMITTED)
        self.assertFalse(Placement.objects.filter(employee=user).exists())

    def test_the_holder_and_a_full_access_admin_may_approve_into_the_seat(self):
        self.assertEqual(self._approve(self.payroll_hr, self._submitted('guard_cand3@test.com', 'GD022'), self.payroll_seat), 200)
        self.assertEqual(self._approve(self.admin, self._submitted('guard_cand4@test.com', 'GD023'), self.payroll_seat_2), 200)

    def test_re_submitting_the_seat_the_person_already_holds_grants_nothing_new_and_is_not_refused(self):
        user = self._submitted('guard_cand5@test.com', 'GD024')
        assign_position(user, self.payroll_seat, effective_from=date(2026, 1, 1), created_by=self.admin)
        self.assertEqual(self._approve(self.hr, user, self.payroll_seat), 200)
