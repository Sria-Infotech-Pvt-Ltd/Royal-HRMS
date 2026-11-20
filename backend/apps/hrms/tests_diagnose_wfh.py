"""diagnose_wfh tells, in plain words, why a work-from-home punch is refused."""
from __future__ import annotations

import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.hrms.models import REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING, WorkFromHomeRequest

TODAY = timezone.localdate()


class DiagnoseWfhTests(TestCase):
    def setUp(self):
        self.employee = make_user('diagwfh@test.com', employee_id='EMPDW001', role=make_role('diagwfh_emp'))
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_COMPLETE, account_activated_at=timezone.now(), activation_pending=False)

    def _request(self, status, days_before=0, days_after=1, **extra):
        return WorkFromHomeRequest.objects.create(
            employee=self.employee, start_date=TODAY - datetime.timedelta(days=days_before), end_date=TODAY + datetime.timedelta(days=days_after),
            reason='Internet repair', location_label='Home', latitude=Decimal('17.385044'), longitude=Decimal('78.486671'), status=status, **extra,
        )

    def _run(self, key='EMPDW001'):
        out = StringIO()
        call_command('diagnose_wfh', key, stdout=out)
        return out.getvalue()

    def test_an_approved_request_covering_today_means_wfh_mode_and_names_the_radius(self):
        self._request(REQ_APPROVED)
        text = self._run()
        self.assertIn('Portal access: open', text)
        self.assertIn('WORK-FROM-HOME mode', text)
        self.assertIn('within 200 m', text)

    def test_a_request_still_waiting_for_the_second_level_is_called_out_as_the_reason(self):
        self._request(REQ_L2_PENDING, l1_status='approved')
        text = self._run()
        self.assertIn('WAITING FOR THE SECOND LEVEL', text)
        self.assertIn('NO approved request covers today', text)
        self.assertIn('OFFICE mode', text)

    def test_an_approved_request_for_other_days_does_not_help_today(self):
        self._request(REQ_APPROVED, days_before=10, days_after=-5)
        text = self._run()
        self.assertIn('NO approved request covers today', text)
        self.assertNotIn('(covers today)', text)

    def test_a_request_with_the_location_check_off_says_a_punch_from_anywhere_is_accepted(self):
        self._request(REQ_APPROVED, enforce_location=False)
        self.assertIn('accepted', self._run())

    def test_no_requests_at_all_is_said_plainly(self):
        self.assertIn('Nothing was ever requested under this account', self._run())

    def test_a_blocked_account_is_reported_before_anything_else(self):
        User.objects.filter(pk=self.employee.pk).update(onboarding_status=User.ONBOARDING_PENDING, requires_self_service_onboarding=True)   # the gate applies to people who must finish the self-service onboarding
        self._request(REQ_APPROVED)
        text = self._run()
        self.assertIn('Portal access: BLOCKED', text)

    def test_it_counts_requests_by_status_and_finds_the_person_by_email_too(self):
        self._request(REQ_APPROVED)
        self._request(REQ_PENDING, days_before=40, days_after=-38)
        text = self._run('diagwfh@test.com')
        self.assertIn('work from home: approved 1, pending 1', text)

    def test_an_unknown_employee_is_reported(self):
        with self.assertRaises(CommandError):
            self._run('nobody@test.com')
