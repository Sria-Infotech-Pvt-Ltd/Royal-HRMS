"""HR Attendance tab: a late punch-in is still a day present, so the Present chip and the Present list include Late people;
the Late chip and Late list keep showing only the late ones."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.accounts.tests_employee_scope import make_branch
from apps.attendance.models import AttendanceRecord
from apps.attendance.services_hr import get_attendance_list, get_dashboard_stats

TODAY = timezone.localdate()


class PresentIncludesLateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('PL-A', 'Present Late Branch').branch_name
        joined = TODAY - datetime.timedelta(days=60)
        cls.rows = {}
        for number, status in enumerate(('present', 'late', 'absent'), start=1):
            user = make_user(f'pl_{status}@test.com', employee_id=f'PL{number:03d}', branch=cls.branch, date_of_joining=joined)
            AttendanceRecord.objects.create(employee=user, date=TODAY, status=status)
            cls.rows[status] = user.employee_id

    def _listed(self, status: str) -> set[str]:
        rows = get_attendance_list({'date': TODAY, 'branch': self.branch, 'status': status})
        return {row['employee_id'] for row in rows}

    def test_present_chip_counts_late_people(self):
        chips = get_dashboard_stats(TODAY, self.branch, '')['summary_chips']
        self.assertEqual(chips['present'], 2)
        self.assertEqual(chips['late'], 1)

    def test_present_list_includes_late_people(self):
        self.assertEqual(self._listed('present'), {self.rows['present'], self.rows['late']})

    def test_late_list_still_only_late_people(self):
        self.assertEqual(self._listed('late'), {self.rows['late']})
