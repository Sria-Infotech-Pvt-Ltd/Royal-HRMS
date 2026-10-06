# `platform_core` — reference

The `backend/apps/platform_core` app is the metadata-driven platform layer
built across Phase 1 (geography/currency, lookups, legal entities, change
history, number series, feature flags) and Phase 2 (fields, forms, custom
objects, generic data API, list views, attachments, import/export, the
onboarding mirror). This doc was not written in Phase 1 (flagged there as a
small gap); this version covers both phases as they stand today.

See `PHASE1_REPORT.md` and `PHASE2_REPORT.md` for the full task-by-task
narrative and the bugs found/fixed along the way; this doc is the shorter
"what exists and where" reference for someone picking up the next phase.

## Models, by file

- `models/phase1.py` — `Currency`, `Timezone`, `Country`, `ExchangeRate`,
  `LookupType`, `LookupValue`, `Translation`, `LegalEntity`,
  `EntityIdentifier`, `EntityBankAccount`, `AuthorisedSignatory`,
  `ChangeHistory`, `NumberSeries`, `FeatureFlag`, `FeatureFlagOverride`,
  `ModuleToggle`, `SeedRecord`.
- `models/fields.py` — `EntityDefinition`, `FieldDefinition`,
  `FieldValueUniqueness`.
- `models/forms.py` — `FormLayout`, `FormStep`, `FormSection`,
  `FormFieldPlacement`.
- `models/custom_objects.py` — `CustomRecord`.
- `models/lists.py` — `ListViewDefinition`.
- `models/attachments.py` — `AttachmentValue`.
- `models/imports.py` — `ImportJob`, `ExportJob`.

## Services, by file

- `services_geo.py` — currency conversion.
- `services_lookups.py` — the ONE place to validate/resolve a value
  against a `LookupType`; never query `LookupValue` directly.
- `services_numbering.py` — `allocate()`/`preview()`, concurrency-safe via
  `select_for_update()`.
- `services_flags.py` — `is_enabled(code, user=, legal_entity=)`,
  `is_module_enabled()`.
- `services_conditions.py` — the declarative `{"all"|"any": [...]}`
  evaluator. **Read `docs/CONDITIONS.md` before using `required_when`** —
  an empty condition evaluates `True` by design, which is the wrong
  default for "is this required," not just "is this visible."
- `services_datatypes.py` — one validator+normaliser per data type, in a
  registry (`_VALIDATORS`).
- `services_attributes.py` — `validate()`/`save()`/`read()` for custom
  attribute values on ANY entity (core or custom) with an
  `attributes_column`. The one place every caller must go through — never
  manipulate a JSONB attributes column directly.
- `services_forms.py` — `resolve_layout()`/`validate_submission()`.
- `services_custom_objects.py` — `create_record()`/`update_record()`/
  `soft_delete_record()`/`list_records()`/`read_record()`/`publish_entity()`.
  `permission_codename(entity_code, action)` is the ONLY correct way to
  build a custom entity's permission codename — this codebase's
  `core.permissions.has_perm()` checks `apps.accounts.models.Permission` +
  `RolePermission`, NOT Django's built-in auth `Permission` app (a real bug
  this phase found and fixed — see `PHASE2_REPORT.md` bug #3).
- `services_list_views.py` — `resolve_default_view()` (personal > role >
  system), `validate_columns()`, `execute_custom_entity_query()`.
- `services_import_export.py` — `generate_import_template()`,
  `validate_job()`, `commit_job()`, `rollback_job()`,
  `export_rows_to_xlsx()` (formula-injection-safe — `escape_formula()`).
- `services_onboarding_sync.py` — write-through mirror of the legacy
  onboarding config onto the new engine, behind `forms.v2`.

## Registry

`registry.py` + `management/commands/sync_entity_registry.py` (run
automatically on `post_migrate`) register and keep in sync the 6 built-in
core entities: `employee`, `branch`, `org_unit`, `position`, `legal_entity`,
`candidate`. The **employee** entity's `attributes_column` is the dotted
path `"profile__custom_field_values"` — it reuses `EmployeeProfile`'s
existing JSON column rather than adding a second one or moving data; every
other core entity has a plain `attributes` JSONB column added directly to
its table.

## API surface

All endpoints live under `/api/v1/platform/` (see `urls.py`), split across
`views.py` (Phase 1: geography, lookups, legal entities, number series,
feature flags, change history), `views_meta.py` (entity/field/layout admin
CRUD + the generic custom-record data API), `views_list_views.py`,
`views_attachments.py`, `views_import_export.py`. Every endpoint follows
the existing `core.responses.success()/error()` envelope and
`core.pagination.paginate()`/`paginated_data()` shape — no second response
convention was introduced anywhere in this app.

## Known limitations (as of Phase 2)

- Core-entity attribute read/write has no generic endpoint — each core
  entity's own existing views are the only path (Task F decision).
- Core-entity attachments are gated by `settings.edit` only (no per-entity
  attachment permission yet — Task H).
- Import/export execution is synchronous, not Celery (Task I).
- Rollback only undoes newly-created records, never update/upsert changes
  (Task I — `ChangeHistory` doesn't retain old values yet).
- The onboarding mirror (`forms.v2`) covers `OnboardingFieldConfig`/
  `OnboardingSection` only, not education/experience/document configs
  (Task J), and is OFF by default — nothing renders from it yet.
- `actor_id` in `request_context` is not reliably populated (Phase 1,
  unresolved) — DRF resolves `request.user` after Django's own middleware
  stack runs.

## Where to look for existing data this app models

Company/legal-entity cutover, Country/Currency pilot-field cutover, and the
NumberSeries employee-code cutover are all tracked in
`docs/MIGRATION_PLAN.md`, not here — this doc covers the engine, that one
tracks the live-data migration state.
