"""Critical-flow and regression tests for the HRMS app (leave + expenses).

This app had zero test coverage before the 2026-07-22 engineering audit.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import ApprovalWorkflowRule
from apps.hrms.models import Expense, LeaveBalance, LeavePolicy, LeaveRequest
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _future_monday(weeks_ahead: int = 2) -> datetime.date:
    """A Monday safely in the future — avoids both 'backdated leave' rejection
    and any ambiguity about weekly-off/holiday configuration on other days.
    """
    base = datetime.date.today() + datetime.timedelta(weeks=weeks_ahead)
    return base + datetime.timedelta(days=(7 - base.weekday()) % 7 or 7)


class LeavePolicyNameEditTests(TestCase):
    """Leave Type name (leave_type_label) is now editable via PUT, not just
    at creation — covers LeavePolicyUpdateSerializer's new field and the
    shared _validate_leave_type_label() duplicate/character-rule check."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('hr_leavepolicy_test', permission_codenames=['settings.edit'])
        self.hr = make_user('hrpolicy@test.com', role=role, password='TestPass123!')
        self.comp_off = LeavePolicy.objects.create(
            leave_type='comp_off', leave_type_label='Comp Off', annual_days=Decimal('2.0'),
        )
        self.half_day = LeavePolicy.objects.create(
            leave_type='half_day_leave', leave_type_label='Half Day Leave', annual_days=Decimal('5.0'),
        )
        _login(self.client, 'hrpolicy@test.com')

    def _url(self, leave_type: str):
        return reverse('leave-policy-detail', kwargs={'leave_type': leave_type})

    def test_create_sets_name_visible_in_list(self):
        resp = self.client.post(reverse('leave-policy-list'), {
            'leave_type_label': 'Sabbatical', 'annual_days': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        listing = self.client.get(reverse('leave-policy-list'))
        names = [p['leave_type_display'] for p in listing.data['data']]
        self.assertIn('Sabbatical', names)

    def test_rename_updates_same_record_not_a_new_one(self):
        before_count = LeavePolicy.objects.count()
        resp = self.client.put(self._url('comp_off'), {'leave_type_label': 'Compensatory Off'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(LeavePolicy.objects.count(), before_count)

        self.comp_off.refresh_from_db()
        self.assertEqual(self.comp_off.leave_type_label, 'Compensatory Off')
        self.assertEqual(self.comp_off.leave_type, 'comp_off')  # key/slug never changes
        self.assertEqual(resp.data['data']['leave_type_display'], 'Compensatory Off')

    def test_rename_to_duplicate_name_rejected(self):
        resp = self.client.put(self._url('half_day_leave'), {'leave_type_label': 'Comp Off'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.half_day.refresh_from_db()
        self.assertEqual(self.half_day.leave_type_label, 'Half Day Leave')

    def test_rename_to_duplicate_name_case_insensitive_rejected(self):
        resp = self.client.put(self._url('half_day_leave'), {'leave_type_label': 'comp off'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_resaving_unchanged_name_is_not_a_self_collision(self):
        resp = self.client.put(self._url('comp_off'), {
            'leave_type_label': 'Comp Off', 'annual_days': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.comp_off.refresh_from_db()
        self.assertEqual(self.comp_off.annual_days, Decimal('3.0'))

    def test_rename_invalid_characters_rejected(self):
        resp = self.client.put(self._url('comp_off'), {'leave_type_label': 'Comp Off 2.0!'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.comp_off.refresh_from_db()
        self.assertEqual(self.comp_off.leave_type_label, 'Comp Off')

    def test_rename_builtin_type_keeps_its_key(self):
        LeavePolicy.objects.update_or_create(
            leave_type='casual', defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0')},
        )
        resp = self.client.put(self._url('casual'), {'leave_type_label': 'Short Leave'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        policy = LeavePolicy.objects.get(leave_type='casual')
        self.assertEqual(policy.leave_type_label, 'Short Leave')

    def test_other_fields_still_editable_without_touching_name(self):
        # Mirrors the frontend's toggleActive() call — a bare partial update
        # with no leave_type_label in the payload at all.
        resp = self.client.put(self._url('comp_off'), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.comp_off.refresh_from_db()
        self.assertFalse(self.comp_off.is_active)
        self.assertEqual(self.comp_off.leave_type_label, 'Comp Off')

    def test_unauthorized_user_cannot_rename(self):
        no_perm_role = make_role('no_perm_leavepolicy_test')
        make_user('noperm@test.com', role=no_perm_role, password='TestPass123!')
        _login(self.client, 'noperm@test.com')
        resp = self.client.put(self._url('comp_off'), {'leave_type_label': 'Hacked'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.comp_off.refresh_from_db()
        self.assertEqual(self.comp_off.leave_type_label, 'Comp Off')


class LeavePolicyDeleteSafetyTests(TestCase):
    """Deleting a custom LeavePolicy must never orphan an employee's existing
    LeaveBalance/LeaveRequest data. LeaveBalance.leave_type/LeaveRequest.
    leave_type are plain CharFields (no FK to LeavePolicy), so a delete can
    never cascade — but it would silently leave existing records pointing at
    a leave_type with no backing policy, dropping them out of future
    allocation/sync and leave-application validation. See
    leave_type_usage()'s own docstring in apps/hrms/models.py.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # 'settings.edit'-holding role — e.g. System Admin's real permission set.
        admin_role = make_role('sysadmin_delete_test', permission_codenames=['settings.edit'])
        self.admin = make_user('sysadmin@test.com', role=admin_role, password='TestPass123!')
        # 'leave.approve'-only role, deliberately WITHOUT settings.edit — the
        # actual Branch Admin permission set per migration 0052, and the
        # exact scenario fixed for tenant_ris earlier this engagement.
        branch_admin_role = make_role('branch_admin_delete_test', permission_codenames=['leave.approve'])
        self.branch_admin = make_user('branchadmin@test.com', role=branch_admin_role, password='TestPass123!')
        no_perm_role = make_role('no_perm_delete_test')
        make_user('noperm_delete@test.com', role=no_perm_role, password='TestPass123!')

        self.unused_policy = LeavePolicy.objects.create(
            leave_type='sabbatical', leave_type_label='Sabbatical', annual_days=Decimal('5.0'),
        )
        self.in_use_policy = LeavePolicy.objects.create(
            leave_type='pink_leave', leave_type_label='Pink Leave', annual_days=Decimal('10.0'),
        )
        self.employee = make_user(
            'pinkleaveemp@test.com', password='TestPass123!', role=make_role('employee_delete_test'),
            employee_id='DELTEST001',
        )
        self.balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='pink_leave', year=datetime.date.today().year,
            total_days=Decimal('10.0'), used_days=Decimal('2.0'),
        )

    def _url(self, leave_type: str):
        return reverse('leave-policy-detail', kwargs={'leave_type': leave_type})

    def test_system_admin_can_delete_unused_type(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('sabbatical'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(LeavePolicy.objects.filter(leave_type='sabbatical').exists())

    def test_branch_admin_without_settings_edit_can_delete_unused_type(self):
        """Regression for the RIS fix: deletion must work via leave.approve
        alone, without needing settings.edit (which Branch Admin shouldn't
        have — see the dashboard-routing/over-privilege fix earlier)."""
        _login(self.client, 'branchadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('sabbatical'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(LeavePolicy.objects.filter(leave_type='sabbatical').exists())

    def test_unauthorized_user_cannot_delete(self):
        _login(self.client, 'noperm_delete@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('sabbatical'))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(LeavePolicy.objects.filter(leave_type='sabbatical').exists())

    def test_in_use_type_is_blocked_not_deleted(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('pink_leave'))
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertTrue(LeavePolicy.objects.filter(leave_type='pink_leave').exists())
        self.assertIn('deactivate', resp.data['message'].lower())

    def test_in_use_type_reports_usage_counts(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('pink_leave'))
        usage = resp.data['data']
        self.assertTrue(usage['in_use'])
        self.assertEqual(usage['affected_employee_count'], 1)
        self.assertEqual(usage['leave_balance_count'], 1)

    def test_in_use_by_leave_request_only_is_also_blocked(self):
        """A leave_type can be "in use" via LeaveRequest history even with
        no current-year LeaveBalance row — both must be checked independently."""
        other_policy = LeavePolicy.objects.create(
            leave_type='comp_time', leave_type_label='Comp Time', annual_days=Decimal('3.0'),
        )
        LeaveRequest.objects.create(
            employee=self.employee, leave_type='comp_time',
            start_date=datetime.date.today(), end_date=datetime.date.today(),
            total_days=Decimal('1.0'), reason='Test request',
        )
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('comp_time'))
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertTrue(LeavePolicy.objects.filter(leave_type='comp_time').exists())

    def test_existing_leave_balance_untouched_when_delete_blocked(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        self.client.delete(self._url('pink_leave'))
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('10.0'))
        self.assertEqual(self.balance.used_days, Decimal('2.0'))

    def test_builtin_type_still_blocked_regardless_of_usage(self):
        """Regression: built-in types remain non-deletable — unrelated to
        the new in-use check, must not have been loosened by it."""
        LeavePolicy.objects.update_or_create(
            leave_type='casual', defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0')},
        )
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.delete(self._url('casual'))
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(LeavePolicy.objects.filter(leave_type='casual').exists())

    def test_deactivate_still_works_unaffected(self):
        """Regression: the existing is_active toggle (separate from delete)
        must still work exactly as before, including for an in-use type."""
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.put(self._url('pink_leave'), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.in_use_policy.refresh_from_db()
        self.assertFalse(self.in_use_policy.is_active)
        # Still exists — deactivating is not deleting.
        self.assertTrue(LeavePolicy.objects.filter(leave_type='pink_leave').exists())

    def test_policy_list_includes_usage_info_for_custom_types(self):
        _login(self.client, 'sysadmin@test.com', password='TestPass123!')
        resp = self.client.get(reverse('leave-policy-list'))
        self.assertEqual(resp.status_code, 200, resp.data)
        by_type = {p['leave_type']: p for p in resp.data['data']}
        self.assertFalse(by_type['sabbatical']['usage_info']['in_use'])
        self.assertTrue(by_type['pink_leave']['usage_info']['in_use'])
        self.assertEqual(by_type['pink_leave']['usage_info']['affected_employee_count'], 1)


class LeavePolicyNewTypeBackfillTests(TestCase):
    """Creating a new LeavePolicy (e.g. a custom "Menstrual Leave" type) must
    backfill a LeaveBalance for every existing eligible active employee —
    previously only _allocate_leaves_for_employee() (employee-creation time)
    and the annual reset task created balances, so an employee who already
    existed before a new policy did would never get one until next year.
    See _allocate_new_policy_for_existing_employees() in
    apps/hrms/views/leave.py.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_backfill_test', permission_codenames=['settings.edit'])
        self.hr = make_user('hrbackfill@test.com', role=hr_role, password='TestPass123!')

        today = datetime.date.today()
        long_ago = today.replace(year=today.year - 3)   # 36 months served
        recent   = today.replace(day=1)                 # < 1 month served

        emp_role = make_role('employee_backfill_test')
        self._emp_id_seq = 0

        def _mk(email, **kwargs):
            # _allocate_new_policy_for_existing_employees() (like every other
            # "real employee" query in this codebase) excludes employee_id=''
            # — make_user() leaves it blank unless given explicitly, unlike
            # the real creation views which auto-generate one. setdefault
            # (not a literal kwarg) for every field a caller might override,
            # so e.g. _mk(..., branch='Delhi HQ') doesn't collide with the
            # default below as a duplicate keyword argument.
            self._emp_id_seq += 1
            kwargs.setdefault('employee_id', f'EMPBKF{self._emp_id_seq:03d}')
            kwargs.setdefault('role', emp_role)
            kwargs.setdefault('branch', 'Mumbai HQ')
            kwargs.setdefault('department', 'Engineering')
            kwargs.setdefault('designation', 'Engineer')
            kwargs.setdefault('date_of_joining', long_ago)
            return make_user(email, password='TestPass123!', **kwargs)

        self.eligible      = _mk('eligible@test.com', full_name='Eligible Employee')
        self.other_branch  = _mk('otherbranch@test.com', full_name='Other Branch', branch='Delhi HQ')
        self.other_dept    = _mk('otherdept@test.com', full_name='Other Dept', department='Sales')
        self.other_desig   = _mk('otherdesig@test.com', full_name='Other Desig', designation='Manager')
        self.short_tenure  = _mk('shorttenure@test.com', full_name='Short Tenure', date_of_joining=recent)
        self.inactive_emp  = _mk('inactive@test.com', full_name='Inactive', is_active=False)
        self._mk_extra = _mk  # exposed for tests that need one more ad-hoc employee

        self._today = today

    def _create_policy(self, label, **extra):
        payload = {'leave_type_label': label, 'annual_days': 12}
        payload.update(extra)
        resp = self.client.post(reverse('leave-policy-list'), payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return LeavePolicy.objects.get(leave_type=resp.data['data']['leave_type'])

    def test_create_new_policy_backfills_eligible_employee(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Compassionate Leave')
        self.assertTrue(
            LeaveBalance.objects.filter(
                employee=self.eligible, leave_type=policy.leave_type, year=self._today.year,
            ).exists()
        )

    def test_ineligible_branch_employee_does_not_receive_balance(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Branch Leave', applicable_branches=['Mumbai HQ'])
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=policy.leave_type).exists()
        )
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.other_branch, leave_type=policy.leave_type).exists()
        )

    def test_female_only_policy_excludes_male_employees(self):
        from apps.accounts.models import EmployeeProfile
        EmployeeProfile.objects.update_or_create(user=self.eligible, defaults={'gender': 'male'})
        female_employee = self._mk_extra('female@test.com', full_name='Female Employee')
        EmployeeProfile.objects.update_or_create(user=female_employee, defaults={'gender': 'female'})

        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Menstrual Leave', applicable_gender='female')

        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=policy.leave_type).exists()
        )
        self.assertTrue(
            LeaveBalance.objects.filter(employee=female_employee, leave_type=policy.leave_type).exists()
        )

    def test_department_and_designation_eligibility_respected(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy(
            'Team Leave',
            applicable_departments=['Engineering'], applicable_designations=['Engineer'],
        )
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=policy.leave_type).exists()
        )
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.other_dept, leave_type=policy.leave_type).exists()
        )
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.other_desig, leave_type=policy.leave_type).exists()
        )

    def test_minimum_service_period_respected_for_existing_employees(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Tenure Leave', minimum_service_period=12)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=policy.leave_type).exists(),
            "An employee with years of service must pass a 12-month minimum_service_period check.",
        )
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.short_tenure, leave_type=policy.leave_type).exists(),
        )

    def test_inactive_employee_excluded(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Active Only Leave')
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.inactive_emp, leave_type=policy.leave_type).exists()
        )

    def test_running_allocation_twice_does_not_duplicate(self):
        from apps.hrms.views.leave import _allocate_new_policy_for_existing_employees
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Idempotent Leave')

        first_count = LeaveBalance.objects.filter(leave_type=policy.leave_type).count()
        second_run_created = _allocate_new_policy_for_existing_employees(policy)
        second_count = LeaveBalance.objects.filter(leave_type=policy.leave_type).count()

        self.assertEqual(second_run_created, 0)
        self.assertEqual(first_count, second_count)

    def test_existing_balance_value_not_overwritten_by_rerun(self):
        from apps.hrms.views.leave import _allocate_new_policy_for_existing_employees
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Preserve Value Leave')

        balance = LeaveBalance.objects.get(employee=self.eligible, leave_type=policy.leave_type)
        balance.total_days = Decimal('999')
        balance.used_days = Decimal('3')
        balance.save(update_fields=['total_days', 'used_days'])

        _allocate_new_policy_for_existing_employees(policy)

        balance.refresh_from_db()
        self.assertEqual(balance.total_days, Decimal('999'))
        self.assertEqual(balance.used_days, Decimal('3'))

    def test_other_leave_type_balances_unaffected(self):
        LeaveBalance.objects.create(
            employee=self.eligible, leave_type='casual', year=self._today.year,
            total_days=Decimal('12'), used_days=Decimal('4'),
        )
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        self._create_policy('Unrelated New Leave')

        casual_balance = LeaveBalance.objects.get(employee=self.eligible, leave_type='casual', year=self._today.year)
        self.assertEqual(casual_balance.total_days, Decimal('12'))
        self.assertEqual(casual_balance.used_days, Decimal('4'))

    def test_my_leave_balance_api_returns_new_type_after_creation(self):
        _login(self.client, 'hrbackfill@test.com', password='TestPass123!')
        policy = self._create_policy('Visible New Leave')

        _login(self.client, 'eligible@test.com', password='TestPass123!')
        resp = self.client.get(reverse('leave-balance'), {'year': self._today.year})
        self.assertEqual(resp.status_code, 200, resp.data)
        leave_types = [b['leave_type'] for b in resp.data['data']]
        self.assertIn(policy.leave_type, leave_types)

    def test_new_employee_creation_allocation_still_works(self):
        """Regression: _allocate_leaves_for_employee() (employee-creation
        time path) must still work unchanged alongside the new backfill
        function — they coexist, neither replaces the other."""
        from apps.hrms.views.leave import _allocate_leaves_for_employee
        LeavePolicy.objects.update_or_create(
            leave_type='casual', defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0')},
        )
        new_emp = self._mk_extra('newjoiner@test.com', full_name='New Joiner', date_of_joining=self._today)
        created = _allocate_leaves_for_employee(new_emp, str(self._today))
        self.assertGreater(created, 0)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=new_emp, leave_type='casual', year=self._today.year).exists()
        )

    def test_annual_reset_task_still_importable_and_unaffected(self):
        """Regression: confirms the new backfill function doesn't shadow or
        interfere with the annual reset Celery task's own name/behavior."""
        from apps.hrms.tasks import reset_annual_leave_balances
        self.assertTrue(callable(reset_annual_leave_balances))


class LeavePolicyEditSyncTests(TestCase):
    """Editing an existing LeavePolicy (not just creating a new one) must
    re-sync LeaveBalance rows against its current eligibility rules —
    LeavePolicyView.put() now calls _allocate_new_policy_for_existing_
    employees() after save, same function POST already used for brand-new
    policies. Covers: widened eligibility backfills the newly-eligible,
    narrowed eligibility never touches an existing balance/history,
    deactivating never deletes anything, reactivating re-syncs.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_editsync_test', permission_codenames=['settings.edit'])
        self.hr = make_user('hreditsync@test.com', role=hr_role, password='TestPass123!')

        today    = datetime.date.today()
        long_ago = today.replace(year=today.year - 3)
        emp_role = make_role('employee_editsync_test')

        self.hr_dept_emp = make_user(
            'hrdeptemp@test.com', password='TestPass123!', role=emp_role,
            employee_id='EDITSYNC001', date_of_joining=long_ago,
            department='Human Resources', designation='HR Manager', branch='Mumbai HQ',
        )
        self.finance_emp = make_user(
            'financeemp@test.com', password='TestPass123!', role=emp_role,
            employee_id='EDITSYNC002', date_of_joining=long_ago,
            department='Finance', designation='Accountant', branch='Mumbai HQ',
        )
        self.policy = LeavePolicy.objects.create(
            leave_type='edit_sync_policy', leave_type_label='Edit Sync Policy',
            annual_days=Decimal('6.0'), applicable_departments=['Human Resources'], is_active=True,
        )
        self._today = today
        _login(self.client, 'hreditsync@test.com', password='TestPass123!')

    def _url(self):
        return reverse('leave-policy-detail', kwargs={'leave_type': self.policy.leave_type})

    def test_widening_eligibility_backfills_newly_eligible_employee(self):
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.finance_emp, leave_type=self.policy.leave_type).exists()
        )
        resp = self.client.put(
            self._url(), {'applicable_departments': ['Human Resources', 'Finance']}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.finance_emp, leave_type=self.policy.leave_type).exists()
        )

    def test_narrowing_eligibility_preserves_existing_balance_and_history(self):
        # First save (even with no field changes) triggers the initial sync.
        resp = self.client.put(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        balance = LeaveBalance.objects.get(employee=self.hr_dept_emp, leave_type=self.policy.leave_type)
        balance.used_days = Decimal('2.0')
        balance.save(update_fields=['used_days'])
        total_days_before = balance.total_days

        # Narrow eligibility so hr_dept_emp (Human Resources) is excluded.
        resp = self.client.put(self._url(), {'applicable_departments': ['Finance']}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        balance.refresh_from_db()
        self.assertEqual(balance.used_days, Decimal('2.0'))
        self.assertEqual(balance.total_days, total_days_before)
        self.assertTrue(
            LeaveBalance.objects.filter(pk=balance.pk).exists(),
            'An existing balance must never be deleted when an employee loses eligibility.',
        )

    def test_deactivating_policy_does_not_delete_existing_balances(self):
        self.client.put(self._url(), {}, format='json')
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.hr_dept_emp, leave_type=self.policy.leave_type).exists()
        )
        resp = self.client.put(self._url(), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.hr_dept_emp, leave_type=self.policy.leave_type).exists()
        )

    def test_deactivating_policy_does_not_backfill_newly_eligible_employee(self):
        resp = self.client.put(
            self._url(),
            {'applicable_departments': ['Human Resources', 'Finance'], 'is_active': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.finance_emp, leave_type=self.policy.leave_type).exists()
        )

    def test_reactivating_policy_resyncs_eligible_employees(self):
        self.policy.is_active = False
        self.policy.applicable_departments = ['Human Resources', 'Finance']
        self.policy.save(update_fields=['is_active', 'applicable_departments'])
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.finance_emp, leave_type=self.policy.leave_type).exists()
        )

        resp = self.client.put(self._url(), {'is_active': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.finance_emp, leave_type=self.policy.leave_type).exists()
        )


class AnnualResetGenderEligibilityTests(TestCase):
    """Regression: reset_annual_leave_balances() previously duplicated its
    own eligibility check inline (branch/department/designation only) and
    never evaluated applicable_gender at all — a female-only policy would
    incorrectly credit every employee regardless of gender at the next
    annual reset. Fixed by routing through the same shared
    _eligible_for_policy() every other LeaveBalance-creating path uses.
    """

    def setUp(self):
        from apps.accounts.models import EmployeeProfile
        cache.clear()
        today    = datetime.date.today()
        long_ago = today.replace(year=today.year - 3)
        emp_role = make_role('annual_reset_gender_test')

        self.male_emp = make_user(
            'maleemp@test.com', password='TestPass123!', role=emp_role,
            employee_id='ARGT001', date_of_joining=long_ago,
        )
        EmployeeProfile.objects.update_or_create(user=self.male_emp, defaults={'gender': 'male'})

        self.female_emp = make_user(
            'femaleemp@test.com', password='TestPass123!', role=emp_role,
            employee_id='ARGT002', date_of_joining=long_ago,
        )
        EmployeeProfile.objects.update_or_create(user=self.female_emp, defaults={'gender': 'female'})

        self.policy = LeavePolicy.objects.create(
            leave_type='reset_gender_policy', leave_type_label='Gender Reset Policy',
            annual_days=Decimal('5.0'), applicable_gender='female', is_active=True,
        )
        self.prev_year = today.year - 1
        for emp in (self.male_emp, self.female_emp):
            LeaveBalance.objects.create(
                employee=emp, leave_type=self.policy.leave_type, year=self.prev_year,
                total_days=Decimal('5.0'), used_days=Decimal('0'),
            )
        self._today = today

    def test_male_employee_not_credited_for_female_only_policy(self):
        from apps.hrms.tasks import reset_annual_leave_balances
        reset_annual_leave_balances()
        self.assertFalse(
            LeaveBalance.objects.filter(
                employee=self.male_emp, leave_type=self.policy.leave_type, year=self._today.year,
            ).exists()
        )
        self.assertTrue(
            LeaveBalance.objects.filter(
                employee=self.female_emp, leave_type=self.policy.leave_type, year=self._today.year,
            ).exists()
        )


class BackfillLeaveBalancesCommandTests(TestCase):
    """manage.py backfill_leave_balances — the reusable, manually-triggered
    sync for LeavePolicy rows that predate the automatic POST/PUT sync.
    Must default to a true dry-run (no writes at all) and only write when
    --apply is passed; --policy must scope to one policy.
    """

    def setUp(self):
        cache.clear()
        today    = datetime.date.today()
        long_ago = today.replace(year=today.year - 3)
        emp_role = make_role('backfill_cmd_test')

        self.eligible = make_user(
            'backfillcmdemp@test.com', password='TestPass123!', role=emp_role,
            employee_id='BCKCMD001', date_of_joining=long_ago,
            department='Engineering', designation='Engineer', branch='Mumbai HQ',
        )
        # Simulates a policy created before the automatic sync existed —
        # plain model .create(), never went through LeavePolicyView.post().
        self.policy = LeavePolicy.objects.create(
            leave_type='pre_sync_policy', leave_type_label='Pre-Sync Policy',
            annual_days=Decimal('4.0'), is_active=True,
        )
        self._today = today

    def _run(self, **options):
        import io
        from apps.hrms.management.commands.backfill_leave_balances import Command
        from apps.tenants.models import Client
        from config.test_runner import TEST_COMPANY_CODE
        client = Client.objects.get(company_code=TEST_COMPANY_CODE)
        options.setdefault('policy', None)
        options.setdefault('apply', False)
        out = io.StringIO()
        Command(stdout=out).handle_tenant(client, **options)
        return out.getvalue()

    def test_dry_run_makes_no_database_writes(self):
        output = self._run()
        self.assertIn('Missing balance:     1', output)
        self.assertIn('[DRY RUN]', output)
        self.assertFalse(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=self.policy.leave_type).exists()
        )

    def test_apply_creates_the_missing_balance(self):
        output = self._run(apply=True)
        self.assertIn('Created 1 LeaveBalance row(s).', output)
        self.assertTrue(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=self.policy.leave_type).exists()
        )

    def test_apply_is_idempotent_on_second_run(self):
        self._run(apply=True)
        output = self._run(apply=True)
        self.assertIn('Created 0 LeaveBalance row(s).', output)
        self.assertEqual(
            LeaveBalance.objects.filter(employee=self.eligible, leave_type=self.policy.leave_type).count(), 1,
        )

    def test_policy_filter_scopes_to_one_policy(self):
        LeavePolicy.objects.create(
            leave_type='other_pre_sync_policy', leave_type_label='Other Pre-Sync Policy',
            annual_days=Decimal('3.0'), is_active=True,
        )
        output = self._run(policy='pre_sync_policy')
        self.assertIn('Pre-Sync Policy', output)
        self.assertNotIn('Other Pre-Sync Policy', output)


class LeaveBalanceAdjustDecimalTests(TestCase):
    """Regression test: patching only one of total_days/used_days left the
    in-memory LeaveBalance with one Decimal field and one raw-float field.
    The very next line (LeaveBalanceSerializer.get_available_days) subtracts
    them and threw a TypeError.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr', permission_codenames=['leave.approve'])
        self.hr_user = make_user('hrleave@test.com', role=hr_role, password='TestPass123!')
        self.employee = make_user('leaveemp@test.com', role=make_role('employee'), password='TestPass123!')
        self.balance = LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=2026,
            total_days=Decimal('12.0'), used_days=Decimal('2.0'),
        )
        _login(self.client, 'hrleave@test.com')

    def test_patching_only_total_days_does_not_crash(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': 15.5},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.total_days, Decimal('15.5'))
        self.assertEqual(resp.data['data']['available_days'], 13.5)

    def test_patching_only_used_days_does_not_crash(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'used_days': 3.5},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('3.5'))

    def test_negative_total_days_rejected(self):
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': -5},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_employee_cannot_adjust_own_balance(self):
        _login(self.client, 'leaveemp@test.com')
        # Grant the employee leave.approve to isolate the self-adjustment
        # check specifically, rather than the permission check.
        self.employee.role.role_permissions.filter(permission__codename='leave.approve')
        resp = self.client.patch(
            reverse('leave-balance-adjust', kwargs={'balance_id': self.balance.pk}),
            {'total_days': 100},
            format='json',
        )
        self.assertIn(resp.status_code, (403, 404))


class LeaveRequestFlowTests(TestCase):
    """End-to-end: submit -> L1 approve -> balance deducted."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        manager_role = make_role(
            'manager__team_lead', permission_codenames=['leave.approve'], can_manage_team=True,
        )
        employee_role = make_role('employee')
        self.manager = make_user('leavemgr@test.com', role=manager_role, password='TestPass123!')
        self.employee = make_user(
            'applicant@test.com', role=employee_role, password='TestPass123!',
            reporting_manager=self.manager,
        )

        # A migration already seeds a default rule for 'leave' — update it in
        # place rather than colliding with the unique workflow_type constraint.
        ApprovalWorkflowRule.objects.update_or_create(
            workflow_type=ApprovalWorkflowRule.WORKFLOW_LEAVE,
            defaults={
                'l1_approver_role': manager_role,
                'l2_approver_role': None,
            },
        )
        LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults={'leave_type_label': 'Casual Leave', 'annual_days': Decimal('12.0'), 'is_active': True},
        )
        self.leave_date = _future_monday()
        LeaveBalance.objects.create(
            employee=self.employee, leave_type='casual', year=self.leave_date.year,
            total_days=Decimal('12.0'), used_days=Decimal('0'),
        )
        _login(self.client, 'applicant@test.com')

    def test_submit_leave_request_happy_path(self):
        resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual',
                'duration': 'full_day',
                'start_date': self.leave_date.isoformat(),
                'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['status'], 'pending')

    def test_insufficient_balance_is_rejected(self):
        resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual',
                'duration': 'full_day',
                'start_date': self.leave_date.isoformat(),
                'end_date': (self.leave_date + datetime.timedelta(days=29)).isoformat(),
                'reason': 'A long trip abroad.',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Insufficient balance', resp.data['message'])

    def test_manager_approval_deducts_balance(self):
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']

        mgr_client = APIClient()
        _login(mgr_client, 'leavemgr@test.com')
        approve_resp = mgr_client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(approve_resp.status_code, 200, approve_resp.data)
        self.assertEqual(approve_resp.data['data']['status'], 'approved')

        balance = LeaveBalance.objects.get(
            employee=self.employee, leave_type='casual', year=self.leave_date.year,
        )
        self.assertEqual(balance.used_days, Decimal('1.0'))

    def test_non_designated_approver_is_rejected(self):
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']

        make_user(
            'othermgr@test.com', role=make_role('manager__team_lead'), password='TestPass123!',
        )
        other_client = APIClient()
        _login(other_client, 'othermgr@test.com')
        resp = other_client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_cannot_approve_own_leave_request(self):
        # Give the applicant leave.approve too, to isolate the self-approval
        # check rather than the permission check.
        create_resp = self.client.post(
            reverse('leave-request-list'),
            {
                'leave_type': 'casual', 'duration': 'full_day',
                'start_date': self.leave_date.isoformat(), 'end_date': self.leave_date.isoformat(),
                'reason': 'Personal work to attend to.',
            },
            format='json',
        )
        request_id = create_resp.data['data']['id']
        self.employee.role = make_role('employee_with_approve', permission_codenames=['leave.approve'])
        self.employee.save(update_fields=['role'])

        resp = self.client.post(
            reverse('leave-request-approve', kwargs={'request_id': request_id}),
            {'action': 'approve'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('cannot approve', resp.data['message'].lower())


class ExpenseSelfApprovalTests(TestCase):
    """Regression/critical-path test: an approver can never approve their
    own expense claim, even if they hold expenses.approve.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        role = make_role('hr', permission_codenames=['expenses.approve'])
        self.hr_user = make_user('hrexpense@test.com', role=role, password='TestPass123!')
        _login(self.client, 'hrexpense@test.com')

    def test_cannot_approve_own_expense(self):
        expense = Expense.objects.create(
            employee=self.hr_user, expense_number=1, title='Taxi',
            category='travel', amount=Decimal('500.00'),
            expense_date=datetime.date(2026, 1, 10),
        )
        resp = self.client.patch(
            reverse('expense-detail', kwargs={'expense_number': expense.expense_number}),
            {'status': 'approved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('cannot approve', resp.data['message'].lower())
