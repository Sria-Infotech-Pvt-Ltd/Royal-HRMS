"""Edit Record > Company Code: moving an employee to another branch, and the branch list that feeds the dropdown."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.branch.models import Branch, City, State

KONDAPUR_ADDRESS = 'Plot 14, Cyber Towers, Kondapur'
MULUGU_ADDRESS = 'Main Road, Mulugu'


def _branch(name, code, address, status=Branch.STATUS_ACTIVE):
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=code, branch_name=name, address=address, state=state, city=city, allowed_radius_meters=150, status=status,
    )


class _BranchChangeBase(TestCase):
    def setUp(self):
        cache.clear()
        self.kondapur = _branch('Kondapur', 'KDP01', KONDAPUR_ADDRESS)
        self.mulugu = _branch('Mulugu', 'MLG01', MULUGU_ADDRESS)
        self.closed = _branch('Old Closed', 'OLD01', 'Gone', status=Branch.STATUS_INACTIVE)
        self.admin = make_user(
            'admin-bc@test.com', role=make_role('admin_bc', permission_codenames=['settings.edit', 'employees.edit', 'employees.view', 'branches.view']),
        )
        # Branch-scoped HR: may edit employees, but only sees/acts inside their own branch.
        self.hr = make_user(
            'hr-bc@test.com', branch='Kondapur', role=make_role('hr_bc', permission_codenames=['employees.edit', 'employees.view', 'branches.view']),
        )
        self.viewer = make_user('viewer-bc@test.com', role=make_role('viewer_bc', permission_codenames=['employees.view']))
        self.employee = make_user(
            'emp-bc@test.com', employee_id='20000001', branch='Kondapur', work_location=KONDAPUR_ADDRESS,
            phone='9876500001', full_name='Branch Move Subject',
        )
        self.employee.refresh_from_db()   # the post_save signal links branch_fk to Kondapur

    def _as(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    def _url(self, employee=None):
        return reverse('employee-detail', args=[(employee or self.employee).employee_id])


class EmployeeBranchChangeTests(_BranchChangeBase):
    def test_precondition_employee_starts_linked_to_kondapur(self):
        self.assertEqual(self.employee.branch_fk_id, self.kondapur.pk)

    def test_authorized_change_persists_the_branch_and_the_real_link(self):
        response = self._as(self.admin).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.branch, 'Mulugu')
        # branch_fk is what employee counts, headcount, attendance devices and the holiday calendar read; it must follow the move.
        self.assertEqual(self.employee.branch_fk_id, self.mulugu.pk)
        self.assertEqual(Branch.objects.get(pk=self.kondapur.pk).employees.filter(pk=self.employee.pk).count(), 0)
        self.assertEqual(Branch.objects.get(pk=self.mulugu.pk).employees.filter(pk=self.employee.pk).count(), 1)

    def test_a_derived_work_location_follows_the_new_branch(self):
        self._as(self.admin).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.work_location, MULUGU_ADDRESS)
        changes = AuditLog.objects.get(action='employee_updated', object_id=str(self.employee.id)).changes
        self.assertEqual(changes['branch'], {'from': 'Kondapur', 'to': 'Mulugu'})
        self.assertEqual(changes['work_location']['to'], MULUGU_ADDRESS)

    def test_a_hand_entered_work_location_is_preserved_but_the_branch_still_moves(self):
        self.employee.work_location = 'Corner desk, 3rd floor'
        self.employee.save(update_fields=['work_location'])
        self._as(self.admin).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.work_location, 'Corner desk, 3rd floor')
        self.assertEqual(self.employee.branch, 'Mulugu')
        self.assertEqual(self.employee.branch_fk_id, self.mulugu.pk)

    def test_the_edit_record_payload_changes_only_what_it_carries(self):
        """The shape EditRecordModal sends on save (branch plus the other employment fields) leaves unrelated fields alone."""
        before = {field: getattr(self.employee, field) for field in ('full_name', 'phone', 'email', 'date_of_joining', 'reporting_manager_id', 'employee_id')}
        payload = {'employee_type': 'Full-time', 'branch': 'Mulugu', 'work_mode': 'office', 'notice_period_days': 30}
        response = self._as(self.admin).put(self._url(), payload, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.branch, 'Mulugu')
        self.assertEqual(self.employee.work_mode, 'office')
        self.assertEqual({field: getattr(self.employee, field) for field in before}, before)

    def test_resubmitting_the_same_branch_changes_nothing(self):
        self._as(self.admin).patch(self._url(), {'branch': 'Kondapur'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.branch, self.employee.branch_fk_id, self.employee.work_location),
                         ('Kondapur', self.kondapur.pk, KONDAPUR_ADDRESS))
        log = AuditLog.objects.filter(action='employee_updated', object_id=str(self.employee.id)).first()
        self.assertTrue(log is None or 'branch' not in (log.changes or {}))

    def test_a_branch_name_matching_no_branch_leaves_no_stale_link_to_the_old_branch(self):
        """Existing rule: the API stores the name it is given. What it must not do is keep pointing at the OLD branch."""
        self._as(self.admin).patch(self._url(), {'branch': 'Nowhere'}, format='json')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.branch, 'Nowhere')
        self.assertIsNone(self.employee.branch_fk_id)


class EmployeeBranchChangeAuthorizationTests(_BranchChangeBase):
    def _assert_untouched(self):
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.branch, self.employee.branch_fk_id, self.employee.work_location),
                         ('Kondapur', self.kondapur.pk, KONDAPUR_ADDRESS))

    def test_a_user_without_employees_edit_cannot_change_the_branch_through_the_api(self):
        response = self._as(self.viewer).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.assertEqual(response.status_code, 403)
        self._assert_untouched()

    def test_an_anonymous_request_is_refused(self):
        response = self._as(None).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.assertIn(response.status_code, (401, 403))
        self._assert_untouched()

    def test_branch_scoped_hr_cannot_reach_an_employee_of_another_branch(self):
        elsewhere = make_user('emp-mlg@test.com', employee_id='20000002', branch='Mulugu', work_location=MULUGU_ADDRESS)
        response = self._as(self.hr).patch(self._url(elsewhere), {'branch': 'Kondapur'}, format='json')
        self.assertEqual(response.status_code, 404)
        elsewhere.refresh_from_db()
        self.assertEqual(elsewhere.branch, 'Mulugu')

    def test_existing_rule_kept_branch_scoped_hr_may_still_edit_an_employee_of_their_own_branch(self):
        response = self._as(self.hr).patch(self._url(), {'branch': 'Mulugu'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.branch_fk_id, self.mulugu.pk)


class BranchLookupForDropdownTests(_BranchChangeBase):
    """GET /branch/branches/ is what the Company Code dropdown reads."""

    def _names(self, user, **params):
        response = self._as(user).get(reverse('branch-list-create'), {'page_size': 50, **params})
        self.assertEqual(response.status_code, 200, response.content)
        return {row['branch_name']: row for row in response.json()['data']['results']}

    def test_admin_with_status_active_gets_every_active_branch_and_no_inactive_one(self):
        rows = self._names(self.admin, status='active')
        self.assertEqual(set(rows), {'Kondapur', 'Mulugu'})
        self.assertEqual(rows['Kondapur']['branch_code'], 'KDP01')

    def test_without_the_status_filter_inactive_branches_are_returned_too(self):
        self.assertIn('Old Closed', self._names(self.admin))

    def test_branch_scoped_user_only_sees_their_own_branch(self):
        self.assertEqual(set(self._names(self.hr, status='active')), {'Kondapur'})

    def test_a_user_without_branches_view_is_refused(self):
        response = self._as(self.viewer).get(reverse('branch-list-create'), {'status': 'active'})
        self.assertEqual(response.status_code, 403)


class EmployeeDirectoryLocationFilterTests(_BranchChangeBase):
    """GET /employees/stats/ feeds the Locations filter on the Employee directory."""

    def _branch_names(self, user):
        response = self._as(user).get(reverse('employee-stats'))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['data']['branch_names']

    def test_org_wide_admin_sees_every_active_branch_including_one_with_no_employees(self):
        # Only Kondapur has an employee; Mulugu is empty. Both must be offered. The inactive branch must not be.
        self.assertEqual(self._branch_names(self.admin), ['Kondapur', 'Mulugu'])

    def test_a_branch_text_an_employee_still_carries_is_not_dropped(self):
        make_user('emp-old@test.com', employee_id='20000009', branch='Legacy Name')
        self.assertEqual(self._branch_names(self.admin), ['Kondapur', 'Legacy Name', 'Mulugu'])

    def test_branch_scoped_user_still_sees_only_their_own_branch(self):
        self.assertEqual(self._branch_names(self.hr), ['Kondapur'])
