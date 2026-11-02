"""Onboarding vs Active: an employee shows "Onboarding" (not "Active") until
they actually activate their account — first login + password set — not
merely once HR finishes entering their data (onboarding_status). See
User.account_activated_at / User.onboarded_q() and views/shared.py's
_employee_dict()."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.accounts.views.shared import _employee_dict


class AccountActivationStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.role = make_role('onboarding_activation_test')

    def test_hire_wizard_style_employee_shows_onboarding_until_activated(self):
        # onboarding_status already complete (data fully entered at hire) but never activated.
        user = make_user(
            'hirewizard@test.com', role=self.role, employee_id='EMPACT01',
            onboarding_status=User.ONBOARDING_COMPLETE, account_activated_at=None,
        )
        self.assertFalse(user.is_onboarded())
        self.assertEqual(_employee_dict(user)['status'], 'onboarding')
        self.assertFalse(_employee_dict(user)['needs_onboarding_data'])  # data IS complete — a separate concern

    def test_change_password_view_activates_a_first_time_temp_password_user(self):
        user = make_user(
            'tempfirstlogin@test.com', role=self.role, employee_id='EMPACT02', password='TempPass123!',
            onboarding_status=User.ONBOARDING_COMPLETE, account_activated_at=None, must_change_password=True,
        )
        self.assertEqual(_employee_dict(user)['status'], 'onboarding')

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(reverse('change-password'), {
            'old_password': 'TempPass123!', 'new_password': 'BrandNewPass123!', 'confirm_password': 'BrandNewPass123!',
        })
        self.assertEqual(resp.status_code, 200, resp.data)

        user.refresh_from_db()
        self.assertIsNotNone(user.account_activated_at)
        self.assertFalse(user.must_change_password)
        self.assertEqual(_employee_dict(user)['status'], 'active')
        self.assertTrue(AuditLog.objects.filter(user=user, action='account_activated').exists())

    def test_change_password_view_does_not_reactivate_an_already_active_user(self):
        # A normal, already-active employee voluntarily changing their password later — not a first activation.
        user = make_user(
            'alreadyactive@test.com', role=self.role, employee_id='EMPACT03', password='CurrentPass123!',
            onboarding_status=User.ONBOARDING_COMPLETE, must_change_password=False,
        )
        first_activated_at = user.account_activated_at
        self.assertIsNotNone(first_activated_at)

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(reverse('change-password'), {
            'old_password': 'CurrentPass123!', 'new_password': 'AnotherPass123!', 'confirm_password': 'AnotherPass123!',
        })
        self.assertEqual(resp.status_code, 200, resp.data)

        user.refresh_from_db()
        self.assertEqual(user.account_activated_at, first_activated_at)  # unchanged
        self.assertTrue(AuditLog.objects.filter(user=user, action='password_changed').exists())
        self.assertFalse(AuditLog.objects.filter(user=user, action='account_activated').exists())

    def test_self_service_employee_is_onboarding_until_data_complete_even_if_activated(self):
        # account_activated_at set (e.g. they logged into their portal account), but HR hasn't approved/completed
        # their data yet — still "Onboarding", and needs_onboarding_data is the separate signal that's actually true here.
        user = make_user(
            'selfservice@test.com', role=self.role, employee_id='EMPACT04',
            onboarding_status=User.ONBOARDING_PENDING,
        )
        self.assertFalse(user.is_onboarded())
        row = _employee_dict(user)
        self.assertEqual(row['status'], 'onboarding')
        self.assertTrue(row['needs_onboarding_data'])

    def test_fully_onboarded_employee_shows_active(self):
        user = make_user(
            'fullyonboarded@test.com', role=self.role, employee_id='EMPACT05',
            onboarding_status=User.ONBOARDING_COMPLETE,
        )
        self.assertTrue(user.is_onboarded())
        self.assertEqual(_employee_dict(user)['status'], 'active')

    def test_onboarded_q_matches_is_onboarded_for_queryset_filtering(self):
        active_user = make_user('qactive@test.com', role=self.role, employee_id='EMPACT06', onboarding_status=User.ONBOARDING_COMPLETE)
        onboarding_user = make_user('qonboarding@test.com', role=self.role, employee_id='EMPACT07', account_activated_at=None)

        onboarded_ids = set(User.objects.filter(User.onboarded_q()).values_list('id', flat=True))
        self.assertIn(active_user.id, onboarded_ids)
        self.assertNotIn(onboarding_user.id, onboarded_ids)
