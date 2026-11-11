"""
Phase 2 notifications:
- Absence alerts also reach the employee, once per absence episode (not daily).
- Category preferences apply to email as well as in-app.
- Approval notifications are mandatory (in-app, email, settings API).
"""
from __future__ import annotations

import datetime
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.tests import _login
from apps.attendance.models import AttendanceRecord
from apps.attendance.services_absence import _absence_episode, detect_absence_alerts
from apps.notifications.models import Notification, NotificationSettings
from apps.notifications.signals import _notify, _send_lifecycle_email, email_category

TODAY = datetime.date(2026, 11, 11)          # a Wednesday


class AbsenceEpisodeTests(TestCase):
    def setUp(self):
        cache.clear()
        role = make_role('p2_staff')
        self.mgr = make_user('p2.mgr@test.com', role=make_role('p2_mgr', can_manage_team=True), full_name='Mgr')
        self.hr = make_user('p2.hr@test.com', role=role, full_name='HR')
        self.emp = make_user('p2.emp@test.com', role=role, full_name='Absent Emp', employee_id='P2E',
                             reporting_manager=self.mgr, hr=self.hr, onboarding_status='complete',
                             date_of_joining=datetime.date(2026, 1, 1))
        cfg = mock.Mock(is_enabled=True, alert_after_days=3, notify_whom='manager_and_hr')
        patcher = mock.patch('apps.attendance.services_absence._get_config', return_value=cfg)
        patcher.start()
        self.addCleanup(patcher.stop)
        no_offs = mock.patch('apps.attendance.services_absence._get_weekly_off_days',
                             side_effect=lambda e, s, en: __import__('collections').defaultdict(set))
        no_offs.start()
        self.addCleanup(no_offs.stop)

    def present(self, day):
        AttendanceRecord.objects.update_or_create(employee=self.emp, date=day, defaults={'status': 'present'})

    def run_on(self, day):
        with mock.patch('apps.attendance.services_absence.timezone.localdate', return_value=day):
            detect_absence_alerts()

    def titles(self, user):
        return list(Notification.objects.filter(user=user).values_list('title', flat=True))

    def test_employee_manager_and_hr_alerted_once_per_episode(self):
        self.present(TODAY - datetime.timedelta(days=5))     # streak starts the day after
        self.run_on(TODAY - datetime.timedelta(days=1))       # 3 absent days -> alert
        self.assertEqual(self.titles(self.emp), ['You Were Marked Absent'])
        self.assertEqual(self.titles(self.mgr), ['Absence Alert'])
        self.assertEqual(self.titles(self.hr), ['Absence Alert'])
        self.run_on(TODAY)                                    # same episode continues: no repeat
        self.run_on(TODAY + datetime.timedelta(days=1))
        self.assertEqual(Notification.objects.count(), 3)

    def test_new_episode_alerts_again(self):
        self.present(TODAY - datetime.timedelta(days=10))
        self.run_on(TODAY - datetime.timedelta(days=6))
        self.assertEqual(Notification.objects.filter(user=self.mgr).count(), 1)
        self.present(TODAY - datetime.timedelta(days=5))     # came back -> episode ends
        self.run_on(TODAY - datetime.timedelta(days=1))       # absent again for 3 days -> new episode
        self.assertEqual(Notification.objects.filter(user=self.mgr).count(), 2)

    def test_episode_start_is_stable(self):
        self.present(TODAY - datetime.timedelta(days=8))
        first = _absence_episode(self.emp, TODAY - datetime.timedelta(days=2))[1]
        later = _absence_episode(self.emp, TODAY)[1]
        self.assertEqual(first, later)
        self.assertEqual(first, TODAY - datetime.timedelta(days=7))

    def test_days_before_joining_not_counted(self):
        self.emp.date_of_joining = TODAY - datetime.timedelta(days=2)
        self.emp.save(update_fields=['date_of_joining'])
        self.assertEqual(_absence_episode(self.emp, TODAY)[0], 2)


class PreferenceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user('p2.pref@test.com', role=make_role('p2_pref'), full_name='Pref User')
        NotificationSettings.objects.create(user=self.user, is_leave_enabled=False, is_approval_enabled=False)

    def emails(self, template):
        with mock.patch('apps.notifications.tasks.send_lifecycle_email_task.apply_async') as send, \
                self.captureOnCommitCallbacks(execute=True):
            _send_lifecycle_email(self.user, template, {})
        return send.call_count

    def test_email_follows_category_preference(self):
        self.assertEqual(self.emails('leave_approved'), 0)          # leave switched off
        self.assertEqual(self.emails('expense_approved'), 1)        # expense still on

    def test_approval_is_mandatory_in_app_and_email(self):
        self.assertEqual(self.emails('leave_request_pending_approval'), 1)
        _notify(self.user, 'New Leave Request', 'x', 'leave_applied', 'leave', 'r1', category='approval')
        self.assertTrue(Notification.objects.filter(user=self.user, title='New Leave Request').exists())
        _notify(self.user, 'Leave Approved', 'x', 'leave_approved', 'leave', 'r2')
        self.assertFalse(Notification.objects.filter(user=self.user, title='Leave Approved').exists())

    def test_security_email_never_gated(self):
        self.assertIsNone(email_category('password_reset_confirmation'))
        self.assertEqual(self.emails('password_reset_confirmation'), 1)

    def test_approval_cannot_be_switched_off_via_api(self):
        cl = APIClient()
        _login(cl, self.user.email)
        resp = cl.patch(reverse('notification-settings'), {'is_approval_enabled': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['data']['is_approval_enabled'])
        self.assertTrue(NotificationSettings.objects.get(user=self.user).is_approval_enabled)
