"""diagnose_leave_balance explains a missing leave balance in plain words, and --allocate creates only what is missing."""
from __future__ import annotations

import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.hrms.models import LeaveBalance, LeavePolicy
from apps.hrms.views.leave_shared import new_joiner_skip_reason

TODAY = datetime.date.today()


class DiagnoseLeaveBalanceTests(TestCase):
    def setUp(self):
        LeavePolicy.objects.all().delete()
        self.casual = LeavePolicy.objects.create(leave_type='casual', annual_days=12, is_active=True)
        self.branch_only = LeavePolicy.objects.create(leave_type='earned', annual_days=15, is_active=True, applicable_branches=['Hyderabad'])
        self.employee = make_user('diag-emp@test.com', employee_id='EMPDG001', date_of_joining=TODAY - datetime.timedelta(days=40))
        self.employee.branch = 'Mulugu'
        self.employee.save(update_fields=['branch'])

    def _run(self, *args):
        out = StringIO()
        call_command('diagnose_leave_balance', *args, stdout=out)
        return out.getvalue()

    def test_a_branch_rule_that_does_not_match_is_named_as_the_reason(self):
        reason = new_joiner_skip_reason(self.employee, self.branch_only, '')
        self.assertIn('only for branches', reason)
        self.assertIn('"Mulugu"', reason)
        self.assertIsNone(new_joiner_skip_reason(self.employee, self.casual, ''))

    def test_it_reports_each_policy_without_changing_anything_by_default(self):
        text = self._run('EMPDG001')
        self.assertIn('casual', text)
        self.assertIn('NO balance', text)
        self.assertIn('only for branches', text)
        self.assertIn('Run again with --allocate', text)
        self.assertEqual(LeaveBalance.objects.filter(employee=self.employee).count(), 0)

    def test_allocate_creates_only_the_balances_the_policies_allow(self):
        text = self._run(self.employee.email, '--allocate')
        self.assertIn('Allocated 1 missing balance(s).', text)
        self.assertEqual(list(LeaveBalance.objects.filter(employee=self.employee).values_list('leave_type', flat=True)), ['casual'])

    def test_allocate_never_changes_a_balance_that_already_exists(self):
        LeaveBalance.objects.create(employee=self.employee, leave_type='casual', year=TODAY.year, total_days=7, used_days=2)
        text = self._run('EMPDG001', '--allocate')
        row = LeaveBalance.objects.get(employee=self.employee, leave_type='casual', year=TODAY.year)
        self.assertEqual((row.total_days, row.used_days), (7, 2))
        self.assertIn('5.0 available', text)

    def test_an_unknown_employee_is_reported_clearly(self):
        with self.assertRaises(CommandError):
            self._run('nobody@test.com')
