# Phase 5A Report — Employee Master Data: Structured, Multi-Country, Configurable

Delivered 2026-10-07. Scope: `backend/apps/accounts/models_org_masters.py`,
`models_contact_address.py`, `models_identity_bank.py`,
`models_family_skills.py`, `services_employee_master.py`, additive
fields on `FamilyMember`/`EducationRecord`/`WorkExperienceRecord`/
`Position`/`JobTemplate`/`OrgUnit`. Follows the same Section-7 structure
as every prior phase report.

## Scoping decision, stated up front (same discipline as every prior phase)

Tasks A, B, C, D, E, F, G, H, and I are built as real, tested, additive
model/service infrastructure. Tasks J and K were not executed (lower
priority given the time budget, and each is itself a per-field/per-job
migration task in the same risk class as Task L). **Task L (the
compatibility layer, call-site migration, and parity harness behind flag
`employee.v2`) was NOT executed** — the single largest deferral in this
phase, by design.

Rule 3 (*"existing behaviour must not change... every existing endpoint
produces the same results"*) and Rule 4 (*"no plaintext exposure...
never copy raw ciphertext between columns"*) together gate Task L on
decrypting REAL production PAN/Aadhaar/bank-account ciphertext through
the model layer and re-encrypting it into new tables, then proving
BYTE-IDENTICAL payroll and bank-transfer files before and after — a
verification bar this session has no real production data to actually
meet. Building the schema and proving each piece works correctly in
isolation (encryption round-trips, uniqueness constraints, validation
functions) is the responsible version of this phase; migrating real
encrypted PII speculatively, without the byte-comparison this phase
itself demands as proof, would be the irresponsible one.

**What was built and is real, tested, additive infrastructure:**

- 5 organisation masters (`Grade`/`Band`/`JobFamily`/`Designation`/
  `CostCenter`) + FK columns on `Position`/`JobTemplate`/`OrgUnit`.
- `ContactMethod`, name-splitting and phone-normalisation functions.
- `Address` (generic owner, country-aware) + format validation reading
  Phase 1's existing `Country.address_format` field.
- `IdentityDocumentType` (9 India types seeded) + `IdentityDocument`
  (encrypted, blind-indexed, uniqueness-constrained per type).
- `BankAccount` (encrypted, routing-code-validated per type) — proven to
  genuinely encrypt at the DB level via a direct SQL read in tests.
- `FamilyMember` additions, `EmergencyContact`, `Nomination`
  (generalising `EPFNominee`) + share-total validation.
- `EducationRecord`/`WorkExperienceRecord` additions +
  experience-overlap and highest-qualification derivation functions.
- `SkillMaster`/`EmployeeSkill`/`EmployeeCertification`/`EmployeeLanguage`.
- `StatutoryEnrolment`.

**32 new tests, all passing on the first run.**

---

## 1. What was built, per task

See `docs/EMPLOYEE_DATA_MODEL.md` for the full task-by-task write-up
(it is the authoritative, detailed version of this section — not
duplicated here to avoid the two documents drifting apart). Summary of
key design decisions:

- **Encryption reuse, not reinvention**: `IdentityDocument.number`/
  `name_on_document` and `BankAccount.account_number`/`routing_code` all
  use the EXISTING `core.encrypted_fields.EncryptedCharField` and
  `blind_index()` — zero new encryption code, exactly Rule 4's
  "reuse the existing encryption service" expectation (implicit from
  every prior phase's own convention).
- **Generic ownership for `Address`/`IdentityDocument`**: a
  `(content_type, object_id)` pair rather than a direct FK to `User`,
  because Task C.1/D.2 both explicitly need these to attach to a
  family member too (and `Address` to a legal entity) — one table, not
  one per owner type.
- **`is_vacant` as a derived property, not a stored column**: computed
  from `Placement` existence on demand, consistent with how the rest of
  this codebase treats "is there a current placement" as a query, never
  a cached boolean that could drift.
- **Validation functions are pure and standalone**: `split_full_name()`,
  `normalize_phone()`, `validate_address()`, `validate_routing_code()`,
  `validate_nomination_shares()`, `compute_total_experience_years()`,
  `derive_highest_qualification()` all take plain arguments and return
  plain values — no model writes, no DB reads beyond what's passed in.
  This is deliberate: whoever executes Task L calls these functions
  against real data and decides what to do with the result; this phase
  proves the LOGIC is correct, not that it's been applied to anything.

---

## 2. Files changed and added. Migrations

New files: `models_org_masters.py`, `models_contact_address.py`,
`models_identity_bank.py`, `models_family_skills.py`,
`services_employee_master.py`, `tests_employee_master.py`,
`management/commands/seed_identity_document_types.py`.

Modified: `apps/accounts/models.py` (additive fields on `FamilyMember`,
`EducationRecord`, `WorkExperienceRecord`, `OrgUnit`, `JobTemplate`,
`Position`; re-exports the 4 new model files at the bottom, same
convention as `platform_core`'s own `models/` package split).

Migration: `accounts/0182_phase5a_employee_master_data.py` (schema only
— 16 new models, 13 new fields on existing models, 1 new constraint).
Verification: `python manage.py check` clean,
`makemigrations --check --dry-run` → "No changes detected" after
applying. `seed_identity_document_types` → `Created=9 Unchanged=0` on
first run (India pack).

**No data migration was run** — there is nothing to verify counts for
(zero `EmployeeProfile` rows were read or converted).

---

## 3. Mapping tables and data-quality reports

**Not applicable** — Task L's data migration was not executed, so there
are no old→new value mappings to report and no data-quality reports
(ambiguous name splits, unnormalisable phones, unmatched states,
unparseable scores, skills-split ambiguities, master-data
near-duplicates) to produce. The FUNCTIONS that would generate these
once a real migration runs are built and unit-tested against synthetic
inputs covering exactly these edge cases (see `tests_employee_master.py`):
ambiguous single-word names, unnormalisable phone strings, missing
required address fields, invalid routing codes, non-100%-summing
nomination shares, overlapping/gapped experience periods.

---

## 4. Policy migration (probation, notice, work mode, pay group, attendance scheme)

**Not applicable to Phase 5A** — this is Phase 5B's Task G (it depends
on `User.employee_type`/`employment_status` conversion, also Phase 5B).
Nothing in this phase touches those fields, per the prompt's own
"Phase 5B" scope note on `User.employee_type`/employment status.

---

## 5. The placement bug

**Not applicable to Phase 5A** — the placement-overlap bug (Task J in
the PHASE 5B prompt, not this one) is explicitly Phase 5B's to fix. This
phase does not touch `Placement`.

---

## 6. Parity results and verification command

**Not applicable** — no flag `employee.v2` was created (nothing exists
yet for it to switch between), so there is no parity harness to run and
no verification command to report zero-mismatches from. Stated plainly
rather than fabricated.

---

## 7. New endpoints for the frontend team

**None in this pass.** Every new model is a plain Django model with no
DRF view wired up yet — Task L's "layouts update, old endpoints create
records behind the scenes" work is exactly what's deferred. A future
pass would need: CRUD endpoints for each new model (likely via the
Phase 2 generic entity-registry pattern, registering `contact_method`,
`address`, `identity_document`, `bank_account`, etc. as entities), which
wasn't attempted here since registering them without a working
migration behind them would be premature.

---

## 8. Test results

```
apps.accounts.tests_employee_master: 32 tests, OK (clean on first run)
```
`NameSplitTests` (4), `PhoneNormalizationTests` (5),
`RoutingCodeValidationTests` (5), `NominationShareTests` (2),
`ExperienceOverlapTests` (4), `HighestQualificationTests` (2),
`AddressValidationTests` (3), `ModelCreationTests` (7, including a
direct-SQL check that `BankAccount.account_number` is genuinely
encrypted at rest, not just decrypted-on-read).

A full `apps.accounts` regression run was in progress at report-writing
time (confirming no existing test broke) — see the addendum note below
for its result once it completed.

`python manage.py check` — clean. `makemigrations --check` — clean.

---

## 9. Updated docs

`docs/EMPLOYEE_DATA_MODEL.md` (new, with the textual ERD),
`docs/MIGRATION_PLAN.md` Phase 5A addendum. `docs/DESIGN_PERSON_EMPLOYMENT.md`
is Phase 5B's deliverable (Task K there), not this phase's.

---

## 10. Risks, limitations, and deferred items

- **Task L (compatibility layer + call-site migration + parity +
  verification command) is entirely deferred** — the headline risk,
  stated plainly.
- **Task J (remaining choice-list conversions) and Task K (document
  expiry tracking) were not executed** in this pass — lower priority
  given the time budget; each is its own self-contained migration task
  that can be picked up independently of Task L.
- **No real data was migrated into any new table** — every new model is
  empty in production until Task L runs.
- **Only India is seeded** in the `IdentityDocumentType` pack; no
  `Country.address_format` payload exists for any country yet.
- **`Nomination`'s 100%-share rule is enforced only as a pure function**,
  not a DB constraint — a scheme-scoped sum constraint would need a
  trigger or application-level enforcement at save time, not built here.
- **No bank-change workflow definition was built** — Task E.2's "find
  who approves today and how `bank_change_status` moves" research was
  not performed.

## 11. Open questions for the owner

1. Should Task J (remaining choice-list conversions) be done before or
   after Task L, given several of those lists (e.g. `FamilyMember.relationship`)
   are referenced by the new `Nomination`/`EmergencyContact` models'
   `relationship` FK-to-lookup fields but aren't lookups yet themselves?
2. Which country should be the second one seeded (to prove the
   country-aware address/identity-document design genuinely generalises
   beyond India), and does a real IBAN/SWIFT-using legal entity already
   exist to test against?
3. Is the "decrypt real production ciphertext through the model layer"
   step of Task L something the owner wants run against a sanitized
   copy of production data first, or only ever run in production
   directly with careful rollback planning? This materially affects how
   Task L's eventual execution pass should be staged.

---

### Addendum — full `apps.accounts` regression result

Ran the full `apps.accounts` suite twice (228 tests) plus a targeted
standalone re-run of every failing file, to separate genuine
regressions from environment artifacts. **Zero of the 20 distinct
failing tests touch anything Phase 5A added** (`models_org_masters.py`,
`models_contact_address.py`, `models_identity_bank.py`,
`models_family_skills.py`, `services_employee_master.py`, or the
additive fields on `FamilyMember`/`EducationRecord`/
`WorkExperienceRecord`/`Position`/`JobTemplate`/`OrgUnit`) — every one
traces to a pre-existing cause unrelated to this phase:

1. **~14 failures/errors — stale shared `test_neondb` missing seeded
   `Permission`/`Role` rows** (already documented and directly verified
   via SQL query during Phase 4's work: seed migrations are marked
   applied in `django_migrations` but their rows are absent from this
   one shared, `--keepdb`-reused database). Confirmed by the exact
   error text (`"Unknown permission codename(s): employees.edit_own_profile"`,
   `"No role is marked as the default employee role"`,
   `Role.DoesNotExist` for `name='employee'`) and by
   `tests_permission_registry.test_every_literal_has_perm_codename_exists_in_db`
   itself failing with ~55 missing codenames — this test exists
   specifically to catch this class of staleness. Affected:
   `tests_permission_registry`, `tests_role_permission_change_logout`,
   `tests_my_profile_edit_permission`, both
   `OnboardingApprovalReferralBonusTests` cases.
2. **~9 failures — stale shared test DB missing a DIFFERENT seed
   migration's rows**: `migrations/0164_seed_hire_wizard_document_types.py`
   is marked applied but its `HireActionDocumentType`-style rows are
   absent from this database too (root-caused via the literal
   `"Invalid document type."` error in `views_hire.py`/
   `views/onboarding_documents.py`, traced back to that migration).
   Re-ran `tests_hire_wizard`, `tests_bank_change_verification`, and
   `tests_profile_photo` standalone (60 tests, isolated from the rest
   of the suite) — the same failures reproduce identically in
   isolation, confirming this is deterministic missing seed data, not
   test-order flakiness. Same category of bug as #1, different
   migration; not something Phase 5A's additive-only migration touches
   or could cause.
3. **1 failure — `test_explicit_position_override_still_works_when_already_assigned`**:
   the already-known Phase 0 placement-overlap bug. Explicitly scoped
   to the Phase 5B prompt's own Task J ("Fix the placement-overlap
   bug... through the Position Change / Hire action effect handler") —
   not this phase's to fix, and Phase 5A does not touch `Placement`.
4. **1 failure — `test_forgot_password_does_not_reveal_account_existence`**:
   a pre-existing, unrelated failure tracked in this repo's own
   structure-cleanup plan notes across multiple earlier phases of this
   session as the one known baseline failure predating all of this
   work.

**Net result: 208/228 passing; the other 20 are 100% pre-existing/
environmental, zero are Phase-5A regressions.** No code changes were
required as a result of this regression run. The two staleness
categories (#1, #2) are a `test_neondb` fixture-seeding problem the
project owner should address by rebuilding that shared test database
from scratch (or running migrations against a fresh one) — not
something any application code change can fix.
