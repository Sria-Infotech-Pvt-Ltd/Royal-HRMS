"""Phase 8B Task F — migrate each CompanyAsset to an Asset + AssetAllocation (dates/condition preserved), lifecycle transitions, exit recovery input."""
from django.db import transaction

from apps.accounts.models import Asset, AssetAllocation, CompanyAsset


@transaction.atomic
def migrate_company_asset(company_asset: CompanyAsset) -> tuple:
    """Idempotent. Returns (asset, allocation)."""
    existing_asset = getattr(company_asset, 'asset_v2', None)
    if existing_asset is not None:
        return existing_asset, existing_asset.allocations.first()

    asset_tag = company_asset.tag_number or f'LEGACY-{company_asset.id}'
    asset, _ = Asset.objects.get_or_create(
        asset_tag=asset_tag,
        defaults={
            'category_code': company_asset.asset_type, 'condition_code': company_asset.condition,
            'status': Asset.STATUS_IN_STOCK if company_asset.returned_at else Asset.STATUS_ALLOCATED,
            'legacy_company_asset': company_asset,
        },
    )
    allocation = AssetAllocation.objects.create(
        asset=asset, employee=company_asset.employee,
        issued_at=company_asset.issued_at, returned_at=company_asset.returned_at,
        condition_at_issue=company_asset.condition,
        condition_at_return=company_asset.condition if company_asset.returned_at else '',
    )
    return asset, allocation


def issue_asset(asset: Asset, employee, issued_at, issued_by=None) -> AssetAllocation:
    if asset.status == Asset.STATUS_ALLOCATED:
        raise ValueError(f'{asset.asset_tag} is already allocated.')
    allocation = AssetAllocation.objects.create(asset=asset, employee=employee, issued_at=issued_at, issued_by=issued_by)
    asset.status = Asset.STATUS_ALLOCATED
    asset.save(update_fields=['status', 'updated_at'])
    return allocation


def return_asset(allocation: AssetAllocation, returned_at, condition_at_return: str, received_by=None) -> AssetAllocation:
    allocation.returned_at = returned_at
    allocation.condition_at_return = condition_at_return
    allocation.received_by = received_by
    allocation.save(update_fields=['returned_at', 'condition_at_return', 'received_by'])

    asset = allocation.asset
    asset.status = Asset.STATUS_IN_STOCK
    asset.condition_code = condition_at_return
    asset.save(update_fields=['status', 'condition_code', 'updated_at'])
    return allocation


def unreturned_allocations_for_employee(employee):
    return AssetAllocation.objects.filter(employee=employee, returned_at__isnull=True)


def exit_recovery_total(employee) -> 'Decimal':  # noqa: F821
    """Sum of recovery_amount across every unreturned allocation for this
    employee — default 0 per allocation until an owner-configured
    depreciation rule table exists (Task F.4's own instruction)."""
    from decimal import Decimal
    from django.db.models import Sum
    return unreturned_allocations_for_employee(employee).aggregate(total=Sum('recovery_amount'))['total'] or Decimal('0')
