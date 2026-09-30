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
    category   = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=100)
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
