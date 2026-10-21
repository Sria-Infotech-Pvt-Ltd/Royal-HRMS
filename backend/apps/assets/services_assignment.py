"""
Assigning one asset to one employee — shared by the single Assign Asset
endpoint (AssignAssetView) and the bulk assignment import, so both get the
same locking, status update, assignment-history row and audit entry.

Callers do their own permission / scope / input validation first.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

from apps.accounts.models import AuditLog
from apps.assets.models import Asset, AssetAssignment

logger = logging.getLogger(__name__)


class AssetNotAvailable(Exception):
    """The asset isn't Available any more (checked under a row lock)."""

    def __init__(self, asset: Asset):
        self.asset = asset
        super().__init__(f'"{asset.asset_tag}" is not available — current status: {asset.get_status_display()}.')


class AssetAssignConflict(Exception):
    """Another request assigned the asset at the same moment (unique active-assignment constraint)."""

    def __init__(self, asset: Asset):
        self.asset = asset
        super().__init__(f'"{asset.asset_tag}" was just assigned to someone else — please refresh and try again.')


def assign_asset(
    *, asset: Asset, employee, assigned_date, condition_at_assignment,
    expected_return_date=None, remarks: str = '', assigned_by, ip_address=None, source: str | None = None,
) -> AssetAssignment:
    """Create the assignment and mark the asset Assigned. Raises AssetNotAvailable / AssetAssignConflict."""
    try:
        with transaction.atomic():
            # Re-check status inside the transaction (SELECT ... FOR
            # UPDATE) — the partial unique constraint on AssetAssignment
            # is the ultimate DB-level guard against a race here, but
            # locking the Asset row too keeps the "already assigned"
            # error message accurate rather than surfacing a raw
            # IntegrityError to the caller under concurrent requests.
            asset = Asset.objects.select_for_update().select_related('branch').get(pk=asset.pk)
            if asset.status != Asset.STATUS_AVAILABLE:
                raise AssetNotAvailable(asset)

            assignment = AssetAssignment.objects.create(
                asset=asset,
                employee=employee,
                assigned_date=assigned_date,
                condition_at_assignment=condition_at_assignment,
                expected_return_date=expected_return_date,
                assign_remarks=remarks or '',
                assigned_by=assigned_by,
            )
            asset.status = Asset.STATUS_ASSIGNED
            asset.condition = condition_at_assignment
            asset.save(update_fields=['status', 'condition', 'updated_at'])
    except IntegrityError:
        raise AssetAssignConflict(asset)

    changes = {'asset_tag': asset.asset_tag, 'employee': employee.full_name}
    if source:
        changes['source'] = source
    AuditLog.objects.create(
        user=assigned_by, action='asset_assigned', module='assets',
        object_id=str(assignment.pk), changes=changes,
        branch=asset.branch.branch_name, ip_address=ip_address,
    )
    logger.info('Asset %s assigned to %s by %s', asset.asset_tag, employee.email, assigned_by.email)
    return assignment
