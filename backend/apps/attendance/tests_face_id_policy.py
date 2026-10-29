"""Face ID ownership (employee / HR in person / employee + HR approval), one consistent instruction per mode, and the
optional audited fallback that lets a new hire clock in from the office before a face ID exists."""
from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

import apps.accounts.tests_hire_wizard as wizard
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmailTemplate
from apps.attendance.models import AttendancePunch, AttendanceRecord, FaceRegistrationRequest
from apps.attendance.services import AttendanceSettingsService
from apps.attendance.services_face_policy import (
    employee_state, fallback_allows, guidance, hire_summary, instruction_for,
)
from apps.attendance.services_face_matching import activate_registration
from apps.branch.models import Branch, City, State

SELF = 'self_service'
HR_ONLY = 'hr_in_person'
APPROVAL = 'self_service_hr_approval'

OFFICE_LAT, OFFICE_LON = 17.4600, 78.3600


def _login(client, email, password='TestPass123!'):
    resp = client.post(reverse('login'), {'email': email, 'password': password}, format='json')
    assert resp.status_code == 200, resp.data


def set_face_rules(mandatory=True, mode=APPROVAL, fallback='none', days=7):
    admin = make_user(f'face-admin-{AttendancePunch.objects.count()}-{mode}@test.com')
    AttendanceSettingsService.partial_update({'face_verification': {
        'is_mandatory': mandatory, 'registration_mode': mode, 'fallback_policy': fallback, 'fallback_days': days,
    }}, admin)
    cache.clear()


def _embedding(value=0.1):
    return [value] * 128


class FaceIdTestBase(TestCase):
    def setUp(self):
        cache.clear()
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        self.branch = Branch.objects.create(
            branch_code='FACE01', branch_name='Face Test Office', address='Test address', state=state, city=city,
            latitude=Decimal(str(OFFICE_LAT)), longitude=Decimal(str(OFFICE_LON)),
            allowed_radius_meters=150, geofencing_enabled=True,
        )
        self.joined = datetime.date.today()
        self.employee = make_user(
            'new-hire@test.com', role=make_role('face_hire'), password='TestPass123!',
            branch='Face Test Office', date_of_joining=self.joined, full_name='New Hire',
        )
        self.client = APIClient()
        _login(self.client, 'new-hire@test.com')

    def _punch(self, **extra):
        payload = {'punch_type': 'IN', 'attendance_mode': 'office', 'latitude': OFFICE_LAT, 'longitude': OFFICE_LON}
        payload.update(extra)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def _status(self):
        return self.client.get(reverse('face-verification-status')).data['data']

    def _register_approved(self):
        request = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=_embedding(), liveness_passed=True,
            status=FaceRegistrationRequest.STATUS_APPROVED,
        )
        activate_registration(request)
        return request


class OneInstructionPerModeTests(FaceIdTestBase):
    def test_each_mode_gives_a_different_but_single_instruction(self):
        messages = {}
        for mode in (SELF, HR_ONLY, APPROVAL):
            set_face_rules(mode=mode)
            messages[mode] = self._status()['message']
        self.assertIn('Register My Face', messages[SELF])
        self.assertIn('immediately', messages[SELF])
        self.assertIn('ask HR', messages[HR_ONLY])
        self.assertNotIn('Register My Face', messages[HR_ONLY])
        self.assertIn('HR will approve', messages[APPROVAL])
        self.assertEqual(len(set(messages.values())), 3)

    def test_the_punch_error_says_exactly_what_the_status_screen_says(self):
        for mode in (SELF, HR_ONLY, APPROVAL):
            set_face_rules(mode=mode)
            punch = self._punch()
            self.assertEqual(punch.status_code, 400, punch.data)
            self.assertEqual(punch.data['message'], self._status()['message'], mode)

    def test_a_pending_request_is_described_the_same_way_everywhere(self):
        set_face_rules(mode=APPROVAL)
        FaceRegistrationRequest.objects.create(employee=self.employee, face_embedding=_embedding(), liveness_passed=True)
        status = self._status()
        self.assertEqual(status['state'], 'pending')
        self.assertIn('waiting for HR approval', status['message'])
        self.assertEqual(self._punch().data['message'], status['message'])
        self.assertFalse(status['can_self_register'])

    def test_only_hr_in_person_stops_employees_from_registering_themselves(self):
        for mode, expected in ((SELF, True), (HR_ONLY, False), (APPROVAL, True)):
            set_face_rules(mode=mode)
            self.assertEqual(self._status()['can_self_register'], expected, mode)

    def test_nothing_is_said_or_required_when_face_id_is_off(self):
        set_face_rules(mandatory=False)
        status = self._status()
        self.assertFalse(status['is_mandatory'])
        self.assertEqual(status['message'], '')
        self.assertEqual(self._punch().status_code, 200)

    def test_the_hr_note_follows_the_mode(self):
        set_face_rules(mode=HR_ONLY)
        self.assertIn('Employees cannot register it themselves', self._status()['hr_note'])
        set_face_rules(mode=SELF)
        self.assertIn('active immediately', self._status()['hr_note'])


