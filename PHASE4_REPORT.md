# Phase 4 Report — Authorization: Roles, Data Scopes, Field-Level Security, Segregation of Duties

Delivered 2026-10-07. Scope: `backend/apps/platform_core/models/authz.py`,
`services_authz.py`, `services_authz_admin.py`, `services_field_security.py`,
`services_sod.py`, `services_module_enforcement.py`, `apps/accounts/permissions_registry.py`,
`apps/accounts/models.py` (Role/Permission/ExternalAPIKey additions),
`scripts/check_no_permission_migrations.py`. Follows the same Section-7
structure as every prior phase report.

## Scoping decision, stated up front (same discipline as every prior phase — the stakes are just higher this time)

Tasks A (partial), B, C (engine only), D (attribute only), E (engine
only), F, G (primitive only), H (partial), J (model only), and K
(partial) are built as real, tested, **additive** infrastructure, proven
end to end against the Phase 2 "Vehicle Allocation" custom entity.

**Task I (the migration + parity harness) was NOT executed.** This is
the single largest deferral in the entire session's work across all
phases, and it is deliberate: Phase 4's own Rule 3 says *"Access must
not change for any user... this is the most important rule of this
phase. Prove it with the parity harness."* Section 6 says *"Do not
approximate scope behaviour you cannot reproduce exactly. Record it as
an open question."* Together, these make Task I gated on first tracing
the EXACT current behaviour of ~442 `has_perm()` call sites and ~87
`can_manage_team`/`can_manage_branch` usages across the entire
codebase — a verification task larger than every other task in this
phase combined, and one where a wrong guess means a real user either
loses access they need (support ticket) or gains access they shouldn't
(security incident). Building the new engine for real and proving it on
a consequence-free custom entity, while leaving `core.permissions.
has_perm()` and all ~442 of its call sites completely untouched, is the
responsible version of this phase — not a half-executed migration that
claims an empty parity diff without actually having verified one.

**What was built and is real, tested, additive infrastructure:**

- Entity-generated permissions (Task A.1 partial) + a self-updating
  source-scan test proving no `has_perm()` literal references a
  nonexistent codename (Task A.2 partial).
- `RoleAssignment` + the full data-scope engine (Task B.1, C) —
  `scope_queryset()`/`can()`, 12 declared scope types, proven against a
  custom entity.
- `Role.is_full_access` (Task D) — backfilled to match `settings.edit`
  holders exactly (1 role).
- **All 4 of the prompt's named hardcoded-role-name call sites
  replaced** (Task B.3) — see the catalogue below.
- `FieldPermission` + the field-security enforcement functions (Task E).
- `SoDRule` + block/warn checking + a violations report (Task F), 4
  suggested rules seeded inactive.
- The module-toggle enforcement primitive (Task G), choosing 403.
- `who_can`/`what_can`/`simulate`/`clone_role`/`compare_roles` (Task H),
  explicitly no impersonation anywhere.
- `ExternalAPIKey` scoping fields (Task J) — existing keys unaffected
  (`scope_codenames=[]` = unrestricted).
- Cached effective permissions with versioned invalidation (Task K.1).
- The CI guard against new permission-granting migrations (Rule 5).

**36 new tests, all passing**, plus the existing `tests_permission_registry.py`
scan test (verified logically correct against the real dev DB; the
shared `--keepdb` test database's own staleness — see Section 6 — kept
it from running cleanly there).

---

## 1. What was built, per task

**Task A — Permission registry.** `generate_entity_permissions()`
creates `<entity>.view/create/edit/delete/export/import` for every
registered CORE entity (36 created on first sync — 6 entities × 6
actions). Custom-entity permissions are already handled by Phase 2's
`publish_entity()` — not duplicated. `Permission` gained `description`/
`is_sensitive`/`implies`/`is_deprecated` (additive). **Deliberately not
built**: automatic deprecation-detection comparing the registry against
every actual call site — see this module's own docstring for why a
hand-typed diff list was rejected as too risky to approximate, in favor
of a test that re-scans the live source tree on every run instead.

