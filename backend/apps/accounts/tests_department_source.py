"""UAT-041 (department column) / UAT-046 (profile): "department" is the org unit of the seat a person holds, on every screen."""
import datetime

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Placement, Position
from apps.accounts.services_placement import org_unit_name_for, org_unit_names_for
from apps.accounts.views_pincode import fill_state_and_district

TODAY = datetime.date.today()


def _seat(unit, title, employee):
    position = Position.objects.create(org_unit=unit, title=title)
    Placement.objects.create(position=position, employee=employee, effective_from=TODAY - datetime.timedelta(days=3))
    return position


class DepartmentSourceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = OrgUnit.objects.create(name='Zeta Operations')
        self.other_unit = OrgUnit.objects.create(name='Zeta Finance')
        role = make_role('hr_dept_test', permission_codenames=['attendance.view', 'attendance.edit', 'employees.view', 'settings.edit'])
        self.viewer = make_user('hr-dept@test.com', role=role, employee_id='EMPDEPT00')
        # the legacy `department` text is blank for everyone hired onto a Position: exactly the reported situation
        self.ops = make_user('ops@test.com', employee_id='EMPDEPT01', department='')
        self.fin = make_user('fin@test.com', employee_id='EMPDEPT02', department='')
        self.nobody = make_user('seatless@test.com', employee_id='EMPDEPT03', department='Legacy Dept')
        _seat(self.unit, 'Executive', self.ops)
        _seat(self.other_unit, 'Analyst', self.fin)
        self.client = APIClient()
        self.client.force_authenticate(user=self.viewer)

    def test_helpers_use_the_seat_and_fall_back_to_the_legacy_text(self):
        names = org_unit_names_for([self.ops.pk, self.fin.pk, self.nobody.pk])
        self.assertEqual(names, {self.ops.pk: 'Zeta Operations', self.fin.pk: 'Zeta Finance'})
        self.assertEqual(org_unit_name_for(self.ops), 'Zeta Operations')
        self.assertEqual(org_unit_name_for(self.nobody), 'Legacy Dept')

    def test_attendance_list_shows_the_org_unit(self):
        rows = self.client.get(reverse('hr-attendance-list'), {'page_size': 100}).json()['data']['results']
        by_id = {row['employee_id']: row['department'] for row in rows}
        self.assertEqual(by_id['EMPDEPT01'], 'Zeta Operations')
        self.assertEqual(by_id['EMPDEPT02'], 'Zeta Finance')
        self.assertEqual(by_id['EMPDEPT03'], 'Legacy Dept')

    def test_weekly_off_screen_shows_the_same_value(self):
        rows = self.client.get(reverse('weekly-off-assignments-list'), {'page_size': 100}).json()['data']['results']
        by_id = {row['employee_id']: row['department'] for row in rows}
        self.assertEqual(by_id['EMPDEPT01'], 'Zeta Operations')

    def test_profile_api_department_is_the_org_unit(self):
        data = self.client.get(reverse('employee-detail', args=[self.ops.employee_id])).json()['data']
        self.assertEqual(data['department'], 'Zeta Operations')
        self.assertEqual(data['org_unit_name'], 'Zeta Operations')  # what the drawer uses: same value

    def test_department_filter_uses_the_org_unit_name(self):
        rows = self.client.get(reverse('hr-attendance-list'), {'department': 'Zeta Operations', 'page_size': 100}).json()['data']['results']
        self.assertEqual({row['employee_id'] for row in rows}, {'EMPDEPT01'})

    def test_weekly_off_list_does_not_query_per_row(self):
        def queries():
            with CaptureQueriesContext(connection) as captured:
                self.client.get(reverse('weekly-off-assignments-list'), {'page_size': 100})
            return len(captured)

        queries()  # warm caches
        before = queries()
        for index in range(5):
            _seat(self.unit, f'Extra {index}', make_user(f'extra{index}@test.com', employee_id=f'EMPDEPX{index}'))
        self.assertEqual(queries(), before)


class StateAndDistrictFromPincodeTests(TestCase):
    def test_blank_state_and_district_are_derived_from_the_pin(self):
        fields = {'current_pin_code': '500084', 'permanent_pin_code': '500084'}
        fill_state_and_district(fields)
        self.assertEqual(fields['current_state'], 'Telangana')
        self.assertTrue(fields['current_district'])
        self.assertEqual(fields['permanent_state'], 'Telangana')

    def test_what_hr_typed_is_kept_and_unknown_pins_change_nothing(self):
        fields = {'current_pin_code': '500084', 'current_state': 'Kept State', 'permanent_pin_code': '000000'}
        fill_state_and_district(fields)
        self.assertEqual(fields['current_state'], 'Kept State')
        self.assertTrue(fields['current_district'])  # blank one is still filled
        self.assertNotIn('permanent_state', fields)
        fill_state_and_district({})  # no PIN at all: no error