class RegistrationByModeTests(FaceIdTestBase):
    def _submit(self):
        return self.client.post(reverse('face-registration-submit'), {
            'face_embedding': _embedding(), 'liveness_passed': True, 'consent_acknowledged': True,
        }, format='json')

    def test_hr_in_person_refuses_self_registration_with_the_same_instruction(self):
        set_face_rules(mode=HR_ONLY)
        resp = self._submit()
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data['message'], self._status()['message'])
        self.assertFalse(FaceRegistrationRequest.objects.exists())

    def test_self_service_is_active_straight_away(self):
        set_face_rules(mode=SELF)
        resp = self._submit()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(employee_state(self.employee), 'approved')
        self.assertTrue(FaceRegistrationRequest.objects.get(employee=self.employee).is_active)

    def test_the_approval_mode_waits_for_hr(self):
        set_face_rules(mode=APPROVAL)
        resp = self._submit()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(employee_state(self.employee), 'pending')


class FallbackTests(FaceIdTestBase):
    def test_without_a_fallback_a_day_one_punch_is_refused(self):
        set_face_rules(fallback='none')
        self.assertEqual(self._punch().status_code, 400)

    def test_until_approved_lets_a_day_one_office_punch_through_flagged_and_audited(self):
        set_face_rules(fallback='until_approved')
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertTrue(punch.face_fallback)
        self.assertFalse(punch.face_verified)
        entry = AuditLog.objects.get(action='punch_without_face_id', object_id=str(punch.pk))
        self.assertEqual(entry.changes['employee_id'], self.employee.employee_id)
        self.assertEqual(entry.changes['face_id_state'], 'not_registered')

    def test_the_status_screen_mentions_the_fallback(self):
        set_face_rules(fallback='until_approved')
        status = self._status()
        self.assertTrue(status['fallback_active'])
        self.assertIn('flagged for HR', status['message'])

    def test_the_fallback_is_still_geofenced(self):
        set_face_rules(fallback='until_approved')
        resp = self._punch(latitude=OFFICE_LAT + 0.5, longitude=OFFICE_LON + 0.5)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(AttendancePunch.objects.exists())

    def test_days_after_joining_covers_a_new_hire_but_not_someone_long_employed(self):
        set_face_rules(fallback='days_after_joining', days=7)
        self.assertTrue(fallback_allows(self.employee))
        self.employee.date_of_joining = datetime.date.today() - datetime.timedelta(days=30)
        self.employee.save(update_fields=['date_of_joining'])
        self.assertFalse(fallback_allows(self.employee))
        self.assertEqual(self._punch().status_code, 400)

    def test_days_after_joining_has_a_last_day(self):
        set_face_rules(fallback='days_after_joining', days=7)
        last_day = self.joined + datetime.timedelta(days=7)
        self.assertTrue(fallback_allows(self.employee, last_day))
        self.assertFalse(fallback_allows(self.employee, last_day + datetime.timedelta(days=1)))
        self.assertEqual(self._status()['fallback_until'], last_day.isoformat())

    def test_a_pending_registration_still_gets_the_fallback_under_until_approved(self):
        set_face_rules(mode=APPROVAL, fallback='until_approved')
        FaceRegistrationRequest.objects.create(employee=self.employee, face_embedding=_embedding(), liveness_passed=True)
        self.assertTrue(fallback_allows(self.employee))
        self.assertEqual(self._punch().status_code, 200)

    def test_an_approved_face_id_ends_the_fallback_and_the_match_is_required_again(self):
        set_face_rules(fallback='until_approved')
        self._register_approved()
        self.assertFalse(fallback_allows(self.employee))
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)  # a face capture is now required
        self.assertFalse(AuditLog.objects.filter(action='punch_without_face_id').exists())

    def test_the_fallback_does_nothing_when_face_id_is_off(self):
        set_face_rules(mandatory=False, fallback='until_approved')
        self.assertFalse(fallback_allows(self.employee))
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(AttendancePunch.objects.get(employee=self.employee).face_fallback)


class SettingsValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user('face-settings@test.com', role=make_role('face_settings_admin', permission_codenames=['settings.view', 'settings.edit']))
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _update(self, face_verification):
        return self.client.patch(reverse('attendance-settings'), {'face_verification': face_verification}, format='json')

    def test_an_unknown_mode_or_policy_is_rejected(self):
        self.assertEqual(self._update({'is_mandatory': True, 'registration_mode': 'whenever'}).status_code, 422)
        self.assertEqual(self._update({'is_mandatory': True, 'fallback_policy': 'forever'}).status_code, 422)

    def test_fallback_days_must_be_between_1_and_90(self):
        self.assertEqual(self._update({'is_mandatory': True, 'fallback_days': 0}).status_code, 422)
        self.assertEqual(self._update({'is_mandatory': True, 'fallback_days': 91}).status_code, 422)

    def test_a_valid_choice_is_saved_and_read_back(self):
        resp = self._update({'is_mandatory': True, 'registration_mode': HR_ONLY, 'fallback_policy': 'days_after_joining', 'fallback_days': 14})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = self.client.get(reverse('attendance-settings')).data['data']['face_verification']
        self.assertEqual((data['registration_mode'], data['fallback_policy'], data['fallback_days']), (HR_ONLY, 'days_after_joining', 14))


