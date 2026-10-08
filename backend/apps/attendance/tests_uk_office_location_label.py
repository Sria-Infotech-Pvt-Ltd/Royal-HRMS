"""
UK Shift location display refinement: "Office – <Branch Name>" when the
employee's own GPS places them inside their branch's geofence, the actual
reverse-geocoded place name otherwise — without ever REJECTING a UK Shift
punch on distance (that bypass already existed; this only changes what the
punch's location_label ends up showing).

Office-vs-outside is now genuinely computed for UK Shift (via the exact same
_match_branch_within_radius() helper _validate_office uses for real
enforcement — see services_geofencing.py), purely for this display decision;
is_allowed is never affected by the result.

The office shortcut is deliberately scoped to UK Shift only — SGT/ICT and
the global default must keep getting a real reverse-geocoded label even when
punching from inside their own office, exactly as before this change.
"""
from __future__ import annotations

from datetime import time
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch, EmployeeShiftAssignment, WorkingHoursPolicy
from apps.attendance.tasks import reverse_geocode_punch_task
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE

OFFICE_LAT = 17.385044
OFFICE_LON = 78.486671
FAR_LAT = 17.529730
FAR_LON = 78.618416


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _punch(client: APIClient, punch_type: str, lat=None, lon=None):
    payload = {'punch_type': punch_type, 'attendance_mode': 'office'}
    if lat is not None:
        payload['latitude'] = lat
    if lon is not None:
        payload['longitude'] = lon
    return client.post(reverse('attendance-punch'), payload, format='json')


def _make_branch(code: str, name: str, geofencing_enabled: bool = True):
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=code, branch_name=name, address='Test Address',
        state=state, city=city,
        latitude=OFFICE_LAT, longitude=OFFICE_LON,
        allowed_radius_meters=150, geofencing_enabled=geofencing_enabled,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Geofence result — is_inside_geofence now genuinely computed for UK Shift
# ══════════════════════════════════════════════════════════════════════════════

class UKShiftOfficeDetectionGeofenceResultTests(TestCase):
    def setUp(self):
        cache.clear()
        self.branch = _make_branch('UKOFF01', 'UK Office Detection Branch')
        self.uk_policy = WorkingHoursPolicy.objects.get(policy_code='WH-UK')
        role = make_role('employee_uk_office_detect_test')
        self.uk_emp = make_user(
            'ukofficedetect@test.com', role=role, password='TestPass123!',
            employee_id='EMPUOD001', branch='UK Office Detection Branch',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )

    def test_uk_inside_geofence_is_marked_inside_not_none(self):
        client = APIClient()
        _login(client, 'ukofficedetect@test.com')
        resp = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertTrue(punch.is_inside_geofence)
        self.assertIsNotNone(punch.calculated_distance)
        self.assertEqual(punch.branch_id, self.branch.id)

    def test_uk_outside_geofence_is_marked_outside_but_still_allowed(self):
        client = APIClient()
        _login(client, 'ukofficedetect@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)  # never rejected
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertFalse(punch.is_inside_geofence)
        self.assertIsNone(punch.calculated_distance)

    def test_uk_with_no_geofenced_branch_is_not_evaluated(self):
        no_perm_role = make_role('employee_uk_no_branch_test')
        emp = make_user(
            'uknobranch@test.com', role=no_perm_role, password='TestPass123!',
            employee_id='EMPUNB001',  # no branch set at all
        )
        EmployeeShiftAssignment.objects.create(
            employee=emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )
        client = APIClient()
        _login(client, 'uknobranch@test.com')
        resp = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=emp, punch_type='IN')
        self.assertIsNone(punch.is_inside_geofence)


# ══════════════════════════════════════════════════════════════════════════════
#  reverse_geocode_punch_task — office shortcut, scoped to UK Shift only
# ══════════════════════════════════════════════════════════════════════════════

