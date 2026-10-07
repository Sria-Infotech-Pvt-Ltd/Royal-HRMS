# Employee data model (Phase 5A)

Built additively alongside the existing flat `EmployeeProfile`/`User`
columns, which remain the **live, unchanged source of truth**. Nothing
in this document's new structures has been migrated into or wired to
replace existing data in this pass — see `PHASE5A_REPORT.md`'s
"Deferred" section.

## Why additive-only, again

Rule 3: *"Existing behaviour must not change... with the new flag OFF.
With it ON and migrated data, every existing endpoint... produces the
same results (parity tests)."* Rule from Section 6: *"Do not copy
ciphertext between columns, or decrypt into logs or reports."* Together
with the explicit "byte-for-byte" requirement on payroll/bank files,
this phase's Task L (the actual data migration + parity harness +
verification command) is gated on a correctness bar this session cannot
responsibly claim to meet without the live production data this phase
would run against. Same discipline as every prior phase's deferred
cutover (Company→LegalEntity, attendance consolidation, approval
migration, authorization parity harness): build the new structures for
real, prove them standalone, defer the risky live-data cutover
explicitly.

## ERD (textual — new models only)

```
User (existing)
 ├─< ContactMethod (type, value, is_primary)
 ├─< BankAccount (country, account_number[enc], routing_code[enc], split_*)
 ├─< EmergencyContact (name, relationship, priority, family_member?)
 ├─< Nomination (scheme, family_member, share_percentage, guardian?)
 ├─< EmployeeSkill (skill?, skill_text, proficiency, years)
 ├─< EmployeeCertification (name, issuer, issue_date, expiry_date)
 ├─< EmployeeLanguage (language_code, can_read/write/speak)
 ├─< StatutoryEnrolment (scheme, is_enrolled, identity_document?)
 ├─< [generic FK via ContentType] Address (type, country, line1.., state, postal_code)
 ├─< [generic FK via ContentType] IdentityDocument (type, number[enc], number_hash)
 └─< FamilyMember (existing, +first_name/+last_name/+is_nominee_eligible/+occupation)
      ├─< Nomination.family_member
      └─< [generic FK via ContentType] Address / IdentityDocument (same owner pattern)

IdentityDocumentType (country-pack master) ─< IdentityDocument
JobFamily ─< Designation ─< Position.designation_ref
Band ─< Grade ─< Position.grade_ref ; JobTemplate.band_ref
CostCenter ─< OrgUnit.cost_center_ref
```

`Address`/`IdentityDocument` use a generic `(content_type, object_id)`
owner, per Task C.1/D.2's own instruction that these need to attach to
an employee, a family member, or (for `Address`) a legal entity.

## What was built, by task

**Task A.** `Band`, `Grade`, `JobFamily`, `Designation`, `CostCenter` —
full models with history-friendly `is_active`/timestamps. `Position`
gained `grade_ref`/`designation_ref`/`job_family`/`fte`/`headcount_budget`;
`JobTemplate` gained `band_ref`; `OrgUnit` gained `cost_center_ref`.
`Position.is_vacant` is a derived property (no stored column), computed
from `Placement` the same way the rest of this codebase already treats
"is there a current placement" queries. **Not built**: the data
migration converting distinct text values into master rows, or the
near-duplicate detection report (Task A.2) — no master rows exist from
real data yet, only the schema to hold them.

