# Authorization engine (Phase 4)

Built additively alongside the existing `Role`/`Permission`/
`RolePermission`/`User.role`/`core.permissions.has_perm()` system, which
remains the **live, unchanged production path**. Nothing in this
document's engine is wired to replace it in this pass — see "What's NOT
wired" below and `PHASE4_REPORT.md` for the full reasoning.

## Why additive-only, again

Rule 3 of this phase is explicit: *"Access must not change for any user
when the new system is switched on with migrated data... prove it with
the parity harness."* Rule from Section 6: *"Do not approximate scope
behaviour you cannot reproduce exactly. Record it as an open question."*
Together these mean: replacing `has_perm()`, rewriting the ~442 call
sites, and running an empty-diff parity harness against real production
data is explicitly gated on doing that work *exactly*, not approximately
— and that work (tracing every one of ~442 call sites' current precise
behaviour) is this phase's single largest undertaking. Same discipline
as every prior phase's deferred live-data cutover (Company→LegalEntity,
attendance consolidation, approval migration): build the new engine for
real, prove it on a consequence-free surface, defer the risky cutover
explicitly rather than guess.

## What's built

### Task A — Permission registry
`apps/accounts/permissions_registry.py` auto-generates
`<entity>.view/create/edit/delete/export/import` permissions for every
registered CORE entity (custom-entity permissions are already created at
publish time by Phase 2's `services_custom_objects.publish_entity()` —
not duplicated). `sync_permissions` is idempotent, run on `post_migrate`.
`Permission` gained `description`/`is_sensitive`/`implies`/`is_deprecated`
fields (additive). **Not built**: automatic `is_deprecated` detection for
permissions no longer referenced anywhere — see "Deferred" below for why
a hand-maintained diff list was deliberately not built instead.
`tests_permission_registry.py` scans the live source tree for every
literal `has_perm('module.action')` call and asserts the codename exists
in the database — self-updating proof instead of a hand-maintained list.

### Task B — Role assignments
`RoleAssignment(user, role, scope_type, scope_values, legal_entity,
effective_from, effective_to, granted_by, reason, is_active)` — a user
may hold many; effective rights are the union (Task B.1). `User.role`
(unchanged) stays the primary role. `Role` gained `is_full_access`,
`is_default_employee_role` (DB-enforced "at most one" via a partial
unique constraint), `exclude_from_payroll`, `exclude_from_headcount`,
`is_assignable` — all 4 of the prompt's named hardcoded-role-name call
sites were actually replaced (not just modeled) — see the catalogue in
`PHASE4_REPORT.md`.

