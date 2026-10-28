"""Branch location: coordinate validation and warnings, the office geofence with corrected coordinates, the
set_branch_location command, and the employee counts shown on Company Codes."""
from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.branch.geo import coordinate_errors, location_warnings
from apps.branch.models import Branch, City, State
from apps.branch.utils import branch_employee_counts

# Hyderabad (Kondapur area) — the real office — and Mumbai, the wrong value from the ticket.
HYD_LAT, HYD_LON = 17.4600, 78.3600
MUMBAI_LAT, MUMBAI_LON = 19.0000, 72.8800


def _login(client, email, password='TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data


def _make_branch(**overrides):
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    fields = dict(
        branch_code='KONT01', branch_name='Kondapur Test Office', address='Plot 14, Cyber Towers, Kondapur',
        state=state, city=city, allowed_radius_meters=150,
    )
    fields.update(overrides)
    return Branch.objects.create(**fields)


class CoordinateRulesTests(TestCase):
    def test_out_of_range_and_null_island_are_errors(self):
        self.assertIn('latitude', coordinate_errors(95, 78))
        self.assertIn('longitude', coordinate_errors(17, 200))
        self.assertIn('latitude', coordinate_errors(0, 0))
        self.assertIn('longitude', coordinate_errors(17.4, None))
        self.assertEqual(coordinate_errors(None, None), {})
        self.assertEqual(coordinate_errors(HYD_LAT, HYD_LON), {})

    def test_mumbai_coordinates_on_a_hyderabad_branch_are_warned_about(self):
        warnings = location_warnings(MUMBAI_LAT, MUMBAI_LON, 'Telangana', 'Hyderabad')
        self.assertTrue(any('outside Telangana' in warning for warning in warnings))
        self.assertTrue(any('km from the centre of Hyderabad' in warning for warning in warnings))

    def test_real_hyderabad_coordinates_give_no_warning(self):
        self.assertEqual(location_warnings(HYD_LAT, HYD_LON, 'Telangana', 'Hyderabad'), [])
        # Kondapur is a locality of Hyderabad.
        self.assertEqual(location_warnings(HYD_LAT, HYD_LON, 'Telangana', 'Kondapur'), [])


class BranchApiValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user(
            'branch-admin@test.com',
            role=make_role('branch_location_admin', permission_codenames=['branches.view', 'branches.create', 'branches.edit', 'settings.edit']),
        )
        self.viewer = make_user('branch-viewer@test.com', role=make_role('branch_location_viewer', permission_codenames=['branches.view']))
        self.branch = _make_branch()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.detail_url = reverse('branch-detail', args=[self.branch.pk])

    def _put(self, **payload):
        # The branch form sends the whole branch, not just the changed fields.
        full = {
            'branch_name': self.branch.branch_name, 'address': self.branch.address,
            'state': self.branch.state_id, 'city': self.branch.city_id,
        }
        full.update(payload)
        return self.client.put(self.detail_url, full, format='json')

    def test_latitude_out_of_range_is_rejected_with_a_clear_message(self):
        resp = self._put(latitude=95, longitude=78.36)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Latitude must be between -90 and 90', resp.data['message'])
        self.branch.refresh_from_db()
        self.assertIsNone(self.branch.latitude)

    def test_longitude_out_of_range_is_rejected(self):
        resp = self._put(latitude=17.46, longitude=300)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Longitude must be between -180 and 180', resp.data['message'])

    def test_only_one_of_latitude_and_longitude_is_rejected(self):
        resp = self._put(latitude=17.46)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('both latitude and longitude', resp.data['message'].lower())

    def test_zero_zero_is_rejected(self):
        self.assertEqual(self._put(latitude=0, longitude=0).status_code, 400)

    def test_radius_outside_the_allowed_range_is_rejected(self):
        for radius in (5, 9000):
            resp = self._put(allowed_radius_meters=radius)
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn('between 10 and 5000 metres', resp.data['message'])

    def test_geofencing_cannot_be_enabled_without_coordinates(self):
        resp = self._put(geofencing_enabled=True)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('Set latitude and longitude', resp.data['message'])

    def test_valid_coordinates_save_without_warnings(self):
        resp = self._put(latitude=HYD_LAT, longitude=HYD_LON, geofencing_enabled=True, allowed_radius_meters=150)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['location_warnings'], [])

    def test_far_away_coordinates_save_but_come_back_with_a_warning(self):
        resp = self._put(latitude=MUMBAI_LAT, longitude=MUMBAI_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['location_warnings'])

    def test_the_geofencing_endpoint_applies_the_same_ranges(self):
        url = reverse('branch-geofencing', args=[self.branch.pk])
        self.assertEqual(self.client.put(url, {'latitude': 95, 'longitude': 78}, format='json').status_code, 422)
        self.assertEqual(self.client.put(url, {'latitude': 0, 'longitude': 0}, format='json').status_code, 422)
        ok = self.client.put(url, {'latitude': MUMBAI_LAT, 'longitude': MUMBAI_LON}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertTrue(ok.data['data']['location_warnings'])

    def test_check_location_endpoint_reports_errors_and_warnings_without_saving(self):
        url = reverse('branch-check-location')
        state, city = self.branch.state_id, self.branch.city_id
        bad = self.client.post(url, {'latitude': 95, 'longitude': 78, 'state': state, 'city': city}, format='json')
        self.assertFalse(bad.data['data']['is_valid'])
        far = self.client.post(url, {'latitude': MUMBAI_LAT, 'longitude': MUMBAI_LON, 'state': state, 'city': city}, format='json')
        self.assertTrue(far.data['data']['is_valid'])
        self.assertTrue(far.data['data']['warnings'])
        fine = self.client.post(url, {'latitude': HYD_LAT, 'longitude': HYD_LON, 'state': state, 'city': city}, format='json')
        self.assertEqual(fine.data['data']['warnings'], [])
        self.branch.refresh_from_db()
        self.assertIsNone(self.branch.latitude)

    def test_check_location_needs_branch_view(self):
        self.client.force_authenticate(user=make_user('no-branch@test.com', role=make_role('no_branch_role')))
        self.assertEqual(self.client.post(reverse('branch-check-location'), {}, format='json').status_code, 403)


class OfficeGeofenceTests(TestCase):
    """A punch from the real office passes once the branch has the right coordinates; the wrong ones reject it."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.branch = _make_branch(
            latitude=Decimal(str(MUMBAI_LAT)), longitude=Decimal(str(MUMBAI_LON)), geofencing_enabled=True,
        )
        make_user('hyd-staff@test.com', role=make_role('hyd_staff'), password='TestPass123!', branch=self.branch.branch_name)
        _login(self.client, 'hyd-staff@test.com')

    def _punch_from_the_office(self):
        return self.client.post(
            reverse('attendance-punch'),
            {'punch_type': 'IN', 'attendance_mode': 'office', 'latitude': HYD_LAT, 'longitude': HYD_LON},
            format='json',
        )

    def test_wrong_coordinates_reject_hyderabad_staff(self):
        resp = self._punch_from_the_office()
        self.assertEqual(resp.status_code, 403)
        self.assertIn('outside your assigned office location', resp.data['message'])

    def test_corrected_coordinates_let_the_same_punch_through(self):
        call_command('set_branch_location', code=self.branch.branch_code, latitude=str(HYD_LAT), longitude=str(HYD_LON), apply=True, stdout=StringIO())
        resp = self._punch_from_the_office()
        self.assertEqual(resp.status_code, 200, resp.data)


class SetBranchLocationCommandTests(TestCase):
    def setUp(self):
        self.branch = _make_branch(latitude=Decimal(str(MUMBAI_LAT)), longitude=Decimal(str(MUMBAI_LON)), geofencing_enabled=True)

    def _run(self, **options):
        out = StringIO()
        call_command('set_branch_location', code=self.branch.branch_code, stdout=out, **options)
        return out.getvalue()

    def test_without_apply_nothing_is_written(self):
        output = self._run(latitude=str(HYD_LAT), longitude=str(HYD_LON))
        self.assertIn('Dry run', output)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.latitude, Decimal(str(MUMBAI_LAT)))

    def test_apply_writes_and_audits(self):
        self._run(latitude=str(HYD_LAT), longitude=str(HYD_LON), radius=200, address='Corrected address, Kondapur', apply=True)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.latitude, Decimal(str(HYD_LAT)))
        self.assertEqual(self.branch.allowed_radius_meters, 200)
        self.assertEqual(self.branch.address, 'Corrected address, Kondapur')
        self.assertTrue(AuditLog.objects.filter(action='branch_location_set_by_command', object_id=str(self.branch.pk)).exists())

    def test_invalid_values_are_refused(self):
        with self.assertRaises(CommandError):
            self._run(latitude='95', longitude='78', apply=True)
        with self.assertRaises(CommandError):
            self._run(latitude='17.4', apply=True)  # latitude without longitude
        with self.assertRaises(CommandError):
            self._run(radius=1, apply=True)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.latitude, Decimal(str(MUMBAI_LAT)))

    def test_geofencing_can_be_switched_off_while_coordinates_are_confirmed(self):
        self._run(disable_geofencing=True, apply=True)
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.geofencing_enabled)


class BranchEmployeeCountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.branch = _make_branch(branch_name='Count Test Office', branch_code='CNT01')
        self.other = _make_branch(branch_name='Other Count Office', branch_code='CNT02')
        self.admin = make_user('count-admin@test.com', role=make_role('count_admin', permission_codenames=['branches.view']))
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_a_new_employee_with_only_the_branch_name_is_linked_and_counted(self):
        employee = make_user('count-a@test.com', employee_id='EMPCNTA', branch='Count Test Office')
        employee.refresh_from_db()
        self.assertEqual(employee.branch_fk_id, self.branch.pk)
        self.assertEqual(branch_employee_counts().get(self.branch.pk), 1)

    def test_an_employee_missing_the_link_is_still_counted_by_name(self):
        employee = make_user('count-b@test.com', employee_id='EMPCNTB', branch='count test office')  # different case
        User.objects.filter(pk=employee.pk).update(branch_fk=None)
        self.assertEqual(branch_employee_counts().get(self.branch.pk), 1)

    def test_an_existing_link_is_never_overridden_by_the_name(self):
        employee = make_user('count-c@test.com', employee_id='EMPCNTC', branch='Count Test Office')
        User.objects.filter(pk=employee.pk).update(branch_fk=self.other)
        employee.refresh_from_db()
        employee.save()
        employee.refresh_from_db()
        self.assertEqual(employee.branch_fk_id, self.other.pk)

    def test_inactive_employees_and_unknown_names_are_not_counted(self):
        gone = make_user('count-d@test.com', employee_id='EMPCNTD', branch='Count Test Office', is_active=False)
        stray = make_user('count-e@test.com', employee_id='EMPCNTE', branch='No Such Office')
        self.assertIsNone(User.objects.get(pk=stray.pk).branch_fk_id)
        self.assertNotIn(self.branch.pk, branch_employee_counts())
        self.assertFalse(gone.is_active)

    def test_the_list_and_distribution_endpoints_show_the_same_counts(self):
        make_user('count-f@test.com', employee_id='EMPCNTF', branch='Count Test Office')
        make_user('count-g@test.com', employee_id='EMPCNTG', branch='Count Test Office')
        make_user('count-h@test.com', employee_id='EMPCNTH', branch='Other Count Office')
        listing = self.client.get(reverse('branch-list-create'), {'page_size': 50})
        by_code = {row['branch_code']: row['employees_count'] for row in listing.data['data']['results']}
        self.assertEqual(by_code['CNT01'], 2)
        self.assertEqual(by_code['CNT02'], 1)
        distribution = self.client.get(reverse('branch-distribution'))
        by_name = {row['branch']: row['employees'] for row in distribution.data['data']}
        self.assertEqual(by_name['Count Test Office'], 2)
        self.assertEqual(by_name['Other Count Office'], 1)