**Task B.** `ContactMethod` (type/value/is_primary/is_verified).
`split_full_name()` implements the documented best-effort rule (2 words
→ first/last; 3+ → first/middle(s)/last; 1 word → ambiguous, never
raises). `normalize_phone()` converts a bare national number or a
separator-formatted number to E.164 given a country phone code;
anything it can't confidently normalize returns `None` rather than
guessing — the caller is expected to keep the original and report it
(Task B.2's own instruction). **Not built**: `User.first_name`/
`last_name`/`preferred_name`/`name_local_script` columns themselves, or
`Country.name_format` — the service layer is proven standalone but has
no column to write into yet, since adding those columns without the
migration that populates them correctly would just be dead schema.

**Task C.** `Address` (generic owner, country-aware, `is_same_as_current`
preserving the existing "permanent = copy of current" semantics,
effective-dated). `validate_address()` reads `Country.address_format`'s
`required_fields`/`postal_code_regex` (Phase 1's existing JSON field) —
no India-specific hardcoding, any country format works once the pack
declares it. **Not seeded**: an actual India `address_format` payload
reproducing today's exact current/permanent field set — flagged as
needed before any real validation can run against it.

**Task D.** `IdentityDocumentType` (country-pack master, `normalisation`/
`mask_pattern`/`unique_scope` declared) + `IdentityDocument` (generic
owner, encrypted `number`/`name_on_document` reusing the EXISTING
`core.encrypted_fields.EncryptedCharField` — never a second encryption
implementation — blind-indexed `number_hash`, DB-enforced uniqueness
scoped by type via a partial unique constraint). 9 India document types
seeded (`seed_identity_document_types`) — PAN's regex is the one
"verified" entry (a genuinely stable, public government format); every
other type is seeded `is_verified_format=False` per the task's own
instruction. **Not built**: migrating `EmployeeProfile`'s existing PAN/
Aadhaar/UAN/ESI/PF/passport/disability-certificate values into this
table — would require decrypting real production ciphertext through the
model layer, exactly the kind of operation this phase's own Rule 4
("no plaintext exposure... never copy raw ciphertext between columns")
means should happen through a careful, dedicated migration pass, not
guessed at here.

**Task E.** `BankAccount` (country-aware routing code types — IFSC/IBAN/
SWIFT/sort-code/ABA/other — `validate_routing_code()` checks IFSC/IBAN/
SWIFT format; encrypted `account_number`/`routing_code`; salary-split
fields stored but `payroll does not use splits until Phase 7`, per the
prompt's own instruction, stated here too). Proven to actually encrypt
at the DB level (`tests_employee_master.test_bank_account_encrypts_account_number`
reads the raw column via a direct SQL query and confirms it's not
plaintext). **Not built**: the bank-change workflow definition (Task
E.2 — would need tracing today's exact `bank_change_status` approval
behavior first, itself a research task on the scale of Phase 3B's
deferred approval migration), or migrating in-flight pending bank
changes.

**Task F.** `FamilyMember` gained `first_name`/`last_name`/
`is_nominee_eligible`/`occupation` (additive columns on the EXISTING
model, not a new table). `EmergencyContact` (multiple, prioritized,
optionally linked to a `FamilyMember`). `Nomination` generalises
`EPFNominee` (kept, untouched) — `validate_nomination_shares()` enforces
the 100%-per-scheme rule as a pure function (not yet a DB constraint,
since shares are scoped by `scheme` + `employee`, which a simple
`CHECK` can't express — would need a trigger or application-level
enforcement at save time, not built in this pass).

**Task G.** `EducationRecord` gained `score_type`/`score_value`/
`score_scale`/`is_highest`/`is_completed` (additive — `percentage`
itself untouched). `WorkExperienceRecord` gained `country`/`is_verified`/
`verified_by` (its `employment_type` field itself is explicitly Phase
5B's to convert, per this phase's own coordination note — left alone).
`compute_total_experience_years()` implements the documented overlap
rule (merge overlapping intervals, sum merged durations) as a pure,
tested function. `derive_highest_qualification()` picks by rank then
most-recent end date. **Not built**: parsing existing `percentage` text
into `score_type`/`score_value`, or making `highest_qualification`/
`institution`/etc. actually computed properties on `EmployeeProfile` —
the derivation functions exist and are tested; nothing calls them from
the profile yet.

**Task H.** `SkillMaster` (taxonomy), `EmployeeSkill` (skill or
freeform `skill_text` fallback, proficiency, years, primary flag),
`EmployeeCertification`, `EmployeeLanguage`. **Not built**: splitting the
existing `core_skills`/`certifications` text fields into rows — no
data exists in these tables from real employees yet.

**Task I.** `StatutoryEnrolment` (scheme lookup, enrolment flag, linked
identity document, scheme-specific `attributes`). **Not built**:
migrating `pf_covered`/`esi_covered`/`is_international_worker` into
enrolment rows, or the payroll-reading adapter — payroll keeps reading
the existing flags directly, completely unaffected.

**Task J.** Not executed as a sweep — `account_type`/`disability_type`/
`EducationRecord.level`/`FamilyMember.relationship`/`EPFNominee.scheme`/
`bank_change_status` remain their existing `choices=` fields. Converting
each to a Phase 1 lookup with a compatibility mapping is exactly the
kind of per-field migration work this phase's Task L defers wholesale.

**Task K.** `EmployeeDocument.expiry_date` was NOT added, and no Phase
3B `document.expiring`/`document.expired` wiring was built in this pass
— `IdentityDocument.expiry_date` exists on the new table (ready for a
future expiry-tracking job to query), but the job itself, the HR
dashboard endpoint, and the default notification rules are not built.

**Task L.** **Entirely deferred** — see `PHASE5A_REPORT.md`. No flag
`employee.v2` was created because there is nothing yet for it to switch
between; no call site reads or writes through these new structures.

## Country-pack coverage

Only India is seeded (9 `IdentityDocumentType` rows). No
`Country.address_format` payload was populated for any country in this
pass — `validate_address()` is proven against a fake country object in
tests, not against real seeded data.
