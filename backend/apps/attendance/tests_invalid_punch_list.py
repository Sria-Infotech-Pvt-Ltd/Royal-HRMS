"""
The Invalid Punches list: it names the employee, and a punch HR has discarded or converted leaves the list.

Before: a row carried no employee at all, so HR could not tell whose punch it was; and the list was rebuilt from the raw punches every
time without looking at the discard / convert record, so a discarded punch came straight back (and kept counting).
"""
import datetime
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests_employee_scope import make_branch
from apps.attendance.models import AttendancePunch, AttendanceRecord
from apps.attendance.services_hr_audit import get_invalid_punch_count, get_invalid_punches
from apps.attendance.services_invalid_punch import convert_invalid_punch, discard_invalid_punch

IST = ZoneInfo('Asia/Kolkata')
TOMORROW = timezone.localdate() + datetime.timedelta(days=1)


def make_punch(employee, kind, hour, minute=0, source='manual'):
    when = datetime.datetime.combine(TOMORROW, datetime.time(hour, minute), tzinfo=IST)
    return AttendancePunch.objects.create(employee=employee, punch_type=kind, punched_at=when, source=source, attendance_mode='office')


class InvalidPunchListTests(TestCase):
    def setUp(self):
        self.hr = make_user('ip-hr@test.com', full_name='HR Person', employee_id='IPH1')
        self.employee = make_user('ip-emp@test.com', full_name='Kondapur Employee', employee_id='IPE1')
        AttendanceRecord.objects.create(employee=self.employee, date=TOMORROW, status='present')

    def rows(self):
        return get_invalid_punches(TOMORROW, '', '')

    def test_a_row_says_whose_punch_it_is(self):
        make_punch(self.employee, 'IN', 13)                      # tomorrow: in the future
        (row,) = self.rows()
        self.assertEqual(row['issue_type'], 'future')
        self.assertEqual(row['employee_name'], 'Kondapur Employee')
        self.assertEqual(row['employee_code'], 'IPE1')
        self.assertEqual(row['source'], 'Manual')                # who or what made it: here HR / admin by hand

    def test_the_name_falls_back_to_the_email_when_there_is_no_full_name(self):
        nameless = make_user('nameless@test.com', full_name='', employee_id='IPE2')
        AttendanceRecord.objects.create(employee=nameless, date=TOMORROW, status='present')
        make_punch(nameless, 'IN', 14)
        names = {row['employee_name'] for row in self.rows()}
        self.assertIn('nameless@test.com', names)

    def test_a_discarded_punch_leaves_the_list_and_the_count(self):
        punch = make_punch(self.employee, 'IN', 13)
        self.assertEqual(get_invalid_punch_count(TOMORROW, '', ''), 1)
        discard_invalid_punch(str(punch.id), 'Duplicate by mistake', self.hr)
        self.assertEqual(self.rows(), [])
        self.assertEqual(get_invalid_punch_count(TOMORROW, '', ''), 0)

    def test_a_converted_punch_leaves_the_list(self):
        punch = make_punch(self.employee, 'IN', 13)
        convert_invalid_punch(str(punch.id), 'IN', '09:00', self.hr)
        self.assertNotIn(str(punch.id), [row['id'] for row in self.rows()])

    def test_a_punch_nobody_acted_on_stays(self):
        keep = make_punch(self.employee, 'IN', 13)
        gone = make_punch(self.employee, 'OUT', 15)
        discard_invalid_punch(str(gone.id), 'Mistake', self.hr)
        self.assertEqual([row['id'] for row in self.rows()], [str(keep.id)])

    def test_a_discarded_punch_no_longer_triggers_the_checks_of_its_neighbours(self):
        # IN 13:00, IN 13:00:30 (a duplicate): discarding the first leaves one punch and no duplicate to report.
        first = make_punch(self.employee, 'IN', 13, 0)
        second = AttendancePunch.objects.create(
            employee=self.employee, punch_type='IN', source='manual', attendance_mode='office',
            punched_at=datetime.datetime.combine(TOMORROW, datetime.time(13, 0, 30), tzinfo=IST),
        )
        before = {row['issue_type'] for row in self.rows()}
        self.assertIn('duplicate', before)
        discard_invalid_punch(str(first.id), 'Duplicate', self.hr)
        after = [row for row in self.rows() if row['id'] == str(second.id)]
        self.assertNotIn('duplicate', {row['issue_type'] for row in after})


class InvalidPunchWithABranchTests(TestCase):
    """AttendancePunch.branch is a branch.Branch (field branch_name, no `name`). A row for a punch that has a branch used to raise
    AttributeError, which turned the whole HR attendance dashboard into a 500 for any day holding such a punch (seen in production)."""

    def setUp(self):
        cache.clear()
        self.branch = make_branch('IPB-HYD', 'Invalid Punch Hyderabad')
        self.employee = make_user('ipb-emp@test.com', full_name='Branch Employee', employee_id='IPB1')
        AttendanceRecord.objects.create(employee=self.employee, date=TOMORROW, status='present')
        self.punch = make_punch(self.employee, 'IN', 13)          # tomorrow: in the future
        AttendancePunch.objects.filter(pk=self.punch.pk).update(branch=self.branch)

    def test_the_row_carries_the_branch_name(self):
        (row,) = get_invalid_punches(TOMORROW, '', '')
        self.assertEqual(row['issue_type'], 'future')
        self.assertEqual(row['branch'], 'Invalid Punch Hyderabad')

    def test_the_row_falls_back_to_the_employees_branch_text_when_the_punch_has_no_branch(self):
        AttendancePunch.objects.filter(pk=self.punch.pk).update(branch=None)
        type(self.employee).objects.filter(pk=self.employee.pk).update(branch='Fallback Branch')
        (row,) = get_invalid_punches(TOMORROW, '', '')
        self.assertEqual(row['branch'], 'Fallback Branch')

    def test_the_hr_dashboard_still_loads_on_a_day_with_such_a_punch(self):
        # HR is limited to their own branch, so the employee has to be in it for their punch to count.
        type(self.employee).objects.filter(pk=self.employee.pk).update(branch='Invalid Punch Hyderabad')
        hr = make_user('ipb-hr@test.com', role=make_role('ipb_hr', permission_codenames=['attendance.view']), branch='Invalid Punch Hyderabad')
        client = APIClient()
        client.force_authenticate(user=hr)
        response = client.get(reverse('hr-attendance-dashboard'), {'date': TOMORROW.isoformat()})
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.assertEqual(response.data['data']['tab_badges']['invalid_punches'], 1)

