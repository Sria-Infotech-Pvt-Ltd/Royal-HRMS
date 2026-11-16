"""Shared fixtures for the timesheet service, API and workflow tests (not a test module itself)."""
from __future__ import annotations

import datetime
from contextlib import ExitStack, contextmanager
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.hrms.models import ProjectAssignment

MONDAY = datetime.date(2026, 11, 9)
LAST_MONDAY = MONDAY - datetime.timedelta(days=7)
WEDNESDAY = MONDAY + datetime.timedelta(days=2)       # the pinned "today" unless a test says otherwise
_TODAY_TARGETS = (
    'apps.attendance.services_timesheet_common.today', 'apps.attendance.services_timesheet.today',
    'apps.attendance.services_timesheet_validation.today', 'apps.attendance.services_timesheet_week.today',
)


def day(offset: int, week: datetime.date = MONDAY) -> str:
    return (week + datetime.timedelta(days=offset)).isoformat()


@contextmanager
def pinned_today(value: datetime.date = WEDNESDAY):
    with ExitStack() as stack:
        for target in _TODAY_TARGETS:
            stack.enter_context(mock.patch(target, return_value=value))
        yield


def cell(offset: int, hours, note: str = '', week: datetime.date = MONDAY) -> dict:
    return {'date': day(offset, week), 'hours': hours, 'note': note}


def project_line(assignment_id: int, *entries: dict, billable: bool = False) -> dict:
    return {'assignment_id': assignment_id, 'is_internal': False, 'is_billable': billable, 'entries': list(entries)}


def internal_line(*entries: dict) -> dict:
    return {'assignment_id': None, 'is_internal': True, 'is_billable': False, 'entries': list(entries)}


def assign(employee, assignment_id: int, name: str = 'Alpha', start=datetime.date(2026, 1, 1), end=None, status: str = 'active') -> ProjectAssignment:
    return ProjectAssignment.objects.create(
        assignment_id=assignment_id, employee_code=employee.employee_id, project_id=assignment_id * 10, project_code=f'P{assignment_id}',
        project_name=name, assignment_start_date=start, assignment_end_date=end, assignment_status=status,
    )


def total_of(view: dict) -> Decimal:
    return Decimal(view['totals']['week'])


class TimesheetTestBase(TestCase):
    """A manager, an employee who reports to them, and an HR partner, all in the same branch."""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.hr = make_user('ts_hr@test.com', employee_id='TSH001', branch='TS-Branch')
        cls.manager = make_user('ts_mgr@test.com', employee_id='TSM001', branch='TS-Branch', hr=cls.hr)
        cls.employee = make_user('ts_emp@test.com', employee_id='TSE001', branch='TS-Branch', reporting_manager=cls.manager, hr=cls.hr)

    def setUp(self):
        cache.clear()
