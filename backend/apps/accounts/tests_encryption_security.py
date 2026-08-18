"""
Regression tests for PII field-level encryption and bank-detail-change
fraud alerting (see core/encrypted_fields.py and
EmployeeProfile.save()/_alert_bank_details_changed).
"""
from __future__ import annotations

from django.db import connection
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeProfile, find_conflicting_pan_profile
from apps.notifications.models import Notification


class FieldEncryptionTests(TestCase):
    """Bank account number / IFSC / PAN / UAN / Aadhaar name are encrypted at rest."""

    def setUp(self):
        role = make_role('employee')
        self.user = make_user('encryption.test@test.com', role=role, password='TestPass123!')

    def test_sensitive_fields_are_ciphertext_in_the_database(self):
        profile = EmployeeProfile.objects.create(
            user=self.user,
            account_number='1234567890',
            ifsc_code='SBIN0001234',
            pan_number='ABCDE1234F',
            uan_number='123456789012',
            name_as_per_aadhar='Test User',
        )
        with connection.cursor() as cur:
            cur.execute(
                'SELECT account_number, ifsc_code, pan_number, uan_number, name_as_per_aadhar '
                'FROM hrms_employee_profiles WHERE id = %s',
                [str(profile.pk)],
            )
            row = cur.fetchone()
        for raw_value, plaintext in zip(row, [
            '1234567890', 'SBIN0001234', 'ABCDE1234F', '123456789012', 'Test User',
        ]):
            self.assertNotEqual(raw_value, plaintext, 'value was stored in plaintext')
            self.assertTrue(raw_value.startswith('gAAAAA'), 'value is not Fernet ciphertext')

    def test_encrypted_fields_transparently_decrypt_on_read(self):
        EmployeeProfile.objects.create(
            user=self.user, account_number='1234567890', pan_number='ABCDE1234F',
        )
        reloaded = EmployeeProfile.objects.get(user=self.user)
        self.assertEqual(reloaded.account_number, '1234567890')
        self.assertEqual(reloaded.pan_number, 'ABCDE1234F')

    def test_pan_duplicate_detection_still_works_via_blind_index(self):
        EmployeeProfile.objects.create(user=self.user, pan_number='ABCDE1234F')
        other_user = make_user(
            'encryption.test2@test.com', role=make_role('employee'), password='TestPass123!',
        )
        other_profile = EmployeeProfile.objects.create(user=other_user)

        conflict = find_conflicting_pan_profile('ABCDE1234F', exclude_profile_pk=other_profile.pk)
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.user_id, self.user.id)

        no_conflict = find_conflicting_pan_profile('ZZZZZ9999Z', exclude_profile_pk=other_profile.pk)
        self.assertIsNone(no_conflict)


class BankDetailChangeAlertTests(TestCase):
    """Overwriting an existing bank account/IFSC fires an audit log + employee notification;
    first-time entry (empty -> filled) does not."""

    def setUp(self):
        role = make_role('employee')
        self.user = make_user('bankalert.test@test.com', role=role, password='TestPass123!')
        self.admin = make_user(
            'bankalert.admin@test.com', role=make_role('hr'), password='TestPass123!',
        )

    def test_first_time_entry_does_not_alert(self):
        profile = EmployeeProfile.objects.create(user=self.user)
        profile.account_number = '1111222233334444'
        profile.ifsc_code = 'SBIN0001111'
        profile.save()

        self.assertFalse(
            AuditLog.objects.filter(action='bank_details_changed', object_id=str(self.user.id)).exists()
        )
        self.assertFalse(
            Notification.objects.filter(notification_type='security_alert', user=self.user).exists()
        )

    def test_overwriting_existing_value_alerts_with_attribution(self):
        profile = EmployeeProfile.objects.create(
            user=self.user, account_number='1111222233334444', ifsc_code='SBIN0001111',
        )
        profile._changed_by = self.admin
        profile.account_number = '9999888877776666'
        profile.save()

        log = AuditLog.objects.filter(
            action='bank_details_changed', object_id=str(self.user.id),
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user_id, self.admin.id)

        notification = Notification.objects.filter(
            notification_type='security_alert', user=self.user,
        ).first()
        self.assertIsNotNone(notification)

    def test_saving_with_unchanged_bank_details_does_not_alert(self):
        profile = EmployeeProfile.objects.create(
            user=self.user, account_number='1111222233334444', ifsc_code='SBIN0001111',
        )
        profile.father_name = 'Someone'  # unrelated field
        profile.save()

        self.assertFalse(
            AuditLog.objects.filter(action='bank_details_changed', object_id=str(self.user.id)).exists()
        )
