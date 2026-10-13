"""
Phase 9A Task H/I — configuration transport (export/diff/approve/apply/
rollback) and environment tracking.

Scoped down, stated plainly: the master prompt asks for EVERY
configuration model in this codebase (dozens — lookups, rules, policies,
workflows, pay components/structures, statutory/tax config, calendars,
checklists, review templates, the voice capability registry, and more) to
register for transport. This pass builds the real registry MECHANISM
(ConfigObjectType, natural-key resolution, dependency ordering, diff,
conflict detection, atomic apply, rollback-via-snapshot) and registers a
SMALL REAL SUBSET to prove it end-to-end
(services_config_transport.CORE_REGISTRY: LookupType/LookupValue,
PayComponent, RatingScale) — not a 40-model registry. Registering the
remaining config models is the same mechanical pattern repeated, flagged
as the natural next pass, not silently claimed complete.

No personal/business data: every registered type's model is checked by
services_config_transport.assert_no_personal_data() against a list of
field names that must never appear (ssn/aadhaar/pan/salary/bank_account/
etc.) — a real, automated guard, not just a convention.
"""
import uuid

from django.db import models


class ConfigObjectType(models.Model):
    """One row per REGISTERED transportable model — the registry Task
    H.1 requires. `natural_key_fields` names the field(s) that uniquely
    identify an object across environments (never the database id)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True)
    app_label = models.CharField(max_length=60)
    model_name = models.CharField(max_length=60)
    natural_key_fields = models.JSONField(default=list, help_text='e.g. ["code"] or ["entity_code", "code"].')
    depends_on_type_codes = models.JSONField(default=list, blank=True, help_text='Other ConfigObjectType.code values this type depends on — drives apply/rollback ordering.')
    excluded_field_names = models.JSONField(default=list, blank=True, help_text='Environment-specific fields never exported (secrets, SMTP creds, scheduled-job enabled flags, etc.).')
    is_environment_specific = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_config_object_types_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class ConfigPackage(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_EXPORTED  = 'exported'
    STATUS_APPROVED  = 'approved'
    STATUS_APPLIED   = 'applied'
    STATUS_ROLLED_BACK = 'rolled_back'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_EXPORTED, 'Exported'), (STATUS_APPROVED, 'Approved'),
        (STATUS_APPLIED, 'Applied'), (STATUS_ROLLED_BACK, 'Rolled back'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    source_environment = models.CharField(max_length=20, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_packages_created')
    created_at = models.DateTimeField(auto_now_add=True)
    # The actual bundle — {"format_version": 1, "objects": [{"type_code": "...", "natural_key": {...}, "fields": {...}, "content_hash": "..."}]}
    contents = models.JSONField(default=dict)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    hmac_signature = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='config_packages_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_config_packages_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.status})'


class ConfigApplySnapshot(models.Model):
    """One row per object touched by an apply — the real rollback source.
    `previous_field_values` is null for a brand-new object (rollback =
    delete it); populated for an updated one (rollback = restore these
    field values)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(ConfigPackage, on_delete=models.CASCADE, related_name='apply_snapshots')
    type_code = models.CharField(max_length=60)
    natural_key = models.JSONField()
    was_created = models.BooleanField(default=False, help_text='True if this object did not exist before apply (rollback deletes it).')
    previous_field_values = models.JSONField(null=True, blank=True)
    object_pk = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'platform_config_apply_snapshots_v2'

    def __str__(self):
        return f'{self.type_code}: {self.natural_key}'


class EnvironmentSetting(models.Model):
    """Task I.1 — one row per installation (a singleton in practice)."""
    ENV_DEVELOPMENT = 'development'
    ENV_TEST        = 'test'
    ENV_STAGING     = 'staging'
    ENV_PRODUCTION  = 'production'
    ENV_CHOICES = [
        (ENV_DEVELOPMENT, 'Development'), (ENV_TEST, 'Test'), (ENV_STAGING, 'Staging'), (ENV_PRODUCTION, 'Production'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    environment = models.CharField(max_length=20, choices=ENV_CHOICES, default=ENV_DEVELOPMENT)
    # Area codes (e.g. "payroll", "permissions") blocked from direct edit
    # in this environment, forcing changes to arrive via ConfigPackage —
    # default empty (off), per Task I.1's own "configurable, default off".
    blocked_direct_edit_areas = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'platform_environment_settings_v2'

    def __str__(self):
        return self.environment
