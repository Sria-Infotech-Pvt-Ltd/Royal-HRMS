"""Phase 8B Tasks E/F/H — policy document versions, asset migration, remaining gates."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import CompanyAsset, Document
from apps.accounts.services_asset_v2 import (
    exit_recovery_total, issue_asset, migrate_company_asset, return_asset, unreturned_allocations_for_employee,
)
from apps.accounts.services_policy_document_v2 import (
    compliance_counts, migrate_document_to_version, publish_new_version, record_acknowledgement,
)
from apps.hrms.services_v2_flags import ModuleV2GateError, enable_assets_v2, enable_documents_v2

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class PolicyDocumentTests(TestCase):
    def test_migrate_preserves_legacy_version_label(self):
        document = Document.objects.create(
            title='Leave Policy', category='policy', version='2.3', file_name='x.pdf', file_type='pdf', file_size=100,
        )
        version = migrate_document_to_version(document)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.legacy_version_label, '2.3')

    def test_publish_new_version_increments_number(self):
        document = Document.objects.create(title='x', category='policy', file_name='x.pdf', file_type='pdf', file_size=100)
        migrate_document_to_version(document)
        admin = _make_employee()
        v2 = publish_new_version(document, 'Updated leave carry-forward rule.', admin, requires_reacknowledgement=True)
        self.assertEqual(v2.version_number, 2)
        self.assertTrue(v2.requires_reacknowledgement)

    def test_compliance_counts_track_pending(self):
        document = Document.objects.create(title='x', category='policy', file_name='x.pdf', file_type='pdf', file_size=100)
        version = migrate_document_to_version(document)
        employee_a = _make_employee()
        employee_b = _make_employee()
        record_acknowledgement(version, employee_a)

        counts = compliance_counts(version, [employee_a.id, employee_b.id])
        self.assertEqual(counts['acknowledged_count'], 1)
        self.assertEqual(counts['pending_count'], 1)
        self.assertIn(employee_b.id, counts['pending_employee_ids'])

    def test_gate_blocks_with_unmigrated_documents(self):
        Document.objects.create(title='x', category='policy', file_name='x.pdf', file_type='pdf', file_size=100)
        with self.assertRaises(ModuleV2GateError):
            enable_documents_v2()


class AssetMigrationTests(TestCase):
    def test_migrate_preserves_dates_and_condition(self):
        employee = _make_employee()
        company_asset = CompanyAsset.objects.create(
            employee=employee, asset_type='laptop', tag_number='LAP-001', condition='good',
            issued_at=datetime.date(2026, 1, 1),
        )
        asset, allocation = migrate_company_asset(company_asset)
        self.assertEqual(asset.asset_tag, 'LAP-001')
        self.assertEqual(asset.category_code, 'laptop')
        self.assertEqual(allocation.issued_at, datetime.date(2026, 1, 1))
        self.assertIsNone(allocation.returned_at)
        self.assertEqual(asset.status, asset.STATUS_ALLOCATED)

    def test_migration_is_idempotent(self):
        employee = _make_employee()
        company_asset = CompanyAsset.objects.create(employee=employee, asset_type='laptop', tag_number='LAP-002')
        first_asset, _ = migrate_company_asset(company_asset)
        second_asset, _ = migrate_company_asset(company_asset)
        self.assertEqual(first_asset.id, second_asset.id)

    def test_issue_and_return_lifecycle(self):
        from apps.accounts.models import Asset
        employee = _make_employee()
        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop')
        allocation = issue_asset(asset, employee, datetime.date(2026, 2, 1))
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_ALLOCATED)
        self.assertEqual(unreturned_allocations_for_employee(employee).count(), 1)

        return_asset(allocation, datetime.date(2026, 3, 1), 'good')
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_IN_STOCK)
        self.assertEqual(unreturned_allocations_for_employee(employee).count(), 0)

    def test_cannot_issue_already_allocated_asset(self):
        from apps.accounts.models import Asset
        employee_a = _make_employee()
        employee_b = _make_employee()
        asset = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop', status=Asset.STATUS_ALLOCATED)
        with self.assertRaises(ValueError):
            issue_asset(asset, employee_b, datetime.date(2026, 2, 1))

    def test_exit_recovery_total_sums_unreturned(self):
        from apps.accounts.models import Asset, AssetAllocation
        employee = _make_employee()
        asset1 = Asset.objects.create(asset_tag=_unique('TAG'), category_code='laptop')
        asset2 = Asset.objects.create(asset_tag=_unique('TAG'), category_code='mobile_phone')
        AssetAllocation.objects.create(asset=asset1, employee=employee, recovery_amount=Decimal('5000'))
        AssetAllocation.objects.create(asset=asset2, employee=employee, recovery_amount=Decimal('2000'), returned_at=datetime.date(2026, 1, 1))
        self.assertEqual(exit_recovery_total(employee), Decimal('5000'))

    def test_gate_blocks_with_unmigrated_assets(self):
        employee = _make_employee()
        CompanyAsset.objects.create(employee=employee, asset_type='laptop', tag_number=_unique('TAG'))
        with self.assertRaises(ModuleV2GateError):
            enable_assets_v2()
