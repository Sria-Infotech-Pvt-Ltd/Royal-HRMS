"""
The reporting manager (L1, the immediate head) follows the org chart on its own.

Before: the head was copied onto the employee once at hire, only when the head was in the same branch, never for a head themselves,
and was then left stale when the org chart changed. Now: any branch, heads report to the head above, and a stored manager that came
from the org chart is kept current whenever a placement / position / unit changes. A manager picked by hand is never touched.
"""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import OrgUnit, Placement, Position, User
from apps.accounts.services_org_chart_managers import resync_all, resync_units, sync_employees
from apps.accounts.views.shared import _auto_assign_managers

TODAY = datetime.date.today()
LONG_AGO = TODAY - datetime.timedelta(days=30)


def seat(unit, title, holder, *, is_chief=False, can_manage_team=False):
    position = Position.objects.create(org_unit=unit, title=title, is_chief=is_chief, can_manage_team=can_manage_team)
    placement = Placement.objects.create(position=position, employee=holder, effective_from=LONG_AGO)
    return position, placement


def reload(user) -> User:
    return User.objects.get(pk=user.pk)


class AutoAssignFollowsTheOrgChartTests(TestCase):
    def setUp(self):
        self.company = OrgUnit.objects.create(name='Chart Company')
        self.dept = OrgUnit.objects.create(name='Chart Department', parent=self.company)
        self.ceo = make_user('chart-ceo@test.com', employee_id='CHT001', branch='Head Office')
        self.dept_head = make_user('chart-head@test.com', employee_id='CHT002', branch='Kondapur')
        seat(self.company, 'CEO', self.ceo, is_chief=True, can_manage_team=True)
        seat(self.dept, 'Head of Department', self.dept_head, is_chief=True, can_manage_team=True)

    def test_a_head_in_another_branch_is_still_the_manager(self):
        worker = make_user('chart-worker@test.com', employee_id='CHT003', branch='Gachibowli')
        seat(self.dept, 'Executive', worker)
        changed = _auto_assign_managers(worker)
        self.assertIn('reporting_manager', changed)
        self.assertEqual(worker.reporting_manager, self.dept_head)
        self.assertTrue(worker.reporting_manager_from_org_chart)

    def test_a_head_reports_to_the_head_above(self):
        changed = _auto_assign_managers(self.dept_head)
        self.assertIn('reporting_manager', changed)
        self.assertEqual(self.dept_head.reporting_manager, self.ceo)

    def test_works_with_no_branch_at_all(self):
        worker = make_user('chart-nobranch@test.com', employee_id='CHT004', branch='')
        seat(self.dept, 'Executive', worker)
        _auto_assign_managers(worker)
        self.assertEqual(worker.reporting_manager, self.dept_head)

    def test_nobody_when_the_person_has_no_seat(self):
        loner = make_user('chart-loner@test.com', employee_id='CHT005', branch='Kondapur')
        self.assertNotIn('reporting_manager', _auto_assign_managers(loner))
        self.assertIsNone(loner.reporting_manager)

    def test_a_manager_already_set_is_left_alone(self):
        worker = make_user('chart-set@test.com', employee_id='CHT006', branch='Kondapur')
        seat(self.dept, 'Executive', worker)
        worker.reporting_manager = self.ceo
        self.assertNotIn('reporting_manager', _auto_assign_managers(worker))
        self.assertEqual(worker.reporting_manager, self.ceo)


class StoredManagerStaysCurrentTests(TestCase):
    def setUp(self):
        self.dept_a = OrgUnit.objects.create(name='Stay Department A')
        self.dept_b = OrgUnit.objects.create(name='Stay Department B')
        self.head_a = make_user('stay-a@test.com', employee_id='STY001')
        self.head_b = make_user('stay-b@test.com', employee_id='STY002')
        self.chief_a, self.chief_a_placement = seat(self.dept_a, 'Head A', self.head_a, is_chief=True, can_manage_team=True)
        seat(self.dept_b, 'Head B', self.head_b, is_chief=True, can_manage_team=True)
        self.worker = make_user('stay-worker@test.com', employee_id='STY003')
        _position, self.worker_placement = seat(self.dept_a, 'Executive', self.worker)
        sync_employees([self.worker])

    def test_the_first_sync_copies_the_head_from_the_org_chart(self):
        worker = reload(self.worker)
        self.assertEqual(worker.reporting_manager, self.head_a)
        self.assertTrue(worker.reporting_manager_from_org_chart)

    def test_a_new_head_replaces_the_old_one_when_the_org_chart_changes(self):
        new_head = make_user('stay-new@test.com', employee_id='STY004')
        with self.captureOnCommitCallbacks(execute=True):
            self.chief_a_placement.effective_to = TODAY - datetime.timedelta(days=1)
            self.chief_a_placement.save()
            Placement.objects.create(position=self.chief_a, employee=new_head, effective_from=TODAY)
        self.assertEqual(reload(self.worker).reporting_manager, new_head)

    def test_moving_to_another_unit_changes_the_manager(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.worker_placement.effective_to = TODAY - datetime.timedelta(days=1)
            self.worker_placement.save()
            position = Position.objects.create(org_unit=self.dept_b, title='Executive B')
            Placement.objects.create(position=position, employee=self.worker, effective_from=TODAY)
        self.assertEqual(reload(self.worker).reporting_manager, self.head_b)

    def test_leaving_the_org_chart_clears_a_copied_manager(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.worker_placement.effective_to = TODAY - datetime.timedelta(days=1)
            self.worker_placement.save()
        worker = reload(self.worker)
        self.assertIsNone(worker.reporting_manager)
        self.assertFalse(worker.reporting_manager_from_org_chart)

    def test_a_manager_picked_by_hand_is_never_changed(self):
        User.objects.filter(pk=self.worker.pk).update(reporting_manager=self.head_b, reporting_manager_from_org_chart=False)
        new_head = make_user('stay-new2@test.com', employee_id='STY005')
        with self.captureOnCommitCallbacks(execute=True):
            self.chief_a_placement.effective_to = TODAY - datetime.timedelta(days=1)
            self.chief_a_placement.save()
            Placement.objects.create(position=self.chief_a, employee=new_head, effective_from=TODAY)
        self.assertEqual(reload(self.worker).reporting_manager, self.head_b)
        self.assertEqual(resync_all(), [])

    def test_changing_a_units_parent_moves_everyone_below_it(self):
        top = OrgUnit.objects.create(name='Stay Top')
        top_head = make_user('stay-top@test.com', employee_id='STY006')
        seat(top, 'Top Head', top_head, is_chief=True, can_manage_team=True)
        sync_employees([self.head_a])
        self.assertIsNone(reload(self.head_a).reporting_manager)          # Head A's unit is a root: nobody above
        with self.captureOnCommitCallbacks(execute=True):
            self.dept_a.parent = top
            self.dept_a.save()
        self.assertEqual(reload(self.head_a).reporting_manager, top_head)  # now reports to the head above

    def test_dry_run_reports_without_writing(self):
        User.objects.filter(pk=self.worker.pk).update(reporting_manager=None, reporting_manager_from_org_chart=False)
        changes = resync_all(dry_run=True)
        self.assertIn(self.worker.pk, [employee.pk for employee, _old, _new in changes])
        self.assertIsNone(reload(self.worker).reporting_manager)
        resync_all()
        self.assertEqual(reload(self.worker).reporting_manager, self.head_a)
        self.assertEqual(resync_units([self.dept_a.pk]), [])             # nothing left to change
