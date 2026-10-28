"""UAT-030: HR can correct an employee's mobile and personal (= login) email after hire, with validation, an audit entry and an explicit login-email confirmation."""
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.accounts.services_contact_change import is_mobile_changed

SEND = 'apps.accounts.services_contact_change.send_template_email'


class HrContactEditTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_contact_edit_test', permission_codenames=['employees.edit', 'employees.view'])
        self.hr_user = make_user('hr-contact@test.com', role=hr_role)
        self.employee = make_user(
            'typo.employee@test.com', full_name='Pat Chester', phone='9876543210', employee_id='EMPCONTACT1',
        )
        self.other = make_user('someone.else@test.com', phone='+91 91234 56780', employee_id='EMPCONTACT2')
        self.url = reverse('employee-detail', args=[self.employee.employee_id])
        self.client.force_authenticate(user=self.hr_user)

    def _patch(self, body):
        return self.client.patch(self.url, body, format='json')

    def _audit(self):
        return AuditLog.objects.filter(action='employee_updated', object_id=str(self.employee.id)).first()

    # ---- mobile ----
    def test_hr_corrects_the_mobile_and_it_is_audited(self):
        response = self._patch({'phone': '+91 98765 11111'})
        self.assertEqual(response.status_code, 200, response.json())
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9876511111')
        entry = self._audit()
        self.assertEqual(entry.changes['phone'], {'from': '9876543210', 'to': '9876511111'})
        self.assertEqual(entry.user_id, self.hr_user.id)
        self.assertIsNotNone(entry.created_at)

    def test_invalid_mobiles_are_rejected_with_a_message_beside_the_field(self):
        for bad in ('12345', '5876543210', 'abcdefghij', '98765432101234', ''):
            response = self._patch({'phone': bad})
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('phone', response.json()['data'], bad)
            self.assertIn('10-digit', response.json()['message'], bad)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone, '9876543210')

    def test_a_mobile_used_by_another_employee_is_rejected_whatever_its_format(self):
        response = self._patch({'phone': '9123456780'})  # stored for `other` as "+91 91234 56780"
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['data']['phone'], 'This mobile number is already used by another employee.')

    def test_echoing_the_stored_mobile_is_not_a_change(self):
        self.assertFalse(is_mobile_changed(self.employee, '+91 98765 43210'))
        self.assertTrue(is_mobile_changed(self.employee, '9876511111'))
        self.assertTrue(is_mobile_changed(self.employee, ''))

    # ---- email (= login) ----
    @mock.patch(SEND)
    def test_login_email_change_needs_explicit_confirmation(self, send):
        response = self._patch({'email': 'fixed.employee@test.com'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('login', response.json()['data']['email'])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'typo.employee@test.com')
        send.assert_not_called()
        self.assertIsNone(self._audit())

    @mock.patch(SEND)
    def test_confirmed_change_updates_login_audits_and_notifies_both_addresses(self, send):
        response = self._patch({'email': 'Fixed.Employee@test.com', 'confirm_login_email_change': True})
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn('notified at both addresses', response.json()['message'])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'fixed.employee@test.com')
        self.assertEqual(
            self._audit().changes['email'],
            {'from': 'typo.employee@test.com', 'to': 'fixed.employee@test.com', 'is_login_email': True},
        )
        recipients = sorted(call.kwargs['recipient_email'] for call in send.call_args_list)
        self.assertEqual(recipients, ['fixed.employee@test.com', 'typo.employee@test.com'])

    @mock.patch(SEND, side_effect=RuntimeError('smtp down'))
    def test_failed_notification_is_reported_not_hidden(self, _send):
        response = self._patch({'email': 'fixed.employee@test.com', 'confirm_login_email_change': True})
        self.assertEqual(response.status_code, 200)
        self.assertIn('could not be sent', response.json()['message'])

    @mock.patch(SEND)
    def test_invalid_and_duplicate_emails_are_rejected(self, _send):
        bad = self._patch({'email': 'not-an-email', 'confirm_login_email_change': True})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()['data']['email'], 'Enter a valid email address.')
        duplicate = self._patch({'email': 'SOMEONE.ELSE@test.com', 'confirm_login_email_change': True})
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()['data']['email'], 'This email is already used by another employee.')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, 'typo.employee@test.com')

    # ---- who may edit ----
    def test_a_role_without_edit_permission_cannot_change_either_field(self):
        employee_role = make_role('plain_employee_contact_test', permission_codenames=[])
        plain_user = make_user('plain@test.com', role=employee_role, employee_id='EMPCONTACT3')
        self.client.force_authenticate(user=plain_user)
        response = self._patch({'phone': '9876511111', 'email': 'x@test.com', 'confirm_login_email_change': True})
        self.assertEqual(response.status_code, 403)
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.phone, self.employee.email), ('9876543210', 'typo.employee@test.com'))


class OldEmailAccessEndsTests(TestCase):
    """UAT-030 follow-up: once the login email changes, nothing tied to the old address keeps working."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        hr_role = make_role('hr_old_email_test', permission_codenames=['employees.edit', 'employees.view'])
        self.client.force_authenticate(user=make_user('hr-old-email@test.com', role=hr_role))
        self.employee = make_user('old.address@test.com', employee_id='EMPOLD0001')
        self.bystander = make_user('bystander@test.com', employee_id='EMPOLD0002')
        self.url = reverse('employee-detail', args=[self.employee.employee_id])

    def _sessions(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        return RefreshToken.for_user(user)

    @mock.patch(SEND)
    def test_sessions_reset_links_and_codes_for_the_old_address_stop_working(self, _send):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from apps.accounts.models import OTPVerification, PasswordResetToken

        own_session, other_session = self._sessions(self.employee), self._sessions(self.bystander)
        later = timezone.now() + timedelta(hours=2)
        reset = PasswordResetToken.objects.create(user=self.employee, expires_at=later)
        invite = PasswordResetToken.objects.create(user=self.employee, expires_at=later, purpose=PasswordResetToken.PURPOSE_INVITE)
        code = OTPVerification.objects.create(user=self.employee, otp='hash', expires_at=later)
        other_reset = PasswordResetToken.objects.create(user=self.bystander, expires_at=later)

        response = self.client.patch(self.url, {'email': 'new.address@test.com', 'confirm_login_email_change': True}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        self.assertIn('Existing sign-ins ended', response.json()['message'])

        self.assertTrue(BlacklistedToken.objects.filter(token__jti=own_session['jti']).exists())
        for token in (reset, invite):
            token.refresh_from_db()
            self.assertFalse(token.is_valid())
            self.assertEqual(token.status, PasswordResetToken.STATUS_EXPIRED)  # kept as a record, shown as Expired
        code.refresh_from_db()
        self.assertLessEqual(code.expires_at, timezone.now())
        # nobody else is affected
        self.assertFalse(BlacklistedToken.objects.filter(token__jti=other_session['jti']).exists())
        other_reset.refresh_from_db()
        self.assertTrue(other_reset.is_valid())

    @mock.patch(SEND)
    def test_a_rejected_email_change_ends_nothing(self, _send):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        own_session = self._sessions(self.employee)
        self.client.patch(self.url, {'email': 'new.address@test.com'}, format='json')  # no confirmation: refused
        self.assertFalse(BlacklistedToken.objects.filter(token__jti=own_session['jti']).exists())