class HireCompletionTests(wizard.HireWizardTestCase):
    """The hire completion screen and the onboarding invite email carry the same Face ID instruction."""

    def _hire(self):
        action = self._create_draft()
        self._set_employment_type(action, 'Permanent')
        self._patch(action, self._valid_full_draft())
        self._upload_all_required_docs(action)
        with patch('apps.accounts.utils.send_activation_invite') as send:
            resp = self._complete(action)
        return resp, send

    def _assert_response_and_email_agree(self, mode):
        set_face_rules(mode=mode)
        resp, send = self._hire()
        self.assertEqual(resp.status_code, 201, resp.data)
        face_id = resp.data['data']['face_id']
        self.assertEqual(face_id['registration_mode'], mode)
        self.assertTrue(face_id['employee_message'])
        self.assertTrue(face_id['hr_next_step'])
        self.assertIn(face_id['employee_message'], send.call_args.kwargs['extra_html'])

    def test_response_and_email_agree_for_self_service(self):
        self._assert_response_and_email_agree(SELF)

    def test_response_and_email_agree_for_hr_in_person(self):
        self._assert_response_and_email_agree(HR_ONLY)

    def test_response_and_email_agree_for_self_service_with_approval(self):
        self._assert_response_and_email_agree(APPROVAL)

    def test_hr_is_told_what_to_do_next_in_each_mode(self):
        set_face_rules(mode=HR_ONLY)
        resp, _ = self._hire()
        self.assertIn('in person from the Face ID Registrations page', resp.data['data']['face_id']['hr_next_step'])

    def test_no_face_id_text_when_face_id_is_off(self):
        set_face_rules(mandatory=False)
        resp, send = self._hire()
        self.assertEqual(send.call_args.kwargs['extra_html'], '')
        self.assertFalse(resp.data['data']['face_id']['is_mandatory'])


class WelcomeEmailTemplateTests(TestCase):
    """Migration 0201 adds the Face ID block to the built-in welcome email, and leaves an edited one alone."""

    def _run_migration(self):
        import importlib

        from django.apps import apps

        importlib.import_module('apps.accounts.migrations.0201_welcome_email_face_id_block').add_face_id_block(apps, None)

    def _template(self, body):
        return EmailTemplate.objects.create(
            name='hire_welcome_credentials', display_name='Welcome', template_type='accounts', subject='Hi',
            body=body, available_variables=['employee_name'],
        )

    def test_the_builtin_welcome_email_gets_the_face_id_block(self):
        import importlib

        seeded = importlib.import_module('apps.accounts.migrations.0190_seed_hire_welcome_credentials_template').HIRE_WELCOME_CREDENTIALS_BODY
        template = self._template(seeded)
        self._run_migration()
        template.refresh_from_db()
        self.assertIn('{face_id_block}', template.body)
        self.assertIn('face_id_block', template.available_variables)
        self._run_migration()  # running it again changes nothing
        template.refresh_from_db()
        self.assertEqual(template.body.count('{face_id_block}'), 1)

    def test_an_edited_welcome_email_keeps_its_wording(self):
        template = self._template('<p>Our own welcome text {employee_name}</p>')
        self._run_migration()
        template.refresh_from_db()
        self.assertEqual(template.body, '<p>Our own welcome text {employee_name}</p>')
        self.assertIn('face_id_block', template.available_variables)  # available to add by hand


class PolicyHelperTests(TestCase):
    def test_instruction_wording_never_mixes_the_modes(self):
        set_face_rules(mode=HR_ONLY)
        self.assertNotIn('Profile page', instruction_for('not_registered'))
        set_face_rules(mode=SELF)
        self.assertNotIn('HR will approve', instruction_for('not_registered'))

    def test_hire_summary_names_the_hire(self):
        set_face_rules(mode=APPROVAL)
        person = make_user('summary@test.com', full_name='Asha Rao')
        self.assertIn('Asha Rao', hire_summary(person)['hr_next_step'])
        self.assertEqual(guidance(person)['state'], 'not_registered')


class HrPunchDetailTests(FaceIdTestBase):
    def test_a_fallback_punch_is_flagged_in_the_hr_attendance_detail(self):
        from apps.attendance.services_hr import get_attendance_detail

        set_face_rules(fallback='until_approved')
        self.assertEqual(self._punch().status_code, 200)
        record = AttendanceRecord.objects.get(employee=self.employee, date=datetime.date.today())
        detail = get_attendance_detail(str(record.id), datetime.date.today(), '')
        self.assertIsNotNone(detail)
        self.assertTrue(detail['punches'][0]['face_fallback'])
