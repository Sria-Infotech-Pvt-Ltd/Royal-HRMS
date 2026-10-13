"""
Regression test for LeaveOverviewView's AttributeError: 'LeaveRequest' object
has no attribute 'get_leave_type_display' — leave_type stopped being a
choices= field in Phase 6A (widened to a plain CharField), which silently
broke Django's auto-generated get_FOO_display() here and at several other
call sites (see apps.hrms.models.leave_type_display_label's own docstring).
Caught live via the dev server log, not by an existing test.
"""
from __future__ import annotations

import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tokens import RoleBasedRefreshToken
from apps.hrms.models import LEAVE_CASUAL, REQ_APPROVED, LeaveRequest


def _login_as(client: APIClient, user):
    access = RoleBasedRefreshToken.for_user(user).access_token
    client.cookies['royal_access_token'] = str(access)


class LeaveOverviewViewRegressionTests(TestCase):
    def test_leave_overview_does_not_crash_on_legacy_charfield_leave_type(self):
        role = make_role('leave_overview_test', permission_codenames=['leave.view'])
        user = make_user('leaveoverview@test.com', role=role, branch='Mumbai')
        today = datetime.date.today()
        LeaveRequest.objects.create(
            employee=user, leave_type=LEAVE_CASUAL, duration='full_day',
            start_date=today, end_date=today, total_days=1, status=REQ_APPROVED, reason='Test',
        )

        client = APIClient()
        _login_as(client, user)
        resp = client.get('/api/dashboard/module/leave-overview/')
        # The real assertion is "it returned 200, not a 500 AttributeError" —
        # not over-asserting on the exact response shape beyond that.
        self.assertEqual(resp.status_code, 200, resp.data)
