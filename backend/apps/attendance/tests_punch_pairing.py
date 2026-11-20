"""
One pairing of punches for the live timer and the saved attendance record.

Before: the live card and the saved record each paired punches themselves. After an approved correction added an EARLIER punch-in
next to a late one, the record showed the early time but only counted the hours from the late punch, and the live timer and the
figure shown after punch-out disagreed. Both now use `pair_punches`, and the session carries the record's own figure.
"""
from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.factories import make_user
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_attendance import AttendanceProcessorService, PunchService, break_minutes_from, pair_punches

IN, OUT = AttendancePunch.PUNCH_IN, AttendancePunch.PUNCH_OUT
DAY = dt.date(2026, 11, 20)


def at(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(DAY, dt.time(hour, minute), tzinfo=dt.timezone.utc)


def punch(kind: str, when: dt.datetime):
    return SimpleNamespace(punch_type=kind, punched_at=when)


class PairPunchesTests(SimpleTestCase):
    def test_a_normal_day_is_one_pair(self):
        self.assertEqual(pair_punches([punch(IN, at(9)), punch(OUT, at(18))]), [[at(9), at(18)]])

    def test_still_in_leaves_the_pair_open(self):
        self.assertEqual(pair_punches([punch(IN, at(9))]), [[at(9), None]])

    def test_a_break_makes_two_pairs(self):
        punches = [punch(IN, at(9)), punch(OUT, at(13)), punch(IN, at(14)), punch(OUT, at(18))]
        self.assertEqual(pair_punches(punches), [[at(9), at(13)], [at(14), at(18)]])

    def test_an_earlier_in_added_by_a_correction_wins(self):
        # He came at 09:00 but punched in at 11:38; the approved correction adds 09:00.
        punches = [punch(IN, at(9)), punch(IN, at(11, 38)), punch(OUT, at(18))]
        self.assertEqual(pair_punches(punches), [[at(9), at(18)]])

    def test_an_earlier_in_wins_while_still_working(self):
        self.assertEqual(pair_punches([punch(IN, at(9)), punch(IN, at(11, 38))]), [[at(9), None]])

    def test_a_later_out_added_by_a_correction_extends_the_day(self):
        punches = [punch(IN, at(9)), punch(OUT, at(13)), punch(OUT, at(18))]
        self.assertEqual(pair_punches(punches), [[at(9), at(18)]])

    def test_an_out_that_is_not_later_changes_nothing(self):
        # A lone Out with no In (an import stray) never creates time.
        self.assertEqual(pair_punches([punch(OUT, at(8)), punch(IN, at(9)), punch(OUT, at(18))]), [[at(9), at(18)]])

    def test_no_punches_no_pairs(self):
        self.assertEqual(pair_punches([]), [])


class BreakMinutesTests(SimpleTestCase):
    def test_reads_the_configured_break_or_zero(self):
        self.assertEqual(break_minutes_from(SimpleNamespace(working_hours=SimpleNamespace(break_duration_minutes=60))), 60)
        self.assertEqual(break_minutes_from(None), 0)
        self.assertEqual(break_minutes_from(SimpleNamespace()), 0)


@mock.patch('apps.attendance.services_attendance.AttendanceProcessorService._is_holiday', return_value=False)
class SessionMatchesRecordTests(TestCase):
    """After a correction the live session, the saved record and the times all describe the same day."""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
        cls.employee = make_user('pairing@test.com', employee_id='PAIR001')

    def _punch(self, kind, hour, minute=0, source='web'):
        today = timezone.localdate()
        when = timezone.make_aware(dt.datetime.combine(today, dt.time(hour, minute)))
        AttendancePunch.objects.create(employee=self.employee, punch_type=kind, punched_at=when, source=source, attendance_mode='office')

    def _record(self):
        return AttendanceRecord.objects.get(employee=self.employee, date=timezone.localdate())

    def test_the_session_figure_equals_the_saved_record_for_a_plain_day(self, *_):
        self._punch(IN, 9)
        self._punch(OUT, 18)
        AttendanceProcessorService.process_day(self.employee, timezone.localdate())
        session = PunchService.get_today_session(self.employee)
        self.assertEqual(session['worked_minutes'], self._record().total_working_minutes)
        self.assertEqual(session['total_seconds'], 9 * 3600)
        self.assertEqual(session['total_seconds'] // 60 - session['break_seconds'] // 60, session['worked_minutes'])

    def test_after_an_early_in_correction_the_hours_count_from_the_corrected_start(self, *_):
        self._punch(IN, 11, 38)
        self._punch(OUT, 18)
        self._punch(IN, 9, 0, source='manual')            # the approved correction
        AttendanceProcessorService.process_day(self.employee, timezone.localdate())
        record = self._record()
        session = PunchService.get_today_session(self.employee)
        self.assertEqual(record.first_punch_in, dt.time(9, 0))
        self.assertEqual(session['total_seconds'], 9 * 3600)                       # 09:00 to 18:00, not 11:38 to 18:00
        self.assertEqual(session['worked_minutes'], record.total_working_minutes)  # the number the record holds
        self.assertEqual(record.total_working_minutes + session['break_seconds'] // 60, 9 * 60)

    def test_while_still_in_the_open_session_starts_at_the_corrected_time(self, *_):
        self._punch(IN, 11, 38)
        self._punch(IN, 9, 0, source='manual')
        session = PunchService.get_today_session(self.employee)
        self.assertTrue(session['is_clocked_in'])
        self.assertGreaterEqual(session['session_seconds'], 0)
        self.assertEqual(session['session_seconds'], session['total_seconds'])
