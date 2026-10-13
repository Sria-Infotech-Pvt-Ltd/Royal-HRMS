"""Phase 8B gap-closure — asset requests, warranty reminders, a depreciation rule table for exit recovery."""
import uuid

from django.db import models


class AssetRequest(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_APPROVED  = 'approved'
    STATUS_REJECTED  = 'rejected'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'), (STATUS_FULFILLED, 'Fulfilled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='asset_requests')
    category_code = models.CharField(max_length=40)
    justification = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_requests_approved')
    fulfilled_allocation = models.ForeignKey('accounts.AssetAllocation', on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_request')
    # The 8A checklist task type the fulfilment goes to (IT/admin) —
    # linked, not duplicated: see services_asset_v2b.create_fulfilment_task().
    checklist_task = models.ForeignKey('hrms.ChecklistTaskInstance', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_request')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_asset_requests_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee_id}: {self.category_code} ({self.status})'


class AssetDepreciationRule(models.Model):
    """Depreciated value by age — 'owner to configure', per the master
    prompt's own words; a row's absence for a category means "no recovery
    amount" (the documented default), never an invented rate."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category_code = models.CharField(max_length=40, unique=True)
    # [{"max_age_months": 12, "recovery_percent": 80}, {"max_age_months": 24, "recovery_percent": 50}, ...]
    # — first matching band (by age) wins; no match = 0 recovery.
    age_bands = models.JSONField(default=list)

    class Meta:
        db_table = 'accounts_asset_depreciation_rules_v2'

    def __str__(self):
        return f'Depreciation: {self.category_code}'