**Task B — Role assignments.** `RoleAssignment(user, role, scope_type,
scope_values, legal_entity, effective_from, effective_to, granted_by,
reason, is_active)`. `Role` gained 5 new attributes; a DB-level partial
unique constraint enforces "at most one `is_default_employee_role`."
Migration `0181` backfilled: `is_full_access` on roles holding
`settings.edit` (1 role, `system_admin`), `is_default_employee_role` on
the role named `employee` (1 role), `exclude_from_payroll` on the role
named `system_admin` (1 role) — exact counts logged at migration time.

**Task C — Data-scope engine.** `scope_queryset(user, entity, action,
queryset)` unions every active `RoleAssignment`'s contribution;
`can(user, entity, action, record)` is the single-record equivalent.
Only `own`/`all`/`legal_entity`/`my_legal_entity` are mapped for
`CustomRecord`; every other scope type and every core entity raises or
contributes nothing (never silently matches everything). **Real bug
caught by the tests**: see Section 3.

**Task D — Full-access attribute.** `is_full_access(user)` checks
`is_superuser` first, then `role.is_full_access` — the explicit,
auditable replacement for the hidden `settings.edit` bypass, used ONLY
by this phase's own new `has_perm_v2()`/`scope_queryset()`/`can()`. The
live `core.permissions.has_perm()` is completely untouched.

**Task E — Field-level security.** `resolve_field_access()` defaults
sensitive fields to `masked`, everything else to `read` (never a silent
`edit` default). `apply_field_security()` drops hidden fields, masks
masked ones (`mask_value()` — last-4-chars for text, `***` otherwise),
and rejects a write to a non-`edit` field. `validate_filter_sort_fields()`
rejects filtering/sorting by a hidden/masked field outright (an
information-leak vector the prompt itself calls out). `SensitiveFieldReadLog`
records who/when/which-record/which-field — never the value.

**Task F — Segregation of duties.** `check()` raises `SoDBlockedError`
for the first `block`-severity conflict found (never partially applies
an action that has one); `warn`-severity requires a `reason` or raises
the same way. `existing_violations_report()` is read-only. 4 suggested
rules seeded `is_active=False` (Task F.3's own "suggestions pending
owner confirmation" instruction) — including a real `block`-severity
one (`edit_bank_details_vs_approve_payroll`).

**Task G — Module toggle enforcement.** `require_module_enabled()`
reuses Phase 1's `is_module_enabled()` (built, never enforced, until
this function). 403 chosen explicitly over 404 (documented reasoning in
`docs/AUTHORIZATION.md`). Not wired into any real endpoint.

**Task H — Admin tools.** All 5 read-mostly tools built; `simulate()`
is explicitly non-impersonating (never creates a session, never logs in
as anyone — just evaluates the same functions a real request would use).
Access review/recertification (Task H.5) was not built — it needs a new
`WorkflowDefinition` wired to iterate assignments, a meaningfully larger
piece than the others.

**Task J — Scoped API keys.** `ExternalAPIKey.allows_scope()`/
`allows_ip()`/`is_expired()` all tested directly (CIDR matching via
`ipaddress`, not string prefix matching). Existing keys: `scope_codenames=[]`
means unrestricted — their current behaviour is unaffected, exactly
Task J.2's requirement. Not wired into the actual external-API
request-handling views.

**Task K — Performance.** `effective_permissions(user)` cached via
Phase 1's versioned-namespace pattern (new `authz` namespace),
invalidated by `RoleAssignment`/`FieldPermission` saves (platform_core
signal) and `RolePermission` saves (new accounts signal, since
`RolePermission` lives in `apps.accounts`). Benchmark targets (2,000
reports / 50,000 employees / 500,000 attendance rows) were not run — no
dataset at that scale exists in this environment.

---

## 2. Catalogues

### Every ad hoc scope pattern found and how it is now expressed

**Not comprehensively catalogued** — Task C.5 itself asks to "list each
view changed" after replacing ad hoc patterns, but since no existing
view was changed (the engine is additive-only), there is no "replaced"
list to produce truthfully. What WAS found and documented: the
`EmployeeBranchAccess` factual correction (its real purpose is punch-in
geofencing, not general data-access scoping — see `docs/AUTHORIZATION.md`
and `OPEN_QUESTIONS.md`), and the shape of `apps/accounts/services_approval.py`'s
existing resolver logic (already catalogued in Phase 3B's resolver-parity
table, reused here for approver-style `RoleAssignment` resolvers — not
re-done).

