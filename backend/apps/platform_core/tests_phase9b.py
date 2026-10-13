"""
Phase 9B Task E — DSR (data subject request) lifecycle: self-service file,
HR-queue fulfilment for access/export, erasure with documented
non-erasable fields, reject, and the permission gate itself.

Scoped-down note (same as every other phase): only the mechanism +
privacy.manage_dsr gate is tested here, not a full byte-for-byte audit
of every PII field across every app.
"""
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.tokens import RoleBasedRefreshToken
from apps.platform_core.models import DataSubjectRequest
from apps.platform_core.services_privacy import (
    DSRAlreadyFulfilledError, create_request, export_user_data,
    fulfil_access_or_export_request, fulfil_erasure_request, reject_request,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}@example.com'


class DataSubjectRequestServiceTests(TestCase):
    def setUp(self):
        self.employee = make_user(_unique('employee'), phone='9999999999')
        self.hr = make_user(_unique('hr'), role=make_role('hr_admin_9b', permission_codenames=['privacy.manage_dsr']))

    def test_export_request_records_evidence_and_does_not_erase(self):
        dsr = create_request(request_type=DataSubjectRequest.TYPE_EXPORT, subject_user=self.employee, requested_by=self.employee)
        fulfil_access_or_export_request(dsr, fulfilled_by=self.hr)
        dsr.refresh_from_db()
        self.assertEqual(dsr.status, DataSubjectRequest.STATUS_FULFILLED)
        self.assertIn('profile', dsr.fulfilment_evidence['exported_keys'])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9999999999')

    def test_erasure_request_scrubs_erasable_fields_and_documents_the_rest(self):
        dsr = create_request(request_type=DataSubjectRequest.TYPE_ERASURE, subject_user=self.employee, requested_by=self.employee)
        fulfil_erasure_request(dsr, fulfilled_by=self.hr)
        dsr.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '')
        self.assertEqual(dsr.fulfilment_evidence['erased_fields'], ['phone'])
        self.assertIn('statutory', dsr.fulfilment_evidence['not_erased_reason'])

    def test_cannot_fulfil_twice(self):
        dsr = create_request(request_type=DataSubjectRequest.TYPE_ACCESS, subject_user=self.employee, requested_by=self.employee)
        fulfil_access_or_export_request(dsr, fulfilled_by=self.hr)
        with self.assertRaises(DSRAlreadyFulfilledError):
            fulfil_access_or_export_request(dsr, fulfilled_by=self.hr)

    def test_reject_records_reason_without_touching_user_data(self):
        dsr = create_request(request_type=DataSubjectRequest.TYPE_ERASURE, subject_user=self.employee, requested_by=self.employee)
        reject_request(dsr, reason='Identity not verified.')
        dsr.refresh_from_db()
        self.assertEqual(dsr.status, DataSubjectRequest.STATUS_REJECTED)
        self.assertEqual(dsr.rejection_reason, 'Identity not verified.')

    def test_export_user_data_reads_profile_fields(self):
        snapshot = export_user_data(self.employee)
        self.assertEqual(snapshot['profile']['email'], self.employee.email)
        self.assertIn('payslips', snapshot)
        self.assertIn('leave_requests', snapshot)
        self.assertIn('expense_claims', snapshot)


def _login_as(client, user):
    access = RoleBasedRefreshToken.for_user(user).access_token
    client.cookies['royal_access_token'] = str(access)


class DataSubjectRequestViewTests(TestCase):
    def setUp(self):
        self.employee = make_user(_unique('employee'))
        self.hr_role = make_role('hr_admin_9b_view', permission_codenames=['privacy.manage_dsr'])
        self.hr = make_user(_unique('hr'), role=self.hr_role)
        self.outsider = make_user(_unique('outsider'))

    def test_employee_can_file_own_request(self):
        _login_as(self.client, self.employee)
        response = self.client.post('/api/v1/platform/privacy/my-requests/', {'request_type': 'access'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(DataSubjectRequest.objects.filter(subject_user=self.employee).count(), 1)

    def test_non_privacy_user_cannot_see_queue(self):
        _login_as(self.client, self.outsider)
        response = self.client.get('/api/v1/platform/privacy/queue/')
        self.assertEqual(response.status_code, 403)

    def test_hr_admin_can_see_and_fulfil_queue(self):
        dsr = create_request(request_type=DataSubjectRequest.TYPE_ACCESS, subject_user=self.employee, requested_by=self.employee)
        _login_as(self.client, self.hr)
        response = self.client.get('/api/v1/platform/privacy/queue/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 1)

        response = self.client.post(f'/api/v1/platform/privacy/requests/{dsr.id}/fulfil/', {}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        dsr.refresh_from_db()
        self.assertEqual(dsr.status, DataSubjectRequest.STATUS_FULFILLED)


class HealthCheckViewTests(TestCase):
    def test_health_check_is_unauthenticated_and_reports_db_ok(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['data']['status'], 'ok')
        self.assertTrue(body['data']['checks']['database']['ok'])
