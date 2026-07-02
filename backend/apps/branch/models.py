import uuid

from django.conf import settings
from django.db import models


class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'branch_states'
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'branch_cities'
        ordering = ['name']
        unique_together = ('name', 'state')

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Branch(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    branch_code = models.CharField(max_length=20, unique=True)
    branch_name = models.CharField(max_length=200)
    address = models.TextField()
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='branches')
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='branches')
    employees_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_headquarter = models.BooleanField(default=False)

    # ── Geofencing ────────────────────────────────────────────────────────────
    latitude = models.DecimalField(
        max_digits=12, decimal_places=8,
        null=True, blank=True,
        help_text='Office GPS latitude. Required when geofencing_enabled is True.',
    )
    longitude = models.DecimalField(
        max_digits=12, decimal_places=8,
        null=True, blank=True,
        help_text='Office GPS longitude. Required when geofencing_enabled is True.',
    )
    allowed_radius_meters = models.PositiveIntegerField(
        default=150,
        help_text='Geofence radius in metres. Punches outside this radius are rejected.',
    )
    geofencing_enabled = models.BooleanField(
        default=False,
        help_text=(
            'When True, employees must be within allowed_radius_meters of the branch '
            'coordinates to record an office punch. Requires latitude + longitude to be set.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'branch_branches'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch_name'], name='branch_name_idx'),
            models.Index(fields=['status'],      name='branch_status_idx'),
        ]

    def __str__(self):
        return f"{self.branch_code} - {self.branch_name}"

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class EmployeeBranchAccess(models.Model):
    """
    Grants an employee access to punch in from a specific branch.

    Most employees have a single branch (from User.branch CharField) and do not
    need a record here.  Add rows for HR, IT Support, Management, and Regional
    Managers who work across multiple locations.  The geofencing service checks
    this table first; if records exist it validates against all listed branches
    instead of just the employee's primary branch.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='branch_access',
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='employee_access',
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="True if this is the employee's home branch.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_branch_access'
        unique_together = ('employee', 'branch')
        ordering = ['-is_primary', 'branch__branch_name']

    def __str__(self):
        label = 'primary' if self.is_primary else 'secondary'
        return f'{self.employee} → {self.branch} ({label})'