class ReverseGeocodeOfficeShortcutTaskTests(TestCase):
    def setUp(self):
        cache.clear()
        self.branch = _make_branch('UKOFF02', 'Office Shortcut Branch')
        self.uk_policy = WorkingHoursPolicy.objects.get(policy_code='WH-UK')
        self.sgt_policy = WorkingHoursPolicy.objects.get(policy_code='WH-SGT-ICT')
        role = make_role('employee_office_shortcut_task_test')
        self.uk_emp = make_user(
            'ukshortcut@test.com', role=role, password='TestPass123!',
            employee_id='EMPOST001', branch='Office Shortcut Branch',
        )
        self.sgt_emp = make_user(
            'sgtshortcut@test.com', role=role, password='TestPass123!',
            employee_id='EMPOST002', branch='Office Shortcut Branch',
        )
        self.default_emp = make_user(
            'defaultshortcut@test.com', role=role, password='TestPass123!',
            employee_id='EMPOST003', branch='Office Shortcut Branch',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.sgt_emp, policy=self.sgt_policy, effective_from=timezone.localdate(),
        )

    _USE_DEFAULT_BRANCH = object()

    def _make_punch(self, employee, is_inside, branch=_USE_DEFAULT_BRANCH):
        return AttendancePunch.objects.create(
            employee=employee, punch_type=AttendancePunch.PUNCH_IN, punched_at=timezone.now(),
            latitude=OFFICE_LAT, longitude=OFFICE_LON,
            is_inside_geofence=is_inside,
            branch=self.branch if branch is self._USE_DEFAULT_BRANCH else branch,
        )

    # UK inside -> office label, reverse_geocode is NOT called.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_uk_inside_geofence_gets_office_label_without_geocoding(self, mock_geocode):
        punch = self._make_punch(self.uk_emp, is_inside=True)
        reverse_geocode_punch_task(connection.schema_name, str(punch.id))
        punch.refresh_from_db()
        self.assertEqual(punch.location_label, 'Office – Office Shortcut Branch')
        mock_geocode.assert_not_called()

    # UK outside -> reverse_geocode IS called.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_uk_outside_geofence_calls_reverse_geocode(self, mock_geocode):
        mock_geocode.return_value = 'London, England, United Kingdom'
        punch = self._make_punch(self.uk_emp, is_inside=False)
        reverse_geocode_punch_task(connection.schema_name, str(punch.id))
        punch.refresh_from_db()
        mock_geocode.assert_called_once()
        self.assertEqual(punch.location_label, 'London, England, United Kingdom')

    # UK with no branch match (is_inside_geofence None) -> reverse_geocode IS called.
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_uk_no_branch_match_calls_reverse_geocode(self, mock_geocode):
        mock_geocode.return_value = 'Somewhere, Else, Country'
        punch = self._make_punch(self.uk_emp, is_inside=None, branch=None)
        reverse_geocode_punch_task(connection.schema_name, str(punch.id))
        punch.refresh_from_db()
        mock_geocode.assert_called_once()
        self.assertEqual(punch.location_label, 'Somewhere, Else, Country')

    # SGT/ICT inside their own office (is_inside_geofence True, as it always
    # was before this change) -> reverse_geocode behavior UNCHANGED (still called).
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_sgt_ict_inside_geofence_still_calls_reverse_geocode(self, mock_geocode):
        mock_geocode.return_value = 'Hyderabad, Telangana, India'
        punch = self._make_punch(self.sgt_emp, is_inside=True)
        reverse_geocode_punch_task(connection.schema_name, str(punch.id))
        punch.refresh_from_db()
        mock_geocode.assert_called_once()
        self.assertEqual(punch.location_label, 'Hyderabad, Telangana, India')

    # Default/unassigned employee inside their own office -> unchanged (still called).
    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_default_shift_employee_inside_geofence_still_calls_reverse_geocode(self, mock_geocode):
        mock_geocode.return_value = 'Hyderabad, Telangana, India'
        punch = self._make_punch(self.default_emp, is_inside=True)
        reverse_geocode_punch_task(connection.schema_name, str(punch.id))
        punch.refresh_from_db()
        mock_geocode.assert_called_once()
        self.assertEqual(punch.location_label, 'Hyderabad, Telangana, India')


