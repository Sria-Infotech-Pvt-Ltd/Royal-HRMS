"""
Long-leave notice (company policy section 9): a leave of long_leave_min_days
or more must be applied long_leave_notice_days in advance. Off by default;
the per-type minimum notice period is unchanged.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.hrms.models import LeavePolicy
from apps.hrms.views.leave import _validate_leave_policy

TODAY = date(2026, 10, 1)
EMP = SimpleNamespace(branch='', department='', gender='', designation='', employment_type='')


def _check(policy, days_ahead, total_days):
    start = TODAY + timedelta(days=days_ahead)
    return _validate_leave_policy(policy, EMP, 'full_day', total_days, start, start + timedelta(days=int(total_days) - 1),
                                  None, TODAY)


class LongLeaveNoticeTests(SimpleTestCase):
    def policy(self, **rules):
        return LeavePolicy(leave_type='casual', annual_days=12, **rules)

    def test_off_by_default(self):
        self.assertIsNone(_check(self.policy(), 1, 10))

    def test_long_leave_needs_notice(self):
        p = self.policy(long_leave_min_days=5, long_leave_notice_days=15)
        msg = _check(p, 14, 5)
        self.assertIn('5 or more days', msg)
        self.assertIn('15 days in advance', msg)
        self.assertIsNone(_check(p, 15, 5))          # exactly 15 days ahead is enough

    def test_short_leave_not_affected(self):
        p = self.policy(long_leave_min_days=5, long_leave_notice_days=15)
        self.assertIsNone(_check(p, 1, 4))

    def test_either_value_zero_disables_rule(self):
        self.assertIsNone(_check(self.policy(long_leave_min_days=5, long_leave_notice_days=0), 1, 10))
        self.assertIsNone(_check(self.policy(long_leave_min_days=0, long_leave_notice_days=15), 1, 10))

    def test_per_type_notice_still_applies(self):
        p = self.policy(minimum_notice_period=3, long_leave_min_days=5, long_leave_notice_days=15)
        self.assertIn('3 day(s) advance notice', _check(p, 2, 1))
