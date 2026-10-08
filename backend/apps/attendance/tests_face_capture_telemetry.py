"""Tests for the face-capture telemetry endpoint (see views/face_capture_telemetry.py)."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.attendance.models import FaceCaptureTelemetry
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data


class FaceCaptureTelemetryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.employee = make_user('face-telemetry@test.com')
        _login(self.client, 'face-telemetry@test.com')
        self.url = reverse('face-capture-telemetry')

    def _payload(self, **overrides):
        base = {
            'capture_session_id': 'abc-123',
            'purpose': 'verify',
            'outcome': 'captured',
            'duration_ms': 8200,
            'liveness_attempts': 2,
            'quality_failures': 3,
            'auto_resumes': 1,
            'manual_retries': 0,
            'tf_backend': 'webgl',
            'avg_fps': 14.5,
            'details': {'failure_reasons': {'too_dark': 2}, 'blink_seen': 1},
        }
        base.update(overrides)
        return base

    def test_records_session_for_the_authenticated_employee(self):
        resp = self.client.post(self.url, self._payload(), format='json', HTTP_USER_AGENT='UnitTest/1.0')
        self.assertEqual(resp.status_code, 201, resp.data)
        row = FaceCaptureTelemetry.objects.get()
        self.assertEqual(row.employee, self.employee)
        self.assertEqual(row.outcome, 'captured')
        self.assertEqual(row.tf_backend, 'webgl')
        self.assertEqual(row.user_agent, 'UnitTest/1.0')
        self.assertEqual(row.details['failure_reasons'], {'too_dark': 2})

    def test_requires_authentication(self):
        resp = APIClient().post(self.url, self._payload(), format='json')
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(FaceCaptureTelemetry.objects.count(), 0)

    def test_rejects_unknown_outcome(self):
        resp = self.client.post(self.url, self._payload(outcome='hacked'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(FaceCaptureTelemetry.objects.count(), 0)

    def test_rejects_oversized_details(self):
        resp = self.client.post(self.url, self._payload(details={'blob': 'x' * 5000}), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(FaceCaptureTelemetry.objects.count(), 0)

    def test_employee_cannot_spoof_another_employee(self):
        other = make_user('someone-else@test.com')
        resp = self.client.post(self.url, self._payload(employee=str(other.pk)), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(FaceCaptureTelemetry.objects.get().employee, self.employee)
