"""
Platform Core — Phase 1 foundations (geography/currency masters, lookup
engine, legal entity, generic change history, number series, feature
flags). See PHASE1_REPORT.md for what each model is for and why.

Every model here follows the same base-field convention already used
throughout this codebase (is_active, created_at, updated_at) rather than
inventing a new one.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ─── Task C — Geography & currency masters ─────────────────────────────────

class Currency(TimestampedModel):
    """ISO 4217. Seeded by the core_geo seed pack from an authoritative
    source (pycountry) — never hand-typed."""
    code        = models.CharField(max_length=3, unique=True)  # e.g. 'INR'
    name        = models.CharField(max_length=100)
    symbol      = models.CharField(max_length=10, blank=True)
    minor_units = models.PositiveSmallIntegerField(default=2)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_currencies'
        ordering = ['code']
        verbose_name_plural = 'currencies'

    def __str__(self):
        return self.code


class Timezone(TimestampedModel):
    """IANA timezone name, e.g. 'Asia/Kolkata' — seeded from Python's own
    zoneinfo.available_timezones(), not a hand-typed subset."""
    name      = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_timezones'
        ordering = ['name']

    def __str__(self):
        return self.name


class Country(TimestampedModel):
    """ISO 3166-1. Seeded by the core_geo seed pack from pycountry."""
    iso2             = models.CharField(max_length=2, unique=True)
    iso3             = models.CharField(max_length=3, unique=True)
    numeric_code     = models.CharField(max_length=3, blank=True)
    name             = models.CharField(max_length=150)
    phone_code       = models.CharField(max_length=10, blank=True)
    default_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, null=True, blank=True, related_name='countries')
    default_timezone = models.ForeignKey(Timezone, on_delete=models.PROTECT, null=True, blank=True, related_name='countries')
    date_format      = models.CharField(max_length=20, default='DD/MM/YYYY')
    # Filled in Phase 5 (structured addresses) — deliberately empty for now,
    # not guessed at, per the Master Prompt's "don't invent legal/statutory
    # rules" rule.
    address_format   = models.JSONField(default=dict, blank=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_countries'
        ordering = ['name']
        verbose_name_plural = 'countries'

    def __str__(self):
        return self.name


class ExchangeRate(TimestampedModel):
    """Admin-entered only in this phase — no external feed. convert() in
    services_geo.py uses the latest rate on or before the requested date."""
    from_currency  = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='rates_from')
    to_currency    = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='rates_to')
    rate           = models.DecimalField(max_digits=20, decimal_places=8)
    effective_date = models.DateField()
    source         = models.CharField(max_length=100, blank=True, help_text='e.g. "manual", "RBI reference rate"')

    class Meta:
        db_table = 'platform_exchange_rates'
        ordering = ['-effective_date']
        constraints = [
            models.UniqueConstraint(
                fields=['from_currency', 'to_currency', 'effective_date'],
                name='uniq_exchange_rate_per_day',
            ),
        ]

    def __str__(self):
        return f'{self.from_currency_id}->{self.to_currency_id} @ {self.effective_date} = {self.rate}'


# ─── Task D — Lookup engine ─────────────────────────────────────────────────

class LookupType(TimestampedModel):
    code               = models.CharField(max_length=64, unique=True, help_text='UPPER_SNAKE, e.g. GENDER')
    name               = models.CharField(max_length=150)
    description        = models.TextField(blank=True)
    module             = models.CharField(max_length=50, blank=True, help_text='Which app/domain owns this, e.g. "accounts"')
    is_system          = models.BooleanField(default=False, help_text='Type itself cannot be deleted (values still can be added if allow_custom_values).')
    allow_custom_values = models.BooleanField(default=True)
    is_hierarchical    = models.BooleanField(default=False)
    attribute_schema   = models.JSONField(default=dict, blank=True, help_text='JSON Schema validating LookupValue.attributes for this type.')

    class Meta:
        db_table = 'platform_lookup_types'
        ordering = ['code']

    def __str__(self):
        return self.code


class LookupValue(TimestampedModel):
    lookup_type    = models.ForeignKey(LookupType, on_delete=models.CASCADE, related_name='values')
    code           = models.CharField(max_length=64, help_text='UPPER_SNAKE, immutable once referenced by any record.')
    label          = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    sort_order     = models.PositiveIntegerField(default=0)
    parent         = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    attributes     = models.JSONField(default=dict, blank=True)
    is_default     = models.BooleanField(default=False)
    is_active      = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to   = models.DateField(null=True, blank=True)
    # null = global / applies everywhere.
    country        = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='lookup_values')
    legal_entity   = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='lookup_values')
    is_system      = models.BooleanField(default=False, help_text='Seeded value — label editable, code is not, cannot be deleted (only deactivated).')

    class Meta:
        db_table = 'platform_lookup_values'
        ordering = ['lookup_type', 'sort_order', 'label']
        constraints = [
            models.UniqueConstraint(fields=['lookup_type', 'code'], name='uniq_lookup_value_code_per_type'),
        ]

    def __str__(self):
        return f'{self.lookup_type_id}:{self.code}'


class Translation(TimestampedModel):
    """Generic label translation for any object (initially: LookupValue
    labels). `language` is a BCP-47 tag, e.g. 'en', 'hi', 'te'."""
    app_label  = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id  = models.CharField(max_length=64)
    field      = models.CharField(max_length=64)
    language   = models.CharField(max_length=10)
    text       = models.TextField()

    class Meta:
        db_table = 'platform_translations'
        constraints = [
            models.UniqueConstraint(
                fields=['app_label', 'model_name', 'object_id', 'field', 'language'],
                name='uniq_translation_target',
            ),
        ]

    def __str__(self):
        return f'{self.model_name}.{self.object_id}.{self.field}[{self.language}]'


# ─── Task E — Legal entity foundation ──────────────────────────────────────

class LegalEntity(TimestampedModel):
    """Replaces the Company singleton. Phase 1 scope: master data only —
    no business data (payroll, employees-as-of-entity, etc.) is filtered by
    this yet. See PHASE1_REPORT.md 'Limitations'."""
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code            = models.CharField(max_length=30, unique=True)
    legal_name      = models.CharField(max_length=255)
    trade_name      = models.CharField(max_length=255, blank=True)

    country         = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='legal_entities')
    base_currency   = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name='legal_entities')
    timezone        = models.ForeignKey(Timezone, on_delete=models.PROTECT, related_name='legal_entities')
    date_format     = models.CharField(max_length=20, default='DD/MM/YYYY')
    financial_year_start_month = models.PositiveSmallIntegerField(default=4)

    # Lookup codes, not FK — these are LookupType ENTITY_TYPE / INDUSTRY /
    # MSME_CLASS / JURISDICTION values (Task D), kept as plain codes here so
    # this model doesn't need to know which LookupType row backs each one.
    entity_type     = models.CharField(max_length=64, blank=True)
    industry        = models.CharField(max_length=64, blank=True)
    msme_class      = models.CharField(max_length=64, blank=True)
    jurisdiction    = models.CharField(max_length=64, blank=True)

    date_of_incorporation = models.DateField(null=True, blank=True)
    is_listed             = models.BooleanField(default=False)
    holding_company_info  = models.TextField(blank=True)
    nature_of_business    = models.TextField(blank=True)
    nic_code              = models.CharField(max_length=20, blank=True)

    registered_address    = models.TextField(blank=True)
    communication_address = models.TextField(blank=True)

    primary_email   = models.EmailField(blank=True)
    website         = models.URLField(blank=True)
    official_phone  = models.CharField(max_length=20, blank=True)
    portal_url      = models.URLField(blank=True)
    logo            = models.ImageField(upload_to='legal_entity_logos/', null=True, blank=True)

    is_primary      = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=True)
    updated_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # Phase 2 — admin-added custom field values, written only through
    # services_attributes.py.
    attributes      = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'platform_legal_entities'
        ordering = ['code']
        verbose_name_plural = 'legal entities'
        constraints = [
            # Exactly one primary entity at a time — a partial unique index.
            models.UniqueConstraint(
                fields=['is_primary'],
                condition=models.Q(is_primary=True),
                name='uniq_primary_legal_entity',
            ),
        ]

    def __str__(self):
        return self.legal_name


class EntityIdentifier(TimestampedModel):
    """CIN/TAN/PAN/UDYAM/IEC/EPFO/ESIC/PT/EIN/etc — identifier_type is a
    LookupValue code under the ENTITY_IDENTIFIER_TYPE lookup type (seeded
    by india_core). Sensitive identifiers (PAN) are encrypted; see
    services_legal_entity.py for the encrypt-on-write path."""
    legal_entity     = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name='identifiers')
    identifier_type  = models.CharField(max_length=64)
    # Plain value for non-sensitive identifiers; for sensitive ones the
    # encrypted value lives in `value_encrypted` instead and this stays
    # blank — kept as two columns (rather than always-encrypt) so a report
    # listing e.g. CIN numbers doesn't need decrypt access at all.
    value            = models.CharField(max_length=255, blank=True)
    value_encrypted  = models.BinaryField(null=True, blank=True)
    value_hash       = models.CharField(max_length=64, blank=True, db_index=True, help_text='Blind index for sensitive identifiers — lookup without decrypting.')
    valid_from       = models.DateField(null=True, blank=True)
    valid_to         = models.DateField(null=True, blank=True)
    is_active        = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_entity_identifiers'
        constraints = [
            models.UniqueConstraint(
                fields=['legal_entity', 'identifier_type'],
                condition=models.Q(is_active=True),
                name='uniq_active_identifier_per_type',
            ),
        ]

    def __str__(self):
        return f'{self.legal_entity_id}:{self.identifier_type}'


class EntityBankAccount(TimestampedModel):
    legal_entity         = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name='bank_accounts')
    account_holder_name  = models.CharField(max_length=255, blank=True)
    account_number_encrypted = models.BinaryField(null=True, blank=True)
    account_number_hash  = models.CharField(max_length=64, blank=True, db_index=True)
    ifsc_encrypted       = models.BinaryField(null=True, blank=True)
    bank_name            = models.CharField(max_length=255, blank=True)
    branch_name          = models.CharField(max_length=255, blank=True)
    is_primary           = models.BooleanField(default=False)
    is_active            = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_entity_bank_accounts'

    def __str__(self):
        return f'{self.legal_entity_id} bank account ({self.bank_name})'


class AuthorisedSignatory(TimestampedModel):
    legal_entity    = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name='signatories')
    full_name       = models.CharField(max_length=255)
    designation     = models.CharField(max_length=150, blank=True)
    purpose         = models.CharField(max_length=64, blank=True, help_text='LookupValue code under SIGNATORY_PURPOSE, e.g. BANKING, STATUTORY.')
    din_pan_encrypted = models.BinaryField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_authorised_signatories'

    def __str__(self):
        return f'{self.full_name} ({self.legal_entity_id})'


# ─── Task F — Generic change history ───────────────────────────────────────

class ChangeHistory(models.Model):
    """Append-only. No update/delete is permitted through the ORM — see
    save()/delete() overrides and ChangeHistoryQuerySet below."""
    id            = models.BigAutoField(primary_key=True)
    occurred_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    actor         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='change_history_entries')
    channel       = models.CharField(max_length=20, default='ui', help_text='ui, api_key, system, import, voice, celery')
    request_id    = models.CharField(max_length=64, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.CharField(max_length=255, blank=True)

    content_type  = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    object_id     = models.CharField(max_length=64)
    object_repr   = models.CharField(max_length=200, blank=True)

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_DEACTIVATE = 'deactivate'
    ACTION_RESTORE = 'restore'
    ACTION_CUSTOM = 'custom'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'), (ACTION_UPDATE, 'Update'), (ACTION_DELETE, 'Delete'),
        (ACTION_DEACTIVATE, 'Deactivate'), (ACTION_RESTORE, 'Restore'), (ACTION_CUSTOM, 'Custom'),
    ]
    action        = models.CharField(max_length=20, choices=ACTION_CHOICES)
    changes       = models.JSONField(default=list, blank=True, help_text='[{field, old, new}] — sensitive values masked before storage.')
    reason        = models.TextField(blank=True)
    legal_entity  = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'platform_change_history'
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'occurred_at'], name='pch_object_idx'),
            models.Index(fields=['actor', 'occurred_at'], name='pch_actor_idx'),
        ]

    def __str__(self):
        return f'{self.action} {self.content_type_id}:{self.object_id} @ {self.occurred_at}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('ChangeHistory is append-only — it cannot be updated after creation.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('ChangeHistory is append-only — entries cannot be deleted.')


class ChangeHistoryQuerySet(models.QuerySet):
    def delete(self):
        raise ValueError('ChangeHistory is append-only — bulk delete is disabled.')

    def update(self, **kwargs):
        raise ValueError('ChangeHistory is append-only — bulk update is disabled.')


ChangeHistory.add_to_class('objects', ChangeHistoryQuerySet.as_manager())


# ─── Task G — Number-series engine ─────────────────────────────────────────

class NumberSeries(TimestampedModel):
    RESET_NEVER = 'never'
    RESET_YEARLY = 'yearly'
    RESET_FINANCIAL_YEAR = 'financial_year'
    RESET_MONTHLY = 'monthly'
    RESET_CHOICES = [
        (RESET_NEVER, 'Never'), (RESET_YEARLY, 'Yearly'),
        (RESET_FINANCIAL_YEAR, 'Financial year'), (RESET_MONTHLY, 'Monthly'),
    ]

    code          = models.CharField(max_length=100, unique=True)
    entity        = models.CharField(max_length=50, help_text='Target object type, e.g. "employee", "leave_request".')
    pattern       = models.CharField(
                        max_length=200, default='{PREFIX}{SEQ:5}',
                        help_text='Tokens: {PREFIX} {SEQ:n} {YYYY} {YY} {MM} {FY} {ENTITY} {BRANCH}',
                    )
    prefix        = models.CharField(max_length=20, blank=True)
    padding       = models.PositiveSmallIntegerField(default=5)
    next_value    = models.PositiveIntegerField(default=1)
    reset_period  = models.CharField(max_length=20, choices=RESET_CHOICES, default=RESET_NEVER)
    last_reset_key = models.CharField(max_length=20, blank=True)

    # Optional scope — e.g. one series per employment type, matching the
    # existing EmployeeCodeSeries behaviour exactly.
    legal_entity   = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='number_series')
    scope_key      = models.CharField(max_length=100, blank=True, help_text='e.g. employment_type code — free-form scope discriminator.')

    is_active      = models.BooleanField(default=True)
    priority       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'platform_number_series'
        ordering = ['entity', 'scope_key']

    def __str__(self):
        return self.code


# ─── Task H — Feature flags & module toggles ───────────────────────────────

class FeatureFlag(TimestampedModel):
    code        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    enabled     = models.BooleanField(default=False, help_text='Global default.')
    rollout_percentage = models.PositiveSmallIntegerField(default=100, help_text='Only applies when enabled=True and no override matches.')
    is_system   = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_feature_flags'
        ordering = ['code']

    def __str__(self):
        return self.code


class FeatureFlagOverride(TimestampedModel):
    flag         = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='overrides')
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    role         = models.ForeignKey('accounts.Role', on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    enabled      = models.BooleanField()

    class Meta:
        db_table = 'platform_feature_flag_overrides'

    def __str__(self):
        return f'{self.flag_id} override'


class ModuleToggle(TimestampedModel):
    """Stored + exposed by API only in Phase 1 — NOT enforced anywhere yet
    (enforcement is Phase 4). See Task H note in PHASE1_REPORT.md."""
    module       = models.CharField(max_length=50)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.CASCADE, related_name='module_toggles')
    enabled      = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_module_toggles'
        constraints = [
            models.UniqueConstraint(fields=['module', 'legal_entity'], name='uniq_module_toggle_per_entity'),
        ]

    def __str__(self):
        return f'{self.module}@{self.legal_entity_id}'


# ─── Task B — Seed-pack framework ───────────────────────────────────────────

class SeedRecord(TimestampedModel):
    """Tracks what a seed pack created/last-touched, so re-running a pack
    is idempotent and never clobbers an admin's own edit. See
    management/commands/load_seed_pack.py."""
    pack          = models.CharField(max_length=100)
    version       = models.CharField(max_length=20)
    content_type  = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    object_id     = models.CharField(max_length=64)
    checksum      = models.CharField(max_length=64, help_text='Hash of the seed-pack source row, to detect admin edits vs pack updates.')

    class Meta:
        db_table = 'platform_seed_records'
        constraints = [
            models.UniqueConstraint(fields=['pack', 'content_type', 'object_id'], name='uniq_seed_record_target'),
        ]

    def __str__(self):
        return f'{self.pack}:{self.content_type_id}:{self.object_id}'
