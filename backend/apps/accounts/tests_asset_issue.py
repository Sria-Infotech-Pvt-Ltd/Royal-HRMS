"""UAT-054: an asset marked "issue later" stays pending until HR records the tag and the date; issuing it is audited; access cards exist."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, CompanyAsset


class AssetIssueTests(TestCase):
    def setUp(self):
        cache.clear()
        hr = make_user('hr-asset@test.com', role=make_role('hr_asset_test', permission_codenames=['onboarding.edit']), employee_id='EMPAS000')
        self.employee = make_user('asset.emp@test.com', employee_id='EMPAS001', onboarding_status='complete')
        self.asset = CompanyAsset.objects.create(employee=self.employee, asset_type='laptop', condition='new')  # issue later: no tag, no date
        self.client = APIClient()
        self.client.force_authenticate(user=hr)
        self.url = reverse('onboarding-employee-assets-detail', args=[self.employee.pk, self.asset.pk])

    def test_access_card_is_a_selectable_type(self):
        self.assertIn('access_card', dict(CompanyAsset.ASSET_TYPE_CHOICES))

    def test_issuing_needs_the_tag_first(self):
        response = self.client.patch(self.url, {'issued_at': datetime.date.today().isoformat()}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('asset tag', response.json()['message'])
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.issued_at)  # still pending

    def test_issuing_with_tag_and_date_assigns_it_and_audits_it(self):
        today = datetime.date.today().isoformat()
        response = self.client.patch(self.url, {'tag_number': 'LT-0042', 'issued_at': today, 'condition': 'good'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        self.asset.refresh_from_db()
        self.assertEqual((self.asset.tag_number, str(self.asset.issued_at), self.asset.condition), ('LT-0042', today, 'good'))
        event = AuditLog.objects.get(action='asset_issued')
        self.assertEqual((event.changes['tag_number'], event.changes['issued_at'], event.changes['condition']), ('LT-0042', today, 'good'))

    def test_editing_an_already_issued_asset_is_not_an_issue_event(self):
        self.client.patch(self.url, {'tag_number': 'LT-1', 'issued_at': datetime.date.today().isoformat()}, format='json')
        self.client.patch(self.url, {'condition': 'refurbished'}, format='json')
        self.assertEqual(AuditLog.objects.filter(action='asset_issued').count(), 1)
        self.assertEqual(AuditLog.objects.filter(action='onboarding_asset_updated_by_hr').count(), 1)