# ══════════════════════════════════════════════════════════════════════════════
#  End-to-end: real punch -> on_commit -> task -> correct label per scenario
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class UKOfficeLabelIntegrationTests(TransactionTestCase):
    # TransactionTestCase truncates every table after each test method,
    # including the WH-UK/WH-SGT-ICT rows seeded by
    # migrations.0045_seed_sgt_ict_and_uk_shifts. serialized_rollback does
    # NOT help here: this project's TenantAwareTestRunner provisions the
    # tenant schema (and runs its migrations — see config/test_runner.py)
    # AFTER Django's own setup_databases() already took its
    # serialized_rollback snapshot, so that snapshot never contains any
    # tenant-schema data to begin with. get_or_create in setUp() below is
    # the robust fix — it doesn't care whether the row survived truncation.
    def setUp(self):
        cache.clear()
        self.branch = _make_branch('UKOFF03', 'Integration Office Branch')
        self.uk_policy, _ = WorkingHoursPolicy.objects.get_or_create(
            policy_code='WH-UK',
            defaults={
                'name': 'UK Shift', 'start_time': time(12, 0), 'end_time': time(21, 0),
                'break_duration': 30, 'grace_period': 15,
                'minimum_working_hours': '4.00', 'maximum_working_hours': '9.00',
            },
        )
        role = make_role('employee_uk_office_integration_test')
        self.uk_emp = make_user(
            'ukofficeintegration@test.com', role=role, password='TestPass123!',
            employee_id='EMPOI001', branch='Integration Office Branch',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.uk_emp, policy=self.uk_policy, effective_from=timezone.localdate(),
        )

    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_real_punch_from_office_gets_office_label_end_to_end(self, mock_geocode):
        client = APIClient()
        _login(client, 'ukofficeintegration@test.com')
        resp = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertEqual(punch.location_label, 'Office – Integration Office Branch')
        mock_geocode.assert_not_called()

    @patch('apps.attendance.services_geocoding.reverse_geocode')
    def test_real_punch_from_elsewhere_gets_reverse_geocoded_label_end_to_end(self, mock_geocode):
        mock_geocode.return_value = 'London, England, United Kingdom'
        client = APIClient()
        _login(client, 'ukofficeintegration@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.uk_emp, punch_type='IN')
        self.assertEqual(punch.location_label, 'London, England, United Kingdom')
        mock_geocode.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
#  Existing non-UK geofence rejection behavior — unchanged
# ══════════════════════════════════════════════════════════════════════════════

class NonUKGeofenceRejectionUnchangedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.branch = _make_branch('UKOFF04', 'Non-UK Rejection Branch')
        self.sgt_policy = WorkingHoursPolicy.objects.get(policy_code='WH-SGT-ICT')
        role = make_role('employee_nonuk_rejection_test')
        self.sgt_emp = make_user(
            'sgtrejection@test.com', role=role, password='TestPass123!',
            employee_id='EMPNUR001', branch='Non-UK Rejection Branch',
        )
        self.default_emp = make_user(
            'defaultrejection@test.com', role=role, password='TestPass123!',
            employee_id='EMPNUR002', branch='Non-UK Rejection Branch',
        )
        EmployeeShiftAssignment.objects.create(
            employee=self.sgt_emp, policy=self.sgt_policy, effective_from=timezone.localdate(),
        )

    def test_sgt_ict_outside_geofence_still_rejected(self):
        client = APIClient()
        _login(client, 'sgtrejection@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('outside your assigned office location', resp.data['message'])

    def test_default_shift_outside_geofence_still_rejected(self):
        client = APIClient()
        _login(client, 'defaultrejection@test.com')
        resp = _punch(client, 'IN', FAR_LAT, FAR_LON)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('outside your assigned office location', resp.data['message'])

    def test_default_shift_inside_geofence_still_allowed(self):
        client = APIClient()
        _login(client, 'defaultrejection@test.com')
        resp = _punch(client, 'IN', OFFICE_LAT, OFFICE_LON)
        self.assertEqual(resp.status_code, 200, resp.data)
