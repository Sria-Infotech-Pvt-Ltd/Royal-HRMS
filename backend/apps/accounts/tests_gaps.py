"""Phase 8B gap-closure tests — asset requests/fulfilment, depreciation recovery, policy-document compliance CSV."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Asset, AssetDepreciationRule, Document
from apps.accounts.services_asset_gaps import (
    approve_asset_request, assets_with_expiring_warranty, compute_recovery_amount, fulfil_asset_request, request_asset,
)
from apps.accounts.services_policy_document_gaps import compliance_report_csv
from apps.accounts.services_policy_document_v2 import migrate_document_to_version

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class AssetRequestLifecycleTests(TestCase):
    def test_request_approve_fulfil(self):
        employee = _make_employee()
        approver = _make_employee()
        request = request_asset(employee, 'laptop', 'Need one for development.')
        approve_asset_request(request, approver)
        request.refresh_from_db()
        self.assertEqual(request.status, request.STATUS_APPROVED)

        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop')
        fulfil_asset_request(request, asset, datetime.date(2026, 2, 1))
        request.refresh_from_db()
        self.assertEqual(request.status, request.STATUS_FULFILLED)
        self.assertIsNotNone(request.fulfilled_allocation)

    def test_cannot_fulfil_unapproved_request(self):
        employee = _make_employee()
        request = request_asset(employee, 'laptop', 'x')
        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop')
        with self.assertRaises(ValueError):
            fulfil_asset_request(request, asset, datetime.date(2026, 2, 1))


class WarrantyAndDepreciationTests(TestCase):
    def test_expiring_warranty_found_within_window(self):
        Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop', warranty_end=datetime.date.today() + datetime.timedelta(days=10))
        Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop', warranty_end=datetime.date.today() + datetime.timedelta(days=90))
        expiring = assets_with_expiring_warranty(within_days=30)
        self.assertEqual(expiring.count(), 1)

    def test_no_rule_means_zero_recovery(self):
        from apps.accounts.models import AssetAllocation
        employee = _make_employee()
        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='unknown_category', cost=Decimal('50000'))
        allocation = AssetAllocation.objects.create(asset=asset, employee=employee, issued_at=datetime.date(2026, 1, 1))
        self.assertEqual(compute_recovery_amount(allocation), Decimal('0'))

    def test_rule_applies_correct_age_band(self):
        from apps.accounts.models import AssetAllocation
        employee = _make_employee()
        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop', cost=Decimal('100000'))
        AssetDepreciationRule.objects.create(
            category_code='laptop',
            age_bands=[{'max_age_months': 12, 'recovery_percent': 80}, {'max_age_months': 36, 'recovery_percent': 30}],
        )
        old_allocation = AssetAllocation.objects.create(
            asset=asset, employee=employee, issued_at=datetime.date.today() - datetime.timedelta(days=800),
        )
        recovery = compute_recovery_amount(old_allocation)
        self.assertEqual(recovery, Decimal('30000.00'))


class PolicyComplianceExportTests(TestCase):
    def test_csv_export_lists_pending_and_acknowledged(self):
        document = Document.objects.create(title='Leave Policy', category='policy', file_name='x.pdf', file_type='pdf', file_size=10)
        version = migrate_document_to_version(document)
        employee_a = _make_employee()
        employee_b = _make_employee()
        from apps.accounts.services_policy_document_v2 import record_acknowledgement
        record_acknowledgement(version, employee_a)

        csv_text = compliance_report_csv(
            version, [employee_a.id, employee_b.id],
            {employee_a.id: {'name': 'A'}, employee_b.id: {'name': 'B'}},
        )
        self.assertIn('Acknowledged', csv_text)
        self.assertIn('Pending', csv_text)
