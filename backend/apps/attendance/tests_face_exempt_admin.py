"""A superuser or System Admin (anyone holding settings.edit) is never asked for a Face ID: not on the status screen, not at
punch time (web or voice), and not in the HR coverage figures. Everyone else, HR and managers included, still is."""
from __future__ import annotations

from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.models import AttendancePunch
from apps.attendance.services_face_policy import EXEMPT_MESSAGE, exempt_q, guidance, is_exempt
from apps.attendance.tests_face_id_policy import (
    OFFICE_LAT, OFFICE_LON, FaceIdTestBase, _login, set_face_rules,
)


class ExemptFromFaceIdTests(FaceIdTestBase):
    def setUp(self):
        super().setUp()
        set_face_rules(mandatory=True, fallback='none')
        self.superuser = make_user(
            'boss@test.com', is_superuser=True, branch='Face Test Office', full_name='Boss', employee_id='SU1',
        )
        self.system_admin = make_user(
            'sysadmin@test.com', role=make_role('face_sysadmin', permission_codenames=['settings.edit']),
            branch='Face Test Office', full_name='System Admin', employee_id='SA1',
        )
        self.hr = make_user(
            'hr-face@test.com', role=make_role('face_hr', permission_codenames=['employees.view', 'facial_recognition.approve']),
            branch='Face Test Office', full_name='HR Person', employee_id='HR1',
        )

    def _punch_as(self, email: str):
        client = APIClient()
        _login(client, email)
        payload = {'punch_type': 'IN', 'attendance_mode': 'office', 'latitude': OFFICE_LAT, 'longitude': OFFICE_LON}
        return client.post(reverse('attendance-punch'), payload, format='json')

    def test_who_is_exempt(self):
        self.assertTrue(is_exempt(self.superuser))
        self.assertTrue(is_exempt(self.system_admin))
        self.assertFalse(is_exempt(self.hr))
        self.assertFalse(is_exempt(self.employee))

    def test_the_status_screen_says_it_is_not_required_for_them_and_still_asks_everyone_else(self):
        for person in (self.superuser, self.system_admin):
            info = guidance(person)
            self.assertFalse(info['is_mandatory'], person.email)
            self.assertTrue(info['is_exempt'])
            self.assertFalse(info['requires_face_to_punch'])
            self.assertEqual(info['message'], EXEMPT_MESSAGE)
        for person in (self.hr, self.employee):
            info = guidance(person)
            self.assertTrue(info['is_mandatory'], person.email)
            self.assertFalse(info['is_exempt'])

    def test_a_superuser_and_a_system_admin_can_punch_with_no_face_id_and_no_fallback(self):
        for email in ('boss@test.com', 'sysadmin@test.com'):
            response = self._punch_as(email)
            self.assertEqual(response.status_code, 200, (email, response.data))
        punch = AttendancePunch.objects.get(employee=self.superuser)
        self.assertFalse(punch.face_fallback)  # not a flagged fallback punch: no face was ever needed

    def test_everyone_else_is_still_refused_without_a_face_id(self):
        self.assertEqual(self._punch_as('hr-face@test.com').status_code, 400)
        self.assertEqual(self._punch_as('new-hire@test.com').status_code, 400)

    def test_the_hr_coverage_figures_leave_the_exempt_people_out(self):
        from apps.accounts.models import User

        counted = User.objects.filter(is_active=True).exclude(exempt_q())
        self.assertFalse(counted.filter(pk__in=[self.superuser.pk, self.system_admin.pk]).exists())
        self.assertTrue(counted.filter(pk__in=[self.hr.pk, self.employee.pk]).count() == 2)