### Every view changed

**None.** The engine is additive-only in this pass — see "Scoping
decision" above.

### The 4 role-name replacements (Task B.3 — all 4 actually done)

| File:line | Before | After |
|---|---|---|
| `apps/accounts/models.py` (superuser creation) | `Role.objects.get(name='system_admin')` | `Role.objects.filter(is_full_access=True, is_active=True).order_by('id').first()` |
| `apps/accounts/views/onboarding_approval.py:257` | `Role.objects.get(name='employee')` | `Role.objects.get(is_default_employee_role=True)` |
| `apps/dashboard/views/module_overviews.py:397` | `.exclude(name='employee')` | `.exclude(is_default_employee_role=True)` |
| `apps/payroll/views/shared.py:331` | `.exclude(role__name__in=['system_admin'])` | `.exclude(role__exclude_from_payroll=True)` |
| `apps/payroll/views/shared.py:344` | `.exclude(employee__role__name__in=['system_admin'])` | `.exclude(employee__role__exclude_from_payroll=True)` |

Each preserved by the migration-0181 backfill matching the EXACT roles
the old literal string would have matched (verified: 1 role each).

### `is_superuser`/`is_staff` usages found (14 citations, catalogued, NOT individually triaged)

`apps/accounts/admin.py:56,67`; `apps/accounts/management/commands/seed_policy_documents.py:48`;
`apps/accounts/models.py` (superuser-creation logic itself, 5 lines);
`apps/accounts/tokens.py:23,54` (comment + volatile-claims refresh —
`FreshClaimsTokenRefreshSerializer` re-derives `is_superuser` on every
token refresh so it never goes stale mid-session); `apps/accounts/views/auth.py:223`;
`apps/hrms/views/separation.py:67`; `apps/payroll/views/attendance_approval.py:23`;
`apps/payroll/views/ecr.py:51`; `apps/payroll/views/shared.py:631,640,647`;
`apps/voice_commands/executor_payroll.py:271`. Task D.3 asks to "keep
only those needed for Django admin and break-glass" — deciding which of
these 14 are genuine break-glass vs. convenience shortcuts is a judgment
call recorded in `OPEN_QUESTIONS.md` for the owner, not guessed at here.

---

## 3. One real bug found and fixed by the tests

**`SCOPE_ALL`'s union contribution was silently a no-op.**
`_custom_record_scope_filter()` returned a bare `Q()` for `SCOPE_ALL`,
folded into the running union via `combined |= q`. Django's `Q()` with
no children is a *no-op identity element* when combined with `|` — it
does NOT force "match everything" in that position (that's only true
when passed directly to `.filter(Q())` with nothing else). The result:
a user with an `all`-scope assignment would have seen **nothing**, not
everything, the exact opposite of the intended grant. Caught immediately
by `test_all_scope_sees_everything`. Fixed by short-circuiting
`SCOPE_ALL` to return the full queryset before any union logic runs at
all, rather than trying to express "always true" as a `Q` object to be
combined.

Two test-fixture bugs (not engine bugs) were also found and fixed along
the way: a `LegalEntity` test fixture missing required `base_currency`/
`country`/`timezone` FKs, and the discovery (via direct query) that the
shared `--keepdb` test database has **zero rows** in `hrms_roles`/
`hrms_permissions` despite the relevant seed migrations being marked
applied — the same pre-existing test-environment staleness class
documented in every prior phase's report (Phase 0's `DocumentTypeConfig`
investigation, Phase 2/3A/3B's Neon connection-drop pattern). Confirmed
via direct `psql`-equivalent query rather than guessed at; this affected
`tests_permission_registry.py`'s one test (logically verified correct
against the real dev DB, which has 113 permissions as expected) and
would affect any test assuming seeded `Role`/`Permission` rows exist in
that specific shared test database.

---

## 4. Parity harness results

