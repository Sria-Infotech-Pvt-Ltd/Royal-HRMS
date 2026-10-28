"""UAT-032: work location comes from the Company Code (Branch); nothing a person typed earlier is overwritten silently."""
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.accounts.services_work_location import follow_branch_change, work_location_for_branch
from apps.branch.models import Branch, City, State


def _branch(name, code, address):
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(branch_code=code, branch_name=name, address=address, state=state, city=city, allowed_radius_meters=150)


class WorkLocationTests(TestCase):
    def setUp(self):
        cache.clear()
        _branch('Kondapur', 'KDP01', 'Plot 14, Cyber Towers, Kondapur')
        _branch('Mulugu', 'MLG01', 'Main Road, Mulugu')
        role = make_role('hr_work_location_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-wl@test.com', role=role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)

    def _move(self, employee, branch):
        return self.client.patch(reverse('employee-detail', args=[employee.employee_id]), {'branch': branch}, format='json')

    def test_lookup_is_case_insensitive_and_blank_for_unknown(self):
        self.assertEqual(work_location_for_branch('kondapur'), 'Plot 14, Cyber Towers, Kondapur')
        self.assertEqual(work_location_for_branch('Nowhere'), '')
        self.assertEqual(work_location_for_branch(''), '')

    def test_follow_rules(self):
        kondapur = 'Plot 14, Cyber Towers, Kondapur'
        self.assertEqual(follow_branch_change(kondapur, 'Kondapur', 'Mulugu'), 'Main Road, Mulugu')   # was derived: follows
        self.assertEqual(follow_branch_change('', 'Kondapur', 'Mulugu'), 'Main Road, Mulugu')         # blank: filled
        self.assertEqual(follow_branch_change('Corner desk', 'Kondapur', 'Mulugu'), 'Corner desk')   # typed by hand: kept

    def test_moving_an_employee_updates_a_derived_work_location_and_audits_it(self):
        employee = make_user('wl.a@test.com', employee_id='EMPWL001', branch='Kondapur', work_location='Plot 14, Cyber Towers, Kondapur')
        self.assertEqual(self._move(employee, 'Mulugu').status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.work_location, 'Main Road, Mulugu')
        changes = AuditLog.objects.get(action='employee_updated', object_id=str(employee.id)).changes
        self.assertEqual(changes['work_location']['to'], 'Main Road, Mulugu')

    def test_a_hand_entered_work_location_survives_the_move(self):
        employee = make_user('wl.b@test.com', employee_id='EMPWL002', branch='Kondapur', work_location='Corner desk, 3rd floor')
        self.assertEqual(self._move(employee, 'Mulugu').status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.work_location, 'Corner desk, 3rd floor')

    def test_backfill_fills_only_blanks_and_dry_run_changes_nothing(self):
        blank = make_user('wl.c@test.com', employee_id='EMPWL003', branch='Mulugu', work_location='')
        kept = make_user('wl.d@test.com', employee_id='EMPWL004', branch='Mulugu', work_location='Corner desk')
        out = StringIO()
        call_command('backfill_work_location', stdout=out)
        self.assertIn('dry run', out.getvalue())
        blank.refresh_from_db()
        self.assertEqual(blank.work_location, '')
        call_command('backfill_work_location', apply=True, stdout=StringIO())
        blank.refresh_from_db()
        kept.refresh_from_db()
        self.assertEqual(blank.work_location, 'Main Road, Mulugu')
        self.assertEqual(kept.work_location, 'Corner desk')
