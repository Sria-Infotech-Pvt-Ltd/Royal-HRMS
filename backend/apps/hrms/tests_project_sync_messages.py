"""A failed pull is shown to admins as one plain sentence, never the raw connection-pool exception text."""
from __future__ import annotations

from unittest import mock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.hrms.models import ProjectSyncLog
from apps.hrms.services_project_sync import (
    ProjectSyncError, _describe_pull_failure, reconcile_all_employees, run_employee_assignments_pull,
)

BASE = 'http://budgeting.test:7000'
RAW_NOISE = "HTTPConnectionPool(host='budgeting.test', port=7000): Max retries exceeded with url: /api/v1/x (Caused by ConnectTimeoutError(<HTTPConnection object at 0x1e426>, 'timed out'))"


def _http_error(code: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = code
    return requests.HTTPError(f'{code} Client Error', response=response)


class DescribePullFailureTests(SimpleTestCase):
    def test_unreachable_server_says_it_is_not_responding(self):
        for exc in (requests.ConnectTimeout(RAW_NOISE), requests.ConnectionError(RAW_NOISE)):
            self.assertIn('not responding', _describe_pull_failure(exc))

    def test_slow_reply_says_taking_too_long(self):
        self.assertIn('taking too long', _describe_pull_failure(requests.ReadTimeout(RAW_NOISE)))

    def test_rejected_key_is_named_as_such(self):
        for code in (401, 403):
            message = _describe_pull_failure(_http_error(code))
            self.assertIn('access key', message)
            self.assertIn(str(code), message)

    def test_other_http_errors_carry_the_code(self):
        self.assertIn('code 500', _describe_pull_failure(_http_error(500)))

    def test_unreadable_reply_is_described_without_the_parser_error(self):
        message = _describe_pull_failure(KeyError('data'))
        self.assertIn('could not understand', message)
        self.assertNotIn('KeyError', message)

    def test_no_message_leaks_the_raw_exception_text(self):
        errors = [requests.ConnectTimeout(RAW_NOISE), requests.ConnectionError(RAW_NOISE), requests.ReadTimeout(RAW_NOISE)]
        for exc in errors:
            message = _describe_pull_failure(exc)
            self.assertNotIn('HTTPConnectionPool', message)
            self.assertNotIn('budgeting.test', message)
            self.assertNotIn('0x1e426', message)
            self.assertLess(len(message), 200)


@override_settings(PROJECT_BUDGET_API_BASE_URL=BASE, PROJECT_BUDGET_API_KEY='test-key')
class StoredFailureMessageTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_scheduled_reconcile_logs_a_short_message(self):
        with mock.patch('apps.hrms.services_project_sync.requests.get', side_effect=requests.ConnectTimeout(RAW_NOISE)):
            with self.assertRaises(ProjectSyncError):
                reconcile_all_employees()
        log = ProjectSyncLog.objects.get(source='reconcile', status=ProjectSyncLog.STATUS_FAILED)
        self.assertIn('not responding', log.message)
        self.assertNotIn('HTTPConnectionPool', log.message)

    def test_fallback_pull_logs_a_short_message(self):
        with mock.patch('apps.hrms.services_project_sync.requests.get', side_effect=requests.ConnectionError(RAW_NOISE)):
            run_employee_assignments_pull('EMP-NOMSG')
        log = ProjectSyncLog.objects.filter(source='pull', employee_code='EMP-NOMSG').first()
        self.assertIsNotNone(log)
        self.assertIn('not responding', log.message)
        self.assertNotIn('HTTPConnectionPool', log.message)
