"""Attendance top strip: Present (everyone who came in), Work from home, Late (full-day and short), Absent, On leave."""
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


class FiveCardsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.branch = make_branch('FC-A', 'Five Cards Branch').branch_name
        joined = TODAY - datetime.timedelta(days=60)
        days = {
            'on_time':    dict(status='present'),
            'late_full':  dict(status='present', is_late=True),              # late login: arrived late, worked the full day
            'late_short': dict(status='late', is_late=True),
            'wfh_late':   dict(status='present', is_late=True, work_mode='wfh'),
            'half':       dict(status='half_day'),
            'working':    dict(status='incomplete'),
            'leave':      dict(status='on_leave'),
            'wfh_absent': dict(status='absent', work_mode='wfh'),            # not counted: never came in
        }
        cls.rows = {}
        for number, (key, fields) in enumerate(days.items(), start=1):
            user = make_user(f'fc_{key}@test.com', employee_id=f'FC{number:03d}', branch=cls.branch, date_of_joining=joined)
            AttendanceRecord.objects.create(employee=user, date=TODAY, **fields)
            cls.rows[key] = user.employee_id

    def cards(self):
        return get_dashboard_stats(TODAY, self.branch, '')['stat_cards']

    def listed(self, status):
        return {row['employee_id'] for row in get_attendance_list({'date': TODAY, 'branch': self.branch, 'status': status})}

    def test_present_counts_everyone_who_came_in(self):
        self.assertEqual(self.cards()['present_today'], 6)   # on time, late full, late short, wfh, half day, still working

    def test_wfh_counts_only_people_who_came_in(self):
        self.assertEqual(self.cards()['wfh'], 1)

    def test_late_is_split_into_full_day_and_short(self):
        cards = self.cards()
        self.assertEqual((cards['late_full_day'], cards['late_short'], cards['late_arrivals']), (2, 1, 3))

    def test_lists_match_the_cards(self):
        rows = self.rows
        self.assertEqual(self.listed('present'), {rows[key] for key in ('on_time', 'late_full', 'late_short', 'wfh_late', 'half', 'working')})
        self.assertEqual(self.listed('late'), {rows['late_full'], rows['late_short'], rows['wfh_late']})
        self.assertEqual(self.listed('wfh'), {rows['wfh_late']})

    def test_chips_agree_with_the_cards(self):
        chips = get_dashboard_stats(TODAY, self.branch, '')['summary_chips']
        self.assertEqual((chips['present'], chips['late'], chips['wfh']), (6, 3, 1))
