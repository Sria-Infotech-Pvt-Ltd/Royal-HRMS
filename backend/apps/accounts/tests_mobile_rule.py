"""UAT-069: one mobile rule on every screen: hire draft, Edit my details, bulk import; "123" is rejected with a friendly message."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import HireAction, OrgUnit, Position
from apps.accounts.validators import validate_mobile_number
from rest_framework import serializers


class SharedMobileValidatorTests(TestCase):
    def test_valid_formats_are_normalised_to_ten_digits(self):
        for value in ('9876543210', '+91 98765 43210', '91-9876543210', ' 98765 43210 '):
            self.assertEqual(validate_mobile_number(value), '9876543210')

    def test_blank_stays_blank_and_bad_values_get_a_friendly_message(self):
        self.assertEqual(validate_mobile_number('  '), '')
        for bad in ('123', '5876543210', '98765432101234', 'abcdefghij'):
            with self.assertRaises(serializers.ValidationError) as caught:
                validate_mobile_number(bad)
            self.assertIn('10-digit Indian mobile', caught.exception.detail[0])
            self.assertNotIn('phone:', caught.exception.detail[0])  # the field name is never baked into the text


class MobileOnEveryScreenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_edit_my_details_rejects_123_and_stores_a_valid_number_normalised(self):
        employee = make_user(
            'mobile.self@test.com', employee_id='EMPMB001',
            role=make_role('self_edit_mobile_test', permission_codenames=['employees.edit_own_profile']),
        )
        self.client.force_authenticate(user=employee)
        url = reverse('my-profile')
        bad = self.client.patch(url, {'phone': '123'}, format='json')
        self.assertEqual(bad.status_code, 400, bad.json())
        self.assertIn('10-digit Indian mobile', bad.json()['message'])
        good = self.client.patch(url, {'phone': '+91 98765 43210'}, format='json')
        self.assertEqual(good.status_code, 200, good.json())
        employee.refresh_from_db()
        self.assertEqual(employee.phone, '9876543210')

    def test_hire_draft_applies_the_same_rule_and_normalises(self):
        hr = make_user('mobile.hr@test.com', role=make_role('hr_mobile_test', permission_codenames=['employees.create']))
        unit = OrgUnit.objects.create(name='Engineering')
        position = Position.objects.create(org_unit=unit, title='Engineer', grade='L2')
        action = HireAction.objects.create(reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(), position=position, created_by=hr)
        self.client.force_authenticate(user=hr)
        url = reverse('hire-action-detail', args=[action.pk])
        bad = self.client.patch(url, {'phone': '123'}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertIn('phone', bad.json()['data'])
        good = self.client.patch(url, {'phone': '+91 98765 43210'}, format='json')
        self.assertEqual(good.status_code, 200, good.json())
        action.refresh_from_db()
        self.assertEqual(action.draft_data['phone'], '9876543210')
