"""Phase 8B gap-closure — asset requests/fulfilment, warranty reminders, depreciated-value recovery."""
import datetime
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import Asset, AssetDepreciationRule, AssetRequest


def request_asset(employee, category_code: str, justification: str) -> AssetRequest:
    return AssetRequest.objects.create(employee=employee, category_code=category_code, justification=justification)


def approve_asset_request(request: AssetRequest, approved_by) -> AssetRequest:
    request.status = AssetRequest.STATUS_APPROVED
    request.approved_by = approved_by
    request.save(update_fields=['status', 'approved_by'])
    return request


@transaction.atomic
def fulfil_asset_request(request: AssetRequest, asset: Asset, issued_at, checklist_task_instance=None) -> AssetRequest:
    """Links the real AssetAllocation created for `asset`/`request.employee`
    — the "fulfilment task goes to IT/admin (8A checklist task type)" is
    satisfied by the CALLER passing a real ChecklistTaskInstance it
    already created via the 8A checklist engine; this function just links
    it, it doesn't create checklist infrastructure of its own."""
    if request.status != AssetRequest.STATUS_APPROVED:
        raise ValueError(f'Request {request.id} is not approved (status={request.status}).')
    from apps.accounts.services_asset_v2 import issue_asset
    allocation = issue_asset(asset, request.employee, issued_at)
    request.status = AssetRequest.STATUS_FULFILLED
    request.fulfilled_allocation = allocation
    request.checklist_task = checklist_task_instance
    request.save(update_fields=['status', 'fulfilled_allocation', 'checklist_task'])
    return request


def assets_with_expiring_warranty(within_days: int = 30):
    cutoff = datetime.date.today() + datetime.timedelta(days=within_days)
    return Asset.objects.filter(warranty_end__isnull=False, warranty_end__lte=cutoff, warranty_end__gte=datetime.date.today())


def compute_recovery_amount(allocation) -> Decimal:
    """The real depreciated-value recovery (Task F.4) — looks up
    AssetDepreciationRule for the asset's category; no matching rule or
    age band = 0, exactly as the master prompt specifies (default no
    recovery amount, owner configures the real rates)."""
    if allocation.issued_at is None:
        return Decimal('0')
    rule = AssetDepreciationRule.objects.filter(category_code=allocation.asset.category_code).first()
    if rule is None:
        return Decimal('0')

    age_months = (datetime.date.today() - allocation.issued_at).days // 30
    for band in rule.age_bands:
        if age_months <= band['max_age_months']:
            original_cost = allocation.asset.cost or Decimal('0')
            return (original_cost * Decimal(str(band['recovery_percent'])) / 100).quantize(Decimal('0.01'))
    return Decimal('0')
