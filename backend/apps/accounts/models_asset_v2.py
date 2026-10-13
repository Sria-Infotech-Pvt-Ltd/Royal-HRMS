"""
Phase 8B Task F — an asset master (`Asset`) + allocation history
(`AssetAllocation`), separate from `CompanyAsset` (the existing
allocation-only row, kept populated for compatibility). Each `CompanyAsset`
migrates into one `Asset` + one `AssetAllocation` (dates/condition
preserved) — see services_asset_v2.migrate_company_asset().

Scoped down: no asset requests/fulfilment-checklist-task wiring (Task
F.3), no warranty/expiry reminder events (Task F.5), no depreciated-
recovery-value rule table (Task F.4's own "owner to configure" —
recovery_amount defaults to 0, exactly as the master prompt specifies).
"""
import uuid

from django.db import models


class Asset(models.Model):
    STATUS_IN_STOCK   = 'in_stock'
    STATUS_ALLOCATED  = 'allocated'
    STATUS_UNDER_REPAIR = 'under_repair'
    STATUS_RETIRED    = 'retired'
    STATUS_LOST       = 'lost'
    STATUS_CHOICES = [
        (STATUS_IN_STOCK, 'In stock'), (STATUS_ALLOCATED, 'Allocated'),
        (STATUS_UNDER_REPAIR, 'Under repair'), (STATUS_RETIRED, 'Retired'), (STATUS_LOST, 'Lost'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_tag = models.CharField(max_length=100, unique=True)
    category_code = models.CharField(max_length=40, help_text='Migrated from CompanyAsset.asset_type — see services_asset_v2.')
    model_name = models.CharField(max_length=200, blank=True)
    serial_number = models.CharField(max_length=200, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Field-secured by the view layer — not masked by this model.')
    vendor = models.CharField(max_length=200, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_STOCK)
    condition_code = models.CharField(max_length=20, blank=True, help_text='Migrated from CompanyAsset.condition.')
    legacy_company_asset = models.OneToOneField('accounts.CompanyAsset', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_v2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_assets_v2'
        ordering = ['asset_tag']

    def __str__(self):
        return self.asset_tag


class AssetAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='allocations')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='asset_allocations')
    issued_at = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    condition_at_issue = models.CharField(max_length=20, blank=True)
    condition_at_return = models.CharField(max_length=20, blank=True)
    acknowledged_by_employee_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_allocations_issued')
    received_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_allocations_received')
    recovery_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Unreturned/damaged recovery at exit — default 0 until an owner-configured depreciation rule exists.')

    class Meta:
        db_table = 'accounts_asset_allocations_v2'
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.asset_id} -> {self.employee_id}'

    @property
    def is_active(self) -> bool:
        return self.returned_at is None
