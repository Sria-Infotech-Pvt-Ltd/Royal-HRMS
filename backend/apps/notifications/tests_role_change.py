"""
Tests for the role-change Notification/email added to
apps.notifications.signals._on_promotion_record_created — the missing
counterpart to the existing designation-change ("promotion") notification,
identified during investigation: role-only changes previously produced no
notification of any kind.

Exercises the real EmployeeDetailView.put() endpoint (not the signal
handler directly) for the end-to-end cases, since the actual production
trigger is a PUT request whose transaction.atomic() block creates the
PromotionRecord this signal reacts to. Uses Django's
captureOnCommitCallbacks — the standard way to make transaction.on_commit
callbacks actually run inside a TestCase (which otherwise wraps everything
in a savepoint that never really commits) and to observe whether a
callback was queued at all.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Department, Designation, PromotionRecord
from apps.notifications.models import Notification
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


class RoleChangeNotificationTests(TestCase):

    def setUp(self):
        self.hr_role = make_role('hr_rolechange_test', permission_codenames=['employees.edit'])
        self.hr_user = make_user(
            'hr.rolechange@test.com', role=self.hr_role, password='TestPass123!',
            employee_id='HRRC001', full_name='HR Admin',
        )

        self.employee_role = make_role('employee_rolechange_test')
        self.manager_role  = make_role('manager_rolechange_test', can_manage_team=True)

        # EmployeeDetailView.put() requires the target designation to exist
        # as a real, active Designation row (level left at its default 0, so
        # _check_promotion_hierarchy skips the level comparison entirely).
        dept = Department.objects.create(name='Engineering Rolechange Test')
        Designation.objects.create(name='Software Engineer', department=dept)
        Designation.objects.create(name='Senior Software Engineer', department=dept)
        Designation.objects.create(name='Engineering Manager', department=dept)

        self.employee = make_user(
            'target.rolechange@test.com', role=self.employee_role, password='TestPass123!',
            employee_id='EMPRC001', full_name='Target Employee',
            department='Engineering Rolechange Test', designation='Software Engineer',
        )
        self.other_employee = make_user(
            'other.rolechange@test.com', role=self.employee_role, password='TestPass123!',
            employee_id='EMPRC002', full_name='Other Employee',
        )

        self.client_api = APIClient()

    def _edit_url(self, employee_id: str):
        return reverse('employee-detail', kwargs={'employee_id': employee_id})

    # ── Role-only change: notification (tests #1, #2, #3, #8) ───────────

    def test_role_only_change_creates_notification_for_correct_employee(self):
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        notifications = Notification.objects.filter(user=self.employee, notification_type='role_change')
        self.assertEqual(notifications.count(), 1)
        note = notifications.first()
        self.assertEqual(note.module, 'role_change')
        self.assertFalse(note.is_read)
        self.assertIn('Employee Rolechange Test', note.message)   # previous role, title-cased
        self.assertIn('Manager Rolechange Test', note.message)    # new role, title-cased

        # test #8: another employee never receives it.
        self.assertEqual(
            Notification.objects.filter(user=self.other_employee, notification_type='role_change').count(), 0,
        )

    # ── Commit/rollback semantics (tests #4, #5) ─────────────────────────

    def test_notification_only_queued_after_commit_via_real_endpoint(self):
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks() as callbacks:  # execute=False: just observe
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)
        # A callback was queued (the deferred _send()) — and, crucially, no
        # Notification row exists yet since we passed execute=False above.
        self.assertGreaterEqual(len(callbacks), 1)
        self.assertEqual(
            Notification.objects.filter(user=self.employee, notification_type='role_change').count(), 0,
        )

    def test_rolled_back_promotion_record_never_notifies(self):
        count_before = Notification.objects.filter(user=self.employee).count()

        callbacks = []
        try:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with transaction.atomic():
                    PromotionRecord.objects.create(
                        employee=self.employee,
                        previous_role='employee_rolechange_test', new_role='manager_rolechange_test',
                        previous_designation='Software Engineer', new_designation='Software Engineer',
                        effective_date=date.today(), promoted_by=self.hr_user,
                    )
                    raise RuntimeError('simulated failure after PromotionRecord.create(), before commit')
        except RuntimeError:
            pass

        # The inner transaction.atomic() rolled back, so Django discards its
        # on_commit callbacks — nothing should have been queued/executed,
        # and no Notification row should exist.
        self.assertEqual(len(callbacks), 0)
        self.assertEqual(Notification.objects.filter(user=self.employee).count(), count_before)

    # ── Designation-only change: unchanged existing behavior (test #6, #12) ──

    def test_designation_only_change_still_uses_existing_promotion_notification(self):
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'designation': 'Senior Software Engineer'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        promo = Notification.objects.filter(user=self.employee, notification_type='promotion')
        self.assertEqual(promo.count(), 1)
        self.assertEqual(promo.first().title, 'Congratulations on Your Promotion!')
        self.assertIn('Senior Software Engineer', promo.first().message)
        # No role text appended, and no separate role_change notification —
        # message/behavior identical to before this change for this case.
        self.assertNotIn('role has also been updated', promo.first().message)
        self.assertEqual(
            Notification.objects.filter(user=self.employee, notification_type='role_change').count(), 0,
        )

    # ── Role + designation together: no duplicate (test #7) ─────────────

    def test_role_and_designation_together_sends_one_enhanced_notification(self):
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test', 'designation': 'Engineering Manager'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        all_notes = Notification.objects.filter(user=self.employee)
        self.assertEqual(all_notes.count(), 1)  # exactly one, not two
        note = all_notes.first()
        self.assertEqual(note.notification_type, 'promotion')
        self.assertIn('Engineering Manager', note.message)
        self.assertIn('role has also been updated', note.message)
        self.assertIn('Manager Rolechange Test', note.message)

    # ── Existing Notification API still works (tests #9, #10) ───────────

    def test_existing_notification_api_can_retrieve_and_mark_read(self):
        _login(self.client_api, 'hr.rolechange@test.com')
        with self.captureOnCommitCallbacks(execute=True):
            self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test'}, format='json',
            )

        employee_client = APIClient()
        _login(employee_client, 'target.rolechange@test.com')

        list_resp = employee_client.get(reverse('notification-list'), {'notification_type': 'role_change'})
        self.assertEqual(list_resp.status_code, 200, list_resp.data)
        results = list_resp.data['data']['results']
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]['is_read'])

        note_id = results[0]['id']
        read_resp = employee_client.patch(reverse('notification-mark-read', kwargs={'notification_id': note_id}))
        self.assertEqual(read_resp.status_code, 200, read_resp.data)

        note = Notification.objects.get(pk=note_id)
        self.assertTrue(note.is_read)

    # ── Email (tests #11, #12) ───────────────────────────────────────────

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_role_only_change_sends_email_to_affected_employee(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Role Change Email Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        mock_send.assert_called_once()
        sent_message = mock_send.call_args.args[0][0]
        self.assertEqual(list(sent_message.to), ['target.rolechange@test.com'])
        self.assertNotIn('Temporary Password', sent_message.body)

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_designation_only_change_sends_designation_email(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Designation Change Email Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'designation': 'Senior Software Engineer'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        mock_send.assert_called_once()
        sent_message = mock_send.call_args.args[0][0]
        self.assertEqual(list(sent_message.to), ['target.rolechange@test.com'])
        self.assertIn('New Designation', sent_message.body)
        self.assertIn('Senior Software Engineer', sent_message.body)
        self.assertIn('Previous Designation', sent_message.body)  # label present -> both values rendered, not just a substring match
        self.assertNotIn('Temporary Password', sent_message.body)
        # No role line — role did not change in this case.
        self.assertNotIn('New Role', sent_message.body)

    @patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1)
    def test_role_and_designation_together_sends_exactly_one_combined_email(self, mock_send):
        from apps.accounts.models import SMTPSettings
        SMTPSettings.objects.create(
            name='Combined Change Email Test SMTP', host='smtp.example.com', port=587,
            username='test@example.com', password='irrelevant',
            from_email='test@example.com', is_active=True,
        )
        _login(self.client_api, 'hr.rolechange@test.com')

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'role': 'manager_rolechange_test', 'designation': 'Engineering Manager'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)

        # Exactly one email — never both send_designation_change_email AND
        # send_role_change_email for the same PromotionRecord.
        mock_send.assert_called_once()
        sent_message = mock_send.call_args.args[0][0]
        self.assertEqual(list(sent_message.to), ['target.rolechange@test.com'])
        self.assertIn('Engineering Manager', sent_message.body)
        self.assertIn('Manager Rolechange Test', sent_message.body)  # new role, title-cased
        self.assertIn('New Role', sent_message.body)

    # ── Neither role nor designation changed: no notification at all ────

    def test_unrelated_field_change_creates_no_promotion_record_or_notification(self):
        _login(self.client_api, 'hr.rolechange@test.com')
        count_before = Notification.objects.filter(user=self.employee).count()

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_api.put(
                self._edit_url(self.employee.employee_id),
                {'phone': '9999999999'}, format='json',
            )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Notification.objects.filter(user=self.employee).count(), count_before)
        self.assertFalse(PromotionRecord.objects.filter(employee=self.employee).exists())
