"""
Clock-in reminder: an email to people who are expected at work today and have not punched in, after the reminder time.

The email goes only to those who really should have punched in: not anyone who already did, nor people on leave, weekly off, a holiday,
nor people who have not joined. Once a day each, never after the shift has ended, and the time and the on/off switch are on the policy.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import EmailTemplate, User
from apps.attendance.models import AttendancePunch, AttendanceRecord, ClockInReminder, MissingPunchNotification, PunchRulesPolicy
from apps.attendance.services_clockin_reminder import send_clock_in_reminders
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, LeaveRequest

IST = ZoneInfo('Asia/Kolkata')
TUESDAY = dt.date(2026, 11, 17)


def at(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(TUESDAY, dt.time(hour, minute), tzinfo=IST)


def employee(email: str, code: str, **fields) -> User:
    person = make_user(email, full_name=f'Person {code}', employee_id=code)
    joined = fields.pop('date_of_joining', dt.date(2025, 1, 1))
    User.objects.filter(pk=person.pk).update(date_of_joining=joined, **fields)
    person.refresh_from_db()
    return person


def leave(person, status=REQ_APPROVED, duration='full_day'):
    return LeaveRequest.objects.create(
        employee=person, leave_type='casual', duration=duration, start_date=TUESDAY, end_date=TUESDAY,
        total_days=Decimal('1.0') if duration == 'full_day' else Decimal('0.5'), reason='Personal work', status=status,
    )


def punch(person, hour=9, minute=40, source='web'):
    return AttendancePunch.objects.create(
        employee=person, punch_type='IN', punched_at=at(hour, minute), source=source, attendance_mode='office',
    )


@mock.patch('apps.attendance.services_attendance._get_settings', return_value=None)
@mock.patch('apps.attendance.services_attendance.AttendanceProcessorService._is_weekly_off', return_value=False)
@mock.patch('apps.attendance.services_attendance.AttendanceProcessorService._is_holiday', return_value=False)
@mock.patch('apps.accounts.utils.send_template_email')
class ClockInReminderTests(TestCase):
    def setUp(self):
        self.person = employee('remind-a@test.com', 'REM001')
        PunchRulesPolicy.objects.filter(is_default=True).update(clock_in_reminder_enabled=True, clock_in_reminder_time=dt.time(10, 0))

    def run_at(self, hour, minute=0):
        return send_clock_in_reminders(now=at(hour, minute))

    def recipients(self, send):
        return [call.kwargs['recipient_email'] for call in send.call_args_list]

    def test_a_person_who_has_not_punched_in_gets_the_reminder_after_the_time(self, send, *_):
        result = self.run_at(10, 5)
        self.assertEqual(result, {'sent': 1, 'reason': 'ok'})
        self.assertEqual(self.recipients(send), ['remind-a@test.com'])
        call = send.call_args.kwargs
        self.assertEqual(call['template_name'], 'attendance_missing_clockin')
        self.assertEqual(call['module'], 'attendance')
        self.assertEqual(call['context']['employee_name'], 'Person REM001')
        self.assertIn('Tuesday', call['context']['date_display'])

    def test_nothing_before_the_reminder_time(self, send, *_):
        self.assertEqual(self.run_at(9, 59)['reason'], 'too_early')
        send.assert_not_called()

    def test_the_time_comes_from_the_policy(self, send, *_):
        PunchRulesPolicy.objects.filter(is_default=True).update(clock_in_reminder_time=dt.time(11, 0))
        self.assertEqual(self.run_at(10, 30)['reason'], 'too_early')
        self.assertEqual(self.run_at(11, 0)['sent'], 1)

    def test_it_can_be_switched_off(self, send, *_):
        PunchRulesPolicy.objects.filter(is_default=True).update(clock_in_reminder_enabled=False)
        self.assertEqual(self.run_at(10, 30), {'sent': 0, 'reason': 'disabled'})
        send.assert_not_called()

    def test_someone_who_already_punched_in_is_not_emailed(self, send, *_):
        punch(self.person)
        self.assertEqual(self.run_at(10, 30)['sent'], 0)
        send.assert_not_called()

    def test_a_day_hr_marked_without_any_punch_or_times_is_not_emailed(self, send, *_):
        for status in ('present', 'late', 'half_day', 'incomplete', 'on_leave', 'weekly_off', 'holiday'):
            AttendanceRecord.objects.filter(employee=self.person).delete()
            AttendanceRecord.objects.create(employee=self.person, date=TUESDAY, status=status)
            self.assertEqual(self.run_at(10, 30)['sent'], 0, status)
        send.assert_not_called()

    def test_marking_someone_absent_does_not_stop_the_reminder(self, send, *_):
        AttendanceRecord.objects.create(employee=self.person, date=TUESDAY, status='absent')
        self.assertEqual(self.run_at(10, 30)['sent'], 1)

    def test_a_record_for_another_day_does_not_count(self, send, *_):
        AttendanceRecord.objects.create(employee=self.person, date=TUESDAY - dt.timedelta(days=1), status='present')
        self.assertEqual(self.run_at(10, 30)['sent'], 1)

    def test_a_punch_entered_by_hr_counts_too(self, send, *_):
        punch(self.person, source='manual')
        self.assertEqual(self.run_at(10, 30)['sent'], 0)

    def test_people_on_approved_leave_are_not_emailed(self, send, *_):
        leave(self.person)
        self.assertEqual(self.run_at(10, 30)['sent'], 0)
        send.assert_not_called()

    def test_a_morning_half_day_of_leave_is_not_emailed_but_an_afternoon_one_is(self, send, *_):
        morning = employee('remind-m@test.com', 'REM002')
        leave(morning, duration='half_morning')
        afternoon = employee('remind-p@test.com', 'REM003')
        leave(afternoon, duration='half_afternoon')
        self.run_at(10, 30)
        recipients = self.recipients(send)
        self.assertNotIn('remind-m@test.com', recipients)
        self.assertIn('remind-p@test.com', recipients)

    def test_leave_that_is_not_approved_yet_still_gets_the_reminder(self, send, *_):
        leave(self.person, status=REQ_PENDING)
        self.assertEqual(self.run_at(10, 30)['sent'], 1)

    def test_weekly_offs_and_holidays_are_skipped(self, send, is_holiday, is_weekly_off, *_):
        is_weekly_off.return_value = True
        self.assertEqual(self.run_at(10, 30)['sent'], 0)
        is_weekly_off.return_value = False
        is_holiday.return_value = True
        self.assertEqual(self.run_at(10, 30)['sent'], 0)
        send.assert_not_called()

    def test_each_person_is_emailed_once_a_day(self, send, *_):
        self.assertEqual(self.run_at(10, 5)['sent'], 1)
        self.assertEqual(self.run_at(10, 10)['sent'], 0)
        self.assertEqual(self.run_at(10, 15)['sent'], 0)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(ClockInReminder.objects.filter(employee=self.person, date=TUESDAY).count(), 1)

    def test_it_stops_for_a_person_once_they_punch_in(self, send, *_):
        self.run_at(10, 5)
        punch(self.person, 10, 7)
        another = employee('remind-b@test.com', 'REM004')
        self.run_at(10, 10)
        self.assertEqual(self.recipients(send), ['remind-a@test.com', 'remind-b@test.com'])
        self.assertTrue(ClockInReminder.objects.filter(employee=another).exists())

    def test_nothing_goes_out_after_the_shift_has_ended(self, send, *_):
        self.assertEqual(self.run_at(18, 30)['reason'], 'shift_over')
        send.assert_not_called()

    def test_people_who_have_not_joined_or_have_no_employee_id_are_skipped(self, send, *_):
        employee('remind-future@test.com', 'REM005', date_of_joining=dt.date(2026, 12, 1))
        employee('remind-noid@test.com', 'REM006', employee_id='')
        self.run_at(10, 30)
        self.assertEqual(self.recipients(send), ['remind-a@test.com'])

    def test_a_failed_email_does_not_stop_the_others_and_is_not_retried_in_a_loop(self, send, *_):
        employee('remind-c@test.com', 'REM007')
        send.side_effect = [RuntimeError('SMTP down'), None]
        result = self.run_at(10, 30)
        self.assertEqual(result['sent'], 1)                          # one failed, one delivered
        self.assertEqual(ClockInReminder.objects.filter(date=TUESDAY).count(), 2)
        self.run_at(10, 35)
        self.assertEqual(send.call_count, 2)                         # the failed one is not hammered every 5 minutes

    def test_the_morning_reminder_does_not_block_the_clock_out_reminder(self, send, *_):
        self.run_at(10, 30)
        MissingPunchNotification.objects.create(employee=self.person, date=TUESDAY, channel='email')   # evening reminder, same day
        self.assertEqual(MissingPunchNotification.objects.filter(employee=self.person, date=TUESDAY).count(), 1)


class SeedAndDefaultsTests(TestCase):
    def test_the_email_template_is_seeded(self):
        template = EmailTemplate.objects.get(name='attendance_missing_clockin')
        self.assertTrue(template.is_active)
        self.assertIn('{employee_name}', template.body)

    def test_the_default_policy_reminds_at_ten(self):
        policy = PunchRulesPolicy.objects.get(is_default=True, is_active=True)
        self.assertTrue(policy.clock_in_reminder_enabled)
        self.assertEqual(policy.clock_in_reminder_time, dt.time(10, 0))
