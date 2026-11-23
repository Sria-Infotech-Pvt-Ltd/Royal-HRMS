"""
Bad input gets a clear message, never "An unexpected error occurred", and an empty request never changes data silently.

Found by sending empty and junk bodies to every write route (QA program, 2026-11-23):
  - onboarding family / nominee forms: a list or number where text belongs crashed with AttributeError (500);
  - DELETE /onboarding/step/<n>/ set NOT NULL text columns to NULL (500);
  - PATCH /employees/<id>/reporting-manager/ with no reporting_manager_id cleared the manager and said "updated";
  - workflow task action / withdraw on an id that does not exist raised DoesNotExist (500).
"""
import datetime
import uuid

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import EmployeeProfile, User

TODAY = datetime.date.today()


class InputValidationFixTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager = make_user('iv-manager@test.com', employee_id='IVM001', date_of_joining=TODAY - datetime.timedelta(days=300))
        self.employee = make_user('iv-emp@test.com', employee_id='IVE002', date_of_joining=TODAY - datetime.timedelta(days=100), reporting_manager=self.manager)
        EmployeeProfile.objects.get_or_create(user=self.employee)
        boss = make_user('iv-super@test.com', employee_id='IVS003')
        User.objects.filter(pk=boss.pk).update(is_superuser=True)
        self.employee_client = APIClient(raise_request_exception=False)
        self.employee_client.force_authenticate(user=self.employee)
        self.admin_client = APIClient(raise_request_exception=False)
        self.admin_client.force_authenticate(user=User.objects.get(pk=boss.pk))

    def message(self, response) -> str:
        return str(response.json().get('message', ''))

    # --- family and nominee forms ----------------------------------------------------------------------------------------
    def test_family_member_text_fields_must_be_text(self):
        for body in ({'name': ['a', None]}, {'name': 'Asha', 'relationship': ['Mother']}, {'name': 'Asha', 'gender': 5}, {'name': 'Asha', 'blood_group': {'x': 1}}):
            response = self.employee_client.post('/api/onboarding/family/', body, format='json')
            self.assertEqual(response.status_code, 400, (body, response.status_code))
            self.assertIn('must be text', self.message(response))

    def test_family_member_date_of_birth_must_be_a_real_date(self):
        response = self.employee_client.post('/api/onboarding/family/', {'name': 'Asha', 'date_of_birth': '2026-13-45'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('real date', self.message(response))

    def test_a_valid_family_member_is_still_added(self):
        response = self.employee_client.post('/api/onboarding/family/', {'name': 'Asha', 'relationship': 'spouse', 'date_of_birth': '1992-04-05'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)

    def test_editing_a_family_member_with_a_list_is_also_a_clear_error(self):
        created = self.employee_client.post('/api/onboarding/family/', {'name': 'Asha'}, format='json').json()['data']
        response = self.employee_client.patch(f"/api/onboarding/family/{created['id']}/", {'name': ['x']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be text', self.message(response))

    def test_a_nominee_scheme_must_be_text(self):
        response = self.employee_client.post('/api/onboarding/nominees/', {'family_member': 'abc', 'scheme': ['epf']}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be text', self.message(response))

    # --- clearing an onboarding step -------------------------------------------------------------------------------------
    def test_clearing_a_step_resets_the_fields_instead_of_crashing(self):
        profile = EmployeeProfile.objects.get(user=self.employee)
        profile.highest_qualification = 'B.Tech'
        profile.save()
        response = self.employee_client.delete('/api/onboarding/step/1/')
        self.assertNotEqual(response.status_code, 500, response.content)

    def test_clearing_the_personal_step_empties_the_text_fields(self):
        profile = EmployeeProfile.objects.get(user=self.employee)
        profile.father_name = 'Someone'
        profile.save()
        response = self.employee_client.delete('/api/onboarding/step/0/')
        self.assertEqual(response.status_code, 200, response.content)
        profile.refresh_from_db()
        self.assertEqual(profile.father_name, '')

    # --- reporting manager -----------------------------------------------------------------------------------------------
    def test_an_empty_request_does_not_clear_the_reporting_manager(self):
        response = self.admin_client.patch('/api/employees/IVE002/reporting-manager/', {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('reporting_manager_id', self.message(response))
        self.assertEqual(User.objects.get(pk=self.employee.pk).reporting_manager_id, self.manager.pk)

    def test_sending_null_still_clears_it_on_purpose(self):
        response = self.admin_client.patch('/api/employees/IVE002/reporting-manager/', {'reporting_manager_id': None}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(User.objects.get(pk=self.employee.pk).reporting_manager_id)

    # --- workflow ids that do not exist ----------------------------------------------------------------------------------
    def test_acting_on_or_withdrawing_something_that_does_not_exist_is_a_404(self):
        missing = uuid.uuid4()
        action = self.admin_client.post(f'/api/v1/platform/workflow/tasks/{missing}/action/', {'action': 'approve'}, format='json')
        self.assertEqual(action.status_code, 404, action.content)
        self.assertIn('not found', self.message(action))
        withdraw = self.admin_client.post(f'/api/v1/platform/workflow/instances/{missing}/withdraw/', {}, format='json')
        self.assertEqual(withdraw.status_code, 404, withdraw.content)
        self.assertIn('not found', self.message(withdraw))

    # --- a malformed id in the URL reads as "not found", not Django's own wording ----------------------------------------
    def test_a_malformed_uuid_in_the_url_is_a_plain_not_found(self):
        for method, url in (('delete', '/api/leave/holidays/abc/'), ('delete', '/api/onboarding/assets/abc/'), ('get', '/api/onboarding/approvals/abc/')):
            response = getattr(self.admin_client, method)(url)
            self.assertEqual(response.status_code, 404, (url, response.status_code, response.content))
            message = self.message(response)
            self.assertNotIn('UUID', message)
            self.assertIn('not found', message.lower())