### Task C — Data-scope engine
`services_authz.scope_queryset(user, entity, action, queryset)` /
`can(user, entity, action, record)`. 12 scope types declared on
`RoleAssignment.SCOPE_CHOICES`; only `own`, `all`, `legal_entity`, and
`my_legal_entity` have a declared mapping for `CustomRecord` in this
pass (Task C.2's entity-scope mapping) — every other scope type
(`direct_reports`, `org_unit`, `branch`, `employee_group`, etc.) raises
or contributes nothing rather than silently matching everything/nothing,
per the "stop and record it" rule. **No core entity has a scope mapping
at all** — `scope_queryset()` raises `AuthzError` for a core entity,
rather than guessing. Proven against the Phase 2 "Vehicle Allocation"
custom entity.

**Real bug caught by the tests**: `SCOPE_ALL`'s filter was originally
expressed as an empty `Q()` folded into the union via `combined |= q`.
Django's `Q()` with no children is a no-op *identity element* when
combined with `|` — it does NOT mean "match everything" in that
position (that's only true when passed directly to `.filter(Q())`).
The union silently contributed *nothing* for an "everything" scope.
Fixed by short-circuiting `SCOPE_ALL` to return the full queryset
immediately, never folding it into the union at all.

### Task D — Explicit full-access attribute
`Role.is_full_access`, backfilled by migration `0181` to exactly the
role(s) holding `settings.edit` today (verified: 1 role,
`system_admin`). `services_authz.is_full_access(user)` /
`has_perm_v2(user, codename)` are the NEW engine's own checks — `core.
permissions.has_perm()` itself is untouched in this pass (the live
production path). A weekly report job listing full-access users/
superusers (Task D.4) was **not built** — would need a Phase 3B
notification rule + a scheduled job wired together, not attempted here.

### Task E — Field-level security
`FieldPermission(role, entity, field_code, access, condition,
effective_from, effective_to)` — `hidden`/`masked`/`read`/`edit`.
Sensitive fields (Phase 2's `FieldDefinition.is_sensitive`) default to
`masked` for every role unless explicitly granted otherwise (Task E.2).
`services_field_security.py`: `apply_field_security()` (hidden fields
dropped, masked fields replaced, writes to non-`edit` fields rejected),
`validate_filter_sort_fields()` (filtering/sorting by a hidden/masked
field raises, rather than silently no-op-ing — Task E.3's own
information-leak concern). `SensitiveFieldReadLog` (Task E.5 — who/when/
which record/which field, NEVER the value). **Not wired** into the
Phase 2 generic data API, exports, history views, search, or voice
responses in this pass — built and proven standalone.

### Task F — Segregation of duties
`SoDRule(code, conflicting_permissions_a, conflicting_permissions_b,
severity, is_suggestion, is_active)`. `services_sod.check()` — raises
`SoDBlockedError` for the first `block`-severity conflict; `warn`-
severity requires a `reason` to proceed. `existing_violations_report()`
— read-only, never auto-removes anything. 4 suggested rules seeded via
`seed_sod_rules`, **all `is_active=False`** pending explicit owner
confirmation (Task F.3's own instruction) — including a genuinely
block-severity one (bank-details-edit vs. payroll-edit).

### Task G — Module toggle enforcement
`services_module_enforcement.require_module_enabled(module,
legal_entity)` reuses Phase 1's `services_flags.is_module_enabled()`
(built, never enforced, until now). Chosen: **403, not 404** — a 404
would be indistinguishable from a genuinely missing resource, making an
admin's own toggle mistake harder to diagnose. **Not wired** into any
existing endpoint, menu metadata, scheduled job, or notification firing
— the primitive exists; the integration sweep across every module does
not.

### Task H — Admin tools
`services_authz_admin.py`: `who_can(codename)`, `what_can(user)`
(permissions + field access + assignments, each with its source),
`simulate(user, codename, entity=, record=)` (explicitly **no
impersonation** — never logs in as anyone, purely evaluates), `clone_role()`,
`compare_roles()`. Access review/recertification campaigns (Task H.5,
"use the Phase 3B workflow engine") — **not built**; would need a new
`WorkflowDefinition` wired to iterate every `RoleAssignment`, a
meaningfully larger undertaking than the other read-only tools above.

### Task I — Migration and parity harness
**Not executed.** See `PHASE4_REPORT.md`'s "Deferred" section — this is
the single largest, most consequential deferral in this phase, by design.

### Task J — Scoped external API keys
`ExternalAPIKey` gained `scope_codenames`, `legal_entity`,
`ip_allowlist` (CIDR, `allows_ip()` tested), `expires_at`
(`is_expired()`), `rotated_from`, `rate_limit_tier`. `APIKeyUsageLog`
(endpoint/status/timestamp/IP, never payloads). **Existing keys keep
working unrestricted** (`scope_codenames=[]` means "unrestricted," Task
J.2's exact requirement) — this phase deliberately did NOT attempt to
reverse-engineer which endpoints each existing key currently calls into
an equivalent scope set (see the model's own docstring for why: getting
that wrong either silently breaks or silently widens a live integration).
**Not wired** into the actual external-API request-handling path (no
view currently checks `allows_scope()`/`allows_ip()`/`is_expired()`).

### Task K — Performance
`services_authz.effective_permissions(user)` — cached via Phase 1's
versioned metadata-cache pattern (new `authz` namespace), invalidated on
any `RoleAssignment`/`FieldPermission`/`RolePermission` write. **Not
measured against the prompt's specific benchmark targets** (2,000
reports / 10 branches / 50,000 employees / 500,000 attendance rows) —
no dataset at that scale exists in this environment to benchmark
against honestly.

## What's NOT wired (the live production path, unchanged)

- `core.permissions.has_perm()` — still one query per call, still the
  `settings.edit` hidden bypass, exactly as before.
- Every one of the ~442 existing `has_perm()` call sites.
- `User.role` single-FK model — still the only role that matters to
  existing code.
- `EmployeeBranchAccess` — note, read during Phase 4's own fact-finding:
  its real current purpose is punch-in geofencing (per its own
  docstring: *"Grants an employee access to punch in from a specific
  branch"*), not the general multi-branch *data-access* scoping the
  prompt's Task I.1 assumes it feeds. A factual correction, not acted on
  further — flagged for whoever executes Task I.

## CI guard (Rule 5)

`scripts/check_no_permission_migrations.py` fails the build if any
migration file writes `RolePermission`/`Permission` rows outside a
frozen baseline of the 40 pre-Phase-4 migrations that already do this
(grep-verified at the time this check was written). Wired into
`.github/workflows/backend-tests.yml`.
