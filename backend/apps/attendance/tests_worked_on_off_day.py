"""A day HR marked Present (or that someone punched) must show as worked on the employee's own calendar, even on a weekly off or holiday."""
from datetime import date, time

from django.test import SimpleTestCase, TestCase

from apps.accounts.factories import make_user
from apps.attendance.models import AttendanceRecord as R
from apps.attendance.services_attendance import AttendanceDashboardService as Service

TUE, SAT, SUN = date(2026, 11, 3), date(2026, 11, 14), date(2026, 11, 15)
TODAY = date(2026, 11, 18)


def record(employee, day, status='present', **extra):
    return R.objects.create(employee=employee, date=day, status=status, first_punch_in=time(9, 0), last_punch_out=time(18, 0), total_working_minutes=540, **extra)


class CalendarShowsWorkedDaysTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = make_user('worked@test.com', full_name='Worked Emp', employee_id='EMP778', branch='Hyderabad')

    def days(self):
        return Service.get_calendar(self.employee, 2026, 11)['days']

    def test_a_weekday_is_shown_as_marked(self):
        record(self.employee, TUE)
        self.assertEqual(self.days()[3]['status'], 'Present')

    def test_a_saturday_and_a_sunday_marked_present_are_shown_as_present_not_weekly_off(self):
        record(self.employee, SAT)
        record(self.employee, SUN, status='half_day')
        days = self.days()
        self.assertEqual((days[14]['status'], days[14]['clockIn']), ('Present', '09:00'))
        self.assertEqual(days[15]['status'], 'Half Day')

    def test_an_off_day_nobody_worked_is_still_weekly_off(self):
        self.assertEqual(self.days()[14]['status'], 'Weekly Off')
        record(self.employee, SUN, status='weekly_off')
        self.assertEqual(self.days()[15]['status'], 'Weekly Off')

    def test_an_absent_record_on_an_off_day_stays_weekly_off(self):
        R.objects.create(employee=self.employee, date=SAT, status='absent')
        self.assertEqual(self.days()[14]['status'], 'Weekly Off')

    def test_the_monthly_summary_counts_a_worked_off_day_as_present(self):
        before = Service.get_monthly_summary(self.employee, 2026, 11)
        record(self.employee, SAT)
        after = Service.get_monthly_summary(self.employee, 2026, 11)
        self.assertEqual(after['days_present'], before['days_present'] + 1)


class ClassifyPriorityTests(SimpleTestCase):
    def classify(self, status, *, holiday=False, off=False, leave=False):
        rec = R(status=status)
        return Service._classify_day(TUE, rec, {TUE} if holiday else set(), {TUE} if off else set(), {TUE} if leave else set(), TODAY)

    def test_worked_statuses_win_over_holiday_and_weekly_off(self):
        for status in ('present', 'late', 'half_day'):
            self.assertEqual(self.classify(status, holiday=True), status)
            self.assertEqual(self.classify(status, off=True), status)

    def test_other_statuses_keep_their_old_priority(self):
        self.assertEqual(self.classify('absent', holiday=True), 'holiday')
        self.assertEqual(self.classify('absent', off=True), 'weekly_off')
        self.assertEqual(self.classify('incomplete', off=True), 'weekly_off')

    def test_approved_leave_keeps_priority_over_a_worked_record(self):
        self.assertEqual(self.classify('present', leave=True), 'on_leave')
