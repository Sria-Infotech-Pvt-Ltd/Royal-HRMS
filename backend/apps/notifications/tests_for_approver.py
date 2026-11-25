"""A notice that asks the person to act as an approver is marked, so the bell can open the approvals screen for it."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.signals import _notify


class ForApproverFlagTests(TestCase):
    def setUp(self):
        self.admin = make_user('notif-admin@test.com', full_name='Admin', employee_id='NA1')
        self.employee = make_user('notif-emp@test.com', full_name='Employee', employee_id='NE1')

    def test_a_notice_in_the_approval_category_is_marked_for_the_approver(self):
        _notify(self.admin, 'New Leave Request', 'Employee asked for leave.', 'leave_applied', 'leave', '1', self.employee, category='approval')
        self.assertTrue(Notification.objects.get(user=self.admin).is_for_approver)

    def test_a_notice_about_your_own_request_is_not(self):
        _notify(self.employee, 'Leave Applied', 'Your leave request was submitted.', 'leave_applied', 'leave', '1', self.employee)
        self.assertFalse(Notification.objects.get(user=self.employee).is_for_approver)

    def test_a_notice_sent_on_purpose_to_an_approver_can_be_marked_without_the_category(self):
        _notify(self.admin, 'Face ID registration awaiting review', 'Please review.', 'face_registration_pending', 'facial_recognition', '9', for_approver=True)
        self.assertTrue(Notification.objects.get(user=self.admin).is_for_approver)

    def test_the_bell_list_carries_the_flag(self):
        _notify(self.admin, 'Regularization Request Pending', 'From Employee.', 'regularization', 'attendance', '3', category='approval')
        _notify(self.admin, 'Holiday', 'Office closed.', 'holiday', 'holiday', '')
        client = APIClient()
        client.force_authenticate(user=User.objects.get(pk=self.admin.pk))
        response = client.get(reverse('notification-list'))
        self.assertEqual(response.status_code, 200)
        rows = {row['title']: row['is_for_approver'] for row in response.data['data']['results']}
        self.assertEqual(rows, {'Regularization Request Pending': True, 'Holiday': False})