**Not applicable — Task I was not executed.** There is no migration to
compare against, so there is no parity diff to report, empty or
otherwise. Stated plainly rather than fabricated.

---

## 5. Role matrix and SoD violations

`docs/ROLE_MATRIX.md` generated by `export_role_matrix` from the live
database: 5 active roles × 113 non-deprecated permissions. SoD
violations report: not run against production data in this pass (no
`SoDRule` is `is_active=True` yet — all 4 seeded rules are suggestions
pending owner activation, so `existing_violations_report()` currently
returns an empty list by design, not because no conflicts exist).

---

## 6. New endpoints for the frontend

**None in this pass.** `services_authz_admin.py`'s functions
(`who_can`/`what_can`/`simulate`/`clone_role`/`compare_roles`) are
callable Python functions, not yet wrapped in DRF views — Task H.6's
"all endpoints use the new authorization itself" would need the
authorization engine's own `has_perm_v2` wired as the permission class
for those views, which is circular with "haven't cut over `has_perm`
yet" and deliberately not attempted prematurely.

---

## 7. Test results

```
tests_authz.py: 36 tests, OK
```
`ScopeQuerysetTests` (9: own/all/no-assignment/expired/future/full-access/
can()/union/unmapped-scope/core-entity-raises), `FieldSecurityTests` (9),
`SoDTests` (4), `AdminToolsTests` (5), `IsFullAccessTests` (3),
`ExternalAPIKeyScopeTests` (4). `tests_permission_registry.py` — 1 test,
logically verified correct against the real dev database (113
permissions, matches scan output exactly); not clean against the stale
shared test database (see Section 3).

`python manage.py check` — clean. `makemigrations --check` — clean.
Migrations: `accounts/0180` (schema), `accounts/0181` (data backfill,
verified counts: 1/1/1), `platform_core/0016` (schema).

---

## 8. Updated docs

`docs/AUTHORIZATION.md` (new), `docs/ROLE_MATRIX.md` (new, generated),
`OPEN_QUESTIONS.md` (new file, per Task C.5's own instruction),
`docs/MIGRATION_PLAN.md` Phase 4 addendum, `scripts/check_no_permission_migrations.py`
wired into `.github/workflows/backend-tests.yml`.

---

## 9. Risks, limitations, and deferred items

- **Task I (migration + parity harness) is entirely deferred** — the
  headline risk, by design, stated plainly rather than buried.
- **No existing view, serializer, export, or endpoint uses any of this
  engine** — `has_perm()`, `can_manage_team`/`can_manage_branch`, and
  every ad hoc scope pattern in production code are completely
  unaffected and unchanged.
- **Only `own`/`all`/`legal_entity`/`my_legal_entity` scope types are
  mapped**, and only for `CustomRecord` — 8 of 12 declared scope types
  and every core entity have no mapping yet.
- **`EmployeeBranchAccess`'s assumed purpose (data-access scoping) does
  not match its actual documented purpose (punch-in geofencing)** — a
  factual correction for whoever executes Task I, recorded in
  `OPEN_QUESTIONS.md`.
- **Module toggle enforcement, field-security enforcement, and API-key
  scoping are all built but not wired into any real request path.**
- **Access review/recertification (Task H.5) is not built.**
- **Weekly full-access/superuser report (Task D.4) is not built.**
- **SSO/SAML/OIDC/MFA**: out of scope per the prompt itself — no design
  hooks were added in this pass (not requested as a concrete deliverable
  beyond "documented," and nothing in this phase's additive engine
  precludes adding them later).

## 10. Open questions for the owner

See `OPEN_QUESTIONS.md` in full — summarized: (1) which legacy scope
patterns need their own mapping before Task C.5 can proceed for real,
(2) whether `EmployeeBranchAccess` should genuinely gain a second
meaning (data-access scope) alongside its existing geofencing purpose,
(3) verifying the reporting-tree source of truth (manager chain vs. org
chart vs. both) for `all_reports` before Task I, (4) the missing
`roles.manage` permission the seeded SoD suggestion references, (5)
triaging each of the 14 `is_superuser`/`is_staff` usages individually.
