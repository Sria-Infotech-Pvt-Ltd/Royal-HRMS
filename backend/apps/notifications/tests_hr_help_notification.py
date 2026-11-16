"""A new HR Help ticket (e.g. a profile correction) notifies the HR side, never the employee who raised it or other employees."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import HRHelpRequest
from apps.notifications.models import Notification


class HrHelpNotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        hr_role = make_role('hr_help_notify_hr', permission_codenames=['hr_help.respond'])
        admin_role = make_role('hr_help_notify_admin', permission_codenames=['settings.edit'])
        self.hr = make_user('hr-notify@test.com', role=hr_role)
        self.admin = make_user('admin-notify@test.com', role=admin_role)
        self.superuser = make_user('super-notify@test.com', is_superuser=True)
        self.employee = make_user('emp-notify@test.com', role=make_role('hr_help_notify_emp', permission_codenames=[]))
        self.other = make_user('other-notify@test.com', role=make_role('hr_help_notify_other', permission_codenames=[]))

    def _raise_ticket(self):
        with self.captureOnCommitCallbacks(execute=True):
            return HRHelpRequest.objects.create(
                submitted_by=self.employee, topic='profile_correction', message='Section: Employment. Field: joining date.',
            )

    def test_hr_side_is_notified_with_a_link_to_the_queue(self):
        self._raise_ticket()
        for person in (self.hr, self.admin, self.superuser):
            note = Notification.objects.get(user=person, notification_type='hr_help_request')
            self.assertEqual((note.module, note.reference_id), ('system', 'hr-help'))
            self.assertIn('Profile correction', note.title)

    def test_the_employee_and_other_staff_are_not_notified(self):
        self._raise_ticket()
        self.assertFalse(Notification.objects.filter(user__in=[self.employee, self.other], notification_type='hr_help_request').exists())

    def test_updating_a_ticket_does_not_notify_again(self):
        ticket = self._raise_ticket()
        before = Notification.objects.filter(notification_type='hr_help_request').count()
        with self.captureOnCommitCallbacks(execute=True):
            ticket.status = 'resolved'
            ticket.save()
        self.assertEqual(Notification.objects.filter(notification_type='hr_help_request').count(), before)
