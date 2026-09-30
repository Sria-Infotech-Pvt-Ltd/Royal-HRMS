"""
Company asset inventory + assignment history.

Tenant-isolated the same way every other TENANT_APP model is (schema-per-
company via django-tenants — see config/settings.py TENANT_APPS) — no
explicit company FK needed, matching Department/Designation/Branch.
"""
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class AssetCategory(models.Model):
    """Asset Category master data — mirrors apps.accounts.models.Department's
    exact shape (name unique, is_active, no branch scoping — company-wide)."""

    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets_category'
        ordering = ['name']
        verbose_name_plural = 'Asset Categories'

    def __str__(self) -> str:
        return self.name


class AssetType(models.Model):
    """Asset Type master data — mirrors Designation's exact shape (name +
    parent FK unique together, is_active)."""

    name = models.CharField(max_length=100)
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, related_name='asset_types')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets_type'
        ordering = ['name']
        unique_together = ('name', 'category')

    def __str__(self) -> str:
        return f'{self.name} ({self.category.name})'


class Asset(models.Model):
    """One row per physical company asset (laptop, phone, furniture, ...)."""

    STATUS_AVAILABLE    = 'available'
    STATUS_ASSIGNED      = 'assigned'
    STATUS_UNDER_REPAIR  = 'under_repair'
    STATUS_LOST          = 'lost'
    STATUS_DAMAGED       = 'damaged'
    STATUS_RETIRED       = 'retired'
    STATUS_DISPOSED      = 'disposed'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE,   'Available'),
        (STATUS_ASSIGNED,    'Assigned'),
        (STATUS_UNDER_REPAIR, 'Under Repair'),
        (STATUS_LOST,        'Lost'),
        (STATUS_DAMAGED,     'Damaged'),
        (STATUS_RETIRED,     'Retired'),
        (STATUS_DISPOSED,    'Disposed'),
    ]

    CONDITION_NEW     = 'new'
    CONDITION_GOOD    = 'good'
    CONDITION_FAIR    = 'fair'
    CONDITION_DAMAGED = 'damaged'
    CONDITION_CHOICES = [
        (CONDITION_NEW,     'New'),
        (CONDITION_GOOD,    'Good'),
        (CONDITION_FAIR,    'Fair'),
        (CONDITION_DAMAGED, 'Damaged'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    asset_tag  = models.CharField(max_length=50, unique=True)
    asset_name = models.CharField(max_length=150)
    # Stores the AssetCategory/AssetType NAME (e.g. "IT Equipment", "Laptop",
    # or "Other") — kept as plain CharFields rather than FKs deliberately:
    # converting them would require a data migration re-mapping every
    # existing asset's free-text value, which isn't genuinely required just
    # to add master-data-backed dropdowns/validation going forward. The
    # AssetCategory/AssetType tables below are the source of truth for what
    # a NEW value must match; existing rows keep whatever string they
    # already had (see AssetSerializer.validate — unchanged-on-update values
    # are exempt from the master-data check for exactly this reason).
    category   = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=100)
    # Populated only when category/asset_type == "Other" — the standard
    # master value ("Other") is never overwritten with free text; the
    # custom text goes here instead (see spec: "Do not replace the master
    # value with arbitrary user text").
    category_other   = models.CharField(max_length=100, blank=True, default='')
    asset_type_other = models.CharField(max_length=100, blank=True, default='')
    brand      = models.CharField(max_length=100, blank=True, default='')
    # Django reserves no special meaning for a field literally named "model" —
    # matches the spec's own field name exactly, no clash with Meta.model etc.
    model      = models.CharField(max_length=100, blank=True, default='')
    # null=True (not just blank) so multiple assets with no serial number
    # don't collide against each other under the unique constraint — Postgres
    # (and Django) treat NULL as distinct from every other NULL for
    # uniqueness purposes, unlike empty string.
    serial_number = models.CharField(max_length=100, null=True, blank=True, unique=True)

    purchase_date  = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    vendor = models.CharField(max_length=150, blank=True, default='')

    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date   = models.DateField(null=True, blank=True)

    # PROTECT — same "cannot delete if referenced" convention Department
    # uses (there via active-employee count, here via the DB FK itself,
    # since every asset must always belong to exactly one branch).
    branch = models.ForeignKey(
        'branch.Branch', on_delete=models.PROTECT, related_name='assets',
    )

    status    = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=CONDITION_NEW)

    description = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assets_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets_asset'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='asset_status_idx'),
            models.Index(fields=['branch', 'status'], name='asset_branch_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.asset_tag} — {self.asset_name}'


class AssetAssignment(models.Model):
    """
    One row per assign-return lifecycle. Never updated after return except
    to fill in the return_* fields — never deleted, so this table is the
    asset's (and the employee's) full assignment history by construction.
    """

    STATUS_ASSIGNED = 'assigned'
    STATUS_RETURNED = 'returned'
    STATUS_CHOICES = [
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_RETURNED, 'Returned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    asset    = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asset_assignments',
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ASSIGNED)

    assigned_date           = models.DateField()
    condition_at_assignment = models.CharField(max_length=20, choices=Asset.CONDITION_CHOICES)
    expected_return_date    = models.DateField(null=True, blank=True)
    assign_remarks          = models.TextField(blank=True, default='')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asset_assignments_made',
    )

    return_date      = models.DateField(null=True, blank=True)
    return_condition = models.CharField(max_length=20, choices=Asset.CONDITION_CHOICES, blank=True, default='')
    return_reason    = models.TextField(blank=True, default='')
    return_remarks   = models.TextField(blank=True, default='')
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asset_returns_processed',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets_assignment'
        ordering = ['-assigned_date', '-created_at']
        indexes = [
            models.Index(fields=['employee', '-assigned_date'], name='assetassign_emp_date_idx'),
            models.Index(fields=['asset', 'status'], name='assetassign_asset_status_idx'),
        ]
        constraints = [
            # DB-level backstop (not just an application-level check) against
            # ever assigning an already-assigned asset to a second employee —
            # a partial unique index means at most one STATUS_ASSIGNED row
            # per asset can exist at a time, closing the race-condition gap
            # a plain "check then create" application check alone would leave.
            models.UniqueConstraint(
                fields=['asset'],
                condition=models.Q(status='assigned'),
                name='unique_active_assignment_per_asset',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.asset.asset_tag} -> {self.employee.full_name} ({self.status})'


class AssetMaintenanceRecord(models.Model):
    """
    One row per maintenance/repair cycle — a SEPARATE history table from
    AssetAssignment (not extra columns on it), the same way AssetAssignment
    is its own table rather than extra columns on Asset: a laptop can go
    through many assign/return cycles AND, independently, many repair
    cycles over its life, and each needs its own append-only history.
    Never deleted; only ever completed (fills in the completed_* fields).
    """

    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED,   'Completed'),
    ]

    OUTCOME_REPAIRED       = 'repaired'
    OUTCOME_NOT_REPAIRABLE = 'not_repairable'
    OUTCOME_CHOICES = [
        (OUTCOME_REPAIRED,       'Repaired'),
        (OUTCOME_NOT_REPAIRABLE, 'Not Repairable'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_records')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)

    # ── Opened (Send to Maintenance) ──
    maintenance_start_date   = models.DateField()
    # Named "issue" (not "reason") — deliberately distinct from
    # AssetAssignment.return_reason (why it came back) vs. this (what's
    # actually wrong with it), even though both were flagged 'damaged'.
    issue                     = models.TextField()
    expected_completion_date = models.DateField(null=True, blank=True)
    vendor                    = models.CharField(max_length=150, blank=True, default='')
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    notes = models.TextField(blank=True, default='')
    sent_to_maintenance_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asset_maintenance_sent',
    )

    # ── Closed (Complete Maintenance) — all blank/null until completed ──
    # "_date" (not "_at") matches this app's own convention for a plain
    # user-entered date (assigned_date, return_date, ...) vs. "_at" for an
    # automatic DateTimeField (created_at/updated_at below).
    completed_date    = models.DateField(null=True, blank=True)
    outcome            = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True, default='')
    maintenance_notes = models.TextField(blank=True, default='')
    actual_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='asset_maintenance_completed',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets_maintenance_record'
        ordering = ['-maintenance_start_date', '-created_at']
        indexes = [
            models.Index(fields=['asset', 'status'], name='assetmaint_asset_status_idx'),
        ]
        constraints = [
            # Same belt-and-suspenders pattern as
            # unique_active_assignment_per_asset above — the application-level
            # check (asset.status must be 'damaged' to send to maintenance)
            # is the primary guard; this closes the race-condition gap it
            # alone would leave, and directly satisfies "prevent duplicate
            # active maintenance records for the same asset."
            models.UniqueConstraint(
                fields=['asset'],
                condition=models.Q(status='in_progress'),
                name='unique_active_maintenance_per_asset',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.asset.asset_tag} maintenance ({self.status})'
