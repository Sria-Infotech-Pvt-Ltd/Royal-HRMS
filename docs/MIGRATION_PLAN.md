# Migration Plan — Hardcoded Choices and Pilot Field Conversion

This tracks every hardcoded `choices=` field inventoried in Phase 0/1,
whether it was converted in Phase 1, and what's planned for later.

## Pilot conversion done in Phase 1

These now have a matching `LookupType`/`LookupValue` seeded (see
`apps/platform_core/seed_packs/core_lookups.json`), with a
`legacy_value` attribute on each value recording the exact string the
field already stores today — **the model fields themselves were NOT
changed in Phase 1** (still plain `CharField(choices=...)`). The lookup
data exists and is tested (see `tests_lookups.py`), ready for whichever
later phase actually swaps the field definition and wires the
compatibility layer into each serializer.

| Old field | Lookup type | Values seeded | Business logic branches on it? |
|---|---|---|---|
| `EmployeeProfile.gender`, `FamilyMember.gender` | `GENDER` | MALE, FEMALE, OTHER | No — display/reporting only |
| `EmployeeProfile.marital_status` | `MARITAL_STATUS` | SINGLE, MARRIED, DIVORCED, WIDOWED | No |
| `EmployeeProfile.blood_group` (`FamilyMember.blood_group` is free text today — no conversion needed there) | `BLOOD_GROUP` | 8 standard groups | No |
| `FamilyMember.relationship` | `FAMILY_RELATIONSHIP` | FATHER, MOTHER, SPOUSE, CHILD, SIBLING | **Yes** — `HireWizardClient.tsx`'s father/mother-name sync logic matches on `relationship === "father"`/`"mother"` literals. Converting the FIELD (not just seeding the lookup) must update that frontend logic too — flagged for whichever phase does the actual cutover. |
| `CompanyAsset.asset_type` | `ASSET_TYPE` | 5 types | No |
| `CompanyAsset.condition` | `ASSET_CONDITION` | NEW, GOOD, REFURBISHED | No |
| `Holiday.holiday_type` | `HOLIDAY_TYPE` | NATIONAL (default), REGIONAL, COMPANY | No |
| `Announcement.category` | `ANNOUNCEMENT_CATEGORY` | 4 categories | No |
| `HRHelpRequest.topic` | `HR_HELP_TOPIC` | 8 topics | No |
| `HRHelpRequest.priority` | `HR_HELP_PRIORITY` | LOW, NORMAL (default), HIGH | No |

**Not converted despite being in the original pilot list, with reason:**
- `EmployeeProfile.salutation` — verified it is a plain `CharField`, not a
  `choices=` field at all. Nothing to convert.
- `Company.industry`/`entity_type`/`msme_class`/`jurisdiction`/`bank_account_type`
  — these move to `LegalEntity` as part of the Company→LegalEntity
  migration, which Phase 1 built the model for (`platform_core.LegalEntity`)
  but deliberately did NOT cut over (see PHASE1_REPORT.md "Deferred").
  Seeding their lookup values is bundled with that cutover, not done
  standalone here.

## Remaining choice lists — target phase

Every other field from the Phase 0 inventory (144 total, 10 pilot-converted
above, 134 remaining) is grouped below by which later phase's scope it
falls under, per the Phase 1 prompt's own phase breakdown. "Branches?"
notes whether business logic depends on the stored value (a `False` there
doesn't guarantee safety — it means no branching was found in THIS
session's review, not an exhaustive proof).

### Phase 5 (Core HR — identity, employment actions)
`User.employee_type`, `User.work_mode`, `User.pay_group`,
`User.attendance_scheme`, `User.payment_method`, `User.onboarding_status`,
`User.assessment_status`, `User.employment_status`, `HireAction.reason`,
`HireAction.employment_type`, `HireAction.status`, `PromotionRecord.reason`,
`EmployeeProfile.account_type`, `EmployeeProfile.bank_change_status`,
`EmployeeProfile.pending_account_type`, `EmployeeProfile.disability_type`,
`EducationRecord.level`, `WorkExperienceRecord.employment_type`,
`EPFNominee.scheme`. **Branches: yes**, extensively — employment_type in
particular drives the whole Hire wizard's number-series selection
(`EmployeeCodeSeries`), payroll statutory calculations, and probation/
notice-period defaults. This is the highest-risk group — do not convert
without the full parity-testing discipline Phase 1 used for NumberSeries.

### Phase 6 (Leave & attendance)
All of `attendance`'s 33 fields, plus `hrms`'s leave/holiday fields
(`LeaveBalance.leave_type`, `LeaveRequest.leave_type`/`duration`/`status`/
`l1_status`/`l2_status`, `LeavePolicy.*`). **This is where the
`LeaveType` asymmetry bug (Section 3 of PHASE0_INVENTORY.md) gets fixed**
— `LeavePolicy.leave_type` (free text) vs `LeaveBalance`/`LeaveRequest.leave_type`
(fixed `LEAVE_TYPE_CHOICES`) need to converge on one FK, not independently
converted to two different lookup types.

### Phase 7 (Payroll)
`PayrollSettings.approval_levels`, `StatutoryConfig.lwf_frequency`,
`SalaryComponent.component_type`/`calculation_type` (**branches: yes** —
`services_estimate.py` matches components by name string, a real
fragility noted in PHASE0_INVENTORY.md), `BranchPayrollConfig.pf_wage_basis`,
`EmployeeSalaryConfig.reason`, `PayrollCycle.status`, `EmployeePayslip.status`,
`PayslipQuery.status`, `PayrollAdjustment.type`, `SalaryTransferBatch.status`,
`EmployeeTaxDeclaration.tax_regime`/`status`.

### Phase 8 (Talent — recruitment, performance)
`Candidate.interview_mode`/`status`, `CandidateLog.log_type`,
`CandidateEmail.status`, `ReferralBonus.status`, `ReviewCycle.status`,
`Goal.status`/`self_rating`, `PerformanceReview.self_rating`/
`manager_rating`/`status`, `AssessmentItem.item_type`,
`CandidateAssignment.status`.

### Phase 9 / unscheduled (low business-admin value, candidates for the
`ALLOWED_CHOICES_FIELDS` permanent exception list in
`scripts/check_no_new_choices.py` rather than conversion)
Internal workflow-status fields that mirror a fixed state machine with
code attached to every transition, not an open business list:
`Notification.notification_type`/`module`, `Document.category`,
`EmployeeDocument.verification_status`,
`ApprovalWorkflowRule.workflow_type`, `EmployeeApprovalOverride.workflow_type`,
`AttendanceAuditLog.event`, `SeparationApprovalStage.stage`/`status`,
`Branch.status`, `EmailLog.status`, `PasswordResetToken.purpose`,
`SMTPSettings.smtp_type`/`priority`/`receiver_email_type`. A later phase
should explicitly decide per-field rather than converting all of these by
default — several of them are genuinely closer to the `ChangeHistory.action`/
`NumberSeries.reset_period` exception pattern Phase 1 itself established.

## Company → LegalEntity cutover (deferred, model built)

`platform_core.LegalEntity` + `EntityIdentifier` + `EntityBankAccount` +
`AuthorisedSignatory` models, admin API, and the `ENTITY_IDENTIFIER_TYPE`/
`SIGNATORY_PURPOSE` lookup data (seed pack `india_core`) are built and
tested. The actual data migration (copy the one real `Company` row into
the primary `LegalEntity`), the backward-compatible Company-API service
shim, and the `legal_entity` FK backfill onto `Branch`/`OrgUnit`/`Position`/
`User`/`AuditLog` are **deliberately deferred** — see PHASE1_REPORT.md
"Deferred, and why."

## Number series cutover (deferred, model + service built)

`platform_core.NumberSeries` + the concurrency-safe `allocate()`/`preview()`
service are built and tested (including the required concurrency test).
`NumberSeries` rows mirroring every existing `EmployeeCodeSeries` row and
the `EmployeeCodeSettings` singleton are seeded via migration
`0002_seed_number_series_from_employee_codes` (additive only).
**`EmployeeCodeSettings.generate_employee_id()` / `generate_employee_id_for_type()`
still issue every real employee code today** — the feature-flag-gated
cutover and the parity test proving identical output under flag ON vs OFF
are deferred to their own pass, not rushed here.

## Phase 2 addendum — field/form/custom-object engine built; onboarding mirrored, not cut over

See `PHASE2_REPORT.md` for full detail. `EntityDefinition`/`FieldDefinition`/
`FormLayout`/`CustomRecord` and their services, list views, attachments,
and the import/export framework are all built and tested. 6 core entities
(employee, branch, org_unit, position, legal_entity, candidate) are
registered with working `attributes` storage.

**The real onboarding wizard (`frontend/app/onboarding/`) still renders
from `OnboardingFieldConfig`/`OnboardingSection` exactly as before.**
`services_onboarding_sync.py` mirrors every save onto the new engine
(write-through, via `apps/accounts/signals.py`) behind feature flag
`forms.v2`, seeded `enabled=False` — nothing reads the mirror for real
rendering yet. Turning the flag on and actually switching the frontend
wizard over to `resolve_layout()` is its own future cutover, same
discipline as Company/NumberSeries above: highest-blast-radius item in the
whole prompt, not a same-commit switch.

### Task J field mapping (what the mirror does)

| Legacy source | New engine target | Mapping rule |
|---|---|---|
| `OnboardingFieldConfig` (`is_custom=True`) | `FieldDefinition` (entity=`employee`) | `field_key`→`code`, `label`→`label`, `field_type`→`data_type` (table below), `required`→`required`, `allow_multiple`→`multiple`, `order`→`order`. Always `status=published`. |
| `OnboardingFieldConfig` (`is_custom=False`) | *(not mirrored)* | Already a real `EmployeeProfile`/`User` column — no `FieldDefinition` created in this phase. |
| `OnboardingFieldConfig.options` (dropdown) | Auto-created `LookupType` (`onboarding_<field_key>`) + `LookupValue` rows | Each option's text becomes one `LookupValue`; generated `UPPER_SNAKE` code, original text preserved as `attributes.legacy_value` so existing stored `custom_field_values` (which hold the raw text) still resolve without a data rewrite. |
| `OnboardingFieldConfig.visible` | Presence/absence of a `FormFieldPlacement` | `visible=True` → placement exists; `visible=False` → no placement (matches the legacy behavior of not rendering the field at all, rather than a permanently-false `visible_when`). |
| `OnboardingFieldConfig.step` (0-3) | `FormStep.order` under the mirrored `onboarding_v2_mirror` `FormLayout` | Fixed labels: 0=Personal Information, 1=Education & Experience, 2=Bank Details, 3=Emergency Contact. |
| `OnboardingSection` (step ≥ 5) | `FormStep` (same layout) | 1:1 — `step`→`order`, `label`→`label`, `icon`→`icon`. |

`field_type` → `data_type` table: `text`→`text`, `textarea`→`long_text`,
`number`→`decimal`, `date`→`date`, `dropdown`→`lookup`, `checkbox`→`boolean`,
`file`→`file`.

**Not mirrored** (see `PHASE2_REPORT.md`'s Task J write-up for why):
`EducationExperienceFieldConfig`-driven repeating sections,
`DocumentTypeConfig`-driven documents section — both need a dedicated
`EntityDefinition` this phase didn't register.

## Phase 3A addendum — rule/policy engine built; per-user policy-output fields (Task G.3)

See `PHASE3A_REPORT.md`, `docs/RULES.md`, `docs/POLICIES.md` for full
detail. The rule engine (`services_rules.py`) and policy engine
(`services_policies.py`, `PolicyType`/`Policy`/`PolicyAssignment`) are
built and tested. 7 attendance `PolicyType`s are registered with full
parameter schemas documenting the System1/System2 field mapping —
**no data migration, no call-site rewiring, and no "identical
resolution" verification report were executed** (same deferral class as
the Company→LegalEntity and NumberSeries cutovers above — the highest-
blast-radius item, attendance processing for every employee, needs its
own dedicated pass with the parity discipline those cutovers used).

Per Task G.3, every per-user field that is really a policy output,
and the phase in which it becomes policy-resolved with a per-employee
override:

| Field | Target phase | Notes |
|---|---|---|
| `User.attendance_scheme` | Phase 3A follow-up (attendance consolidation) | The 7 `ATT_*` `PolicyType`s registered this phase are exactly what this field should resolve through once the consolidation itself is done. |
| `User.pay_group` | Phase 7 (Payroll) | Becomes a `PAY_GROUP` policy type once payroll formulas/statutory tables are built. |
| `User.leave_plan` | Phase 6 (Leave) | `LEAVE_PLAN` policy type is already registered (read-only, Task G.2) — this phase explicitly does not change leave behavior; Phase 6 is where it becomes a real, writable, policy-resolved assignment. |
| `User.work_mode` | Phase 5 (Core HR) | Already flagged in Phase 0's inventory as a hardcoded-choices field with no branching logic found — low risk, but still a per-user field that conceptually belongs in a policy once Phase 5 does its HR-identity pass. |
| `HireAction.employment_type`-derived `probation_period_months`/`notice_period_days` | Phase 5 (Core HR) | Currently plain fields on `User`/`HireAction`; Phase 5's own plan (see PHASE2_REPORT.md's referenced hire-wizard plan) already lists these as candidates for policy-driven defaults by employment type/legal entity. |

### Known gaps carried from Phase 1 (unrelated to Phase 3A's own scope, found while registering history on new models)

`ChangeHistory.changes` was missing `encoder=DjangoJSONEncoder` since
Phase 1 — any tracked field value that's a `date`/`datetime`/`Decimal`/
`UUID` crashed `_capture_update_or_create()`'s `ChangeHistory.objects.create()`
call with a `TypeError: Object of type date is not JSON serializable`.
This never surfaced in Phase 1/2 because no registered model's tests
happened to `.save()` a tracked date/Decimal field directly; Phase 3A's
`RuleDefinition`/`Policy`/`PolicyAssignment` history registrations hit it
immediately via their own `effective_from`/`published_at` fields. Fixed
in migration `0011_change_history_json_encoder_fix` — a real, general fix
(not scoped to Phase 3A's own models), so every future `history.register()`
call on any model with a date/Decimal/UUID field is now safe by default.

## Phase 3B addendum — workflow/approval engine built; legacy approvals NOT migrated

See `PHASE3B_REPORT.md`, `docs/WORKFLOWS.md`, `docs/EVENTS_AND_NOTIFICATIONS.md`,
`docs/SCHEDULER.md` for full detail. The workflow runtime
(`WorkflowDefinition`/`WorkflowStep`/`WorkflowInstance`/`WorkflowTask`/
`WorkflowHistory`), the domain-event catalogue + outbox, notification
rules/templates/delivery/preferences, and the scheduler models are built
and tested — proven end to end against a Phase 2 custom entity (the
"Vehicle Allocation" 2-step approval, Acceptance Criterion 2), which needs
no legacy `l1_*`/`l2_*` column compatibility at all.

**Task C (migrating leave/WFH/attendance-correction/expense approvals onto
this engine, behind `workflow.v2`) was NOT executed** — same deferral
class as Phase 3A's attendance consolidation: the full parity-test matrix
(L1-only, L1+L2, override present, approver-is-requester, approver
missing, reject-at-L1, reject-at-L2, withdraw, concurrent-clicks, each
compared OFF vs ON) and the `l1_*`/`l2_*` column sync-back hook are a
dedicated, high-blast-radius pass of their own — every existing leave/
WFH/attendance-correction/expense approval in production goes through
the legacy path unchanged.

### Approvals explicitly out of scope for Phase 3B (per the prompt), with target phase

| Approval | Current model | Target phase |
|---|---|---|
| Separation | `SeparationApprovalStage` | Not yet assigned — own dedicated migration pass, same discipline as leave/WFH/attendance/expense would need |
| Payroll cycle (attendance L1/L2) | `PayrollCycle`, `PayrollSettings.approval_levels` | Phase 7 (Payroll) |
| Onboarding and hire approvals | `HireAction`, onboarding wizard approval step | Phase 5 (Core HR) |
| Tax declaration | `EmployeeTaxDeclaration` | Phase 9 (per the Phase 2-era functional-spec plan already in this repo) |
| Overtime | Attendance overtime approval fields | Phase 3A follow-up (attendance consolidation) or its own pass |
| Face registration | Face verification approval flow | Not yet assigned |
| Bank-change | `EmployeeProfile.bank_change_status` | Not yet assigned |

### Resolver parity catalogue (Task 3's "how roles were resolved to people, before vs after")

| Legacy (`apps/accounts/services_approval.py`) | New resolver (`approver_resolvers.py`) | Parity |
|---|---|---|
| `resolve_approver(role, employee)` — `can_manage_team` branch | `reporting_manager_level_n` (level=1) | Real — same field (`employee.reporting_manager`), generalised to level N per Task A.2's own ask |
| `resolve_approver(role, employee)` — else branch | `hr_business_partner` | Real — same field (`employee.hr`) |
| `resolve_employee_org_unit_chief(employee)` | `org_unit_chief` | Real — calls the EXACT existing function, not a reimplementation |
| `resolve_approval_chain` (override lookup) | `WorkflowApproverOverride` + `_apply_overrides_and_delegation()` | Real — same override-first-then-role-default precedence, generalised from 4 fixed workflow types to any (definition, step) |
| N/A (no legacy equivalent) | `role_scoped` (branch/org_unit/legal_entity/global scope) | New capability |
| N/A | `dotted_line_manager` | New — real field, never used as a resolver before |
| N/A | `specific_user`, `position_holder`, `record_field`, `rule_expression` | New capability |
| "branch admin of the employee's branch" (named by the prompt) | **Not implemented** | No single existing function defines "branch admin" unambiguously — registering a guessed resolver would risk silently disagreeing with whatever the real intended definition turns out to be |

## Phase 4 addendum — authorization engine built; parity-migration NOT executed

See `PHASE4_REPORT.md`, `docs/AUTHORIZATION.md`, `OPEN_QUESTIONS.md` for
full detail. `RoleAssignment`/`FieldPermission`/`SoDRule`/the scope
engine are built and tested (proven against the Phase 2 custom entity).
`Role` gained `is_full_access`/`is_default_employee_role`/
`exclude_from_payroll`/`exclude_from_headcount`/`is_assignable`,
backfilled by migration to match exactly the roles that hold the
behaviour being replaced (1 role each for `is_full_access`,
`is_default_employee_role`, `exclude_from_payroll`). **All 4 of the
prompt's named hardcoded-role-name call sites were replaced** (not just
modeled) — `accounts/models.py`'s superuser creation, `onboarding_approval.py`'s
role assignment on conversion, `dashboard/views/module_overviews.py`'s
admin-role count, and both `payroll/views/shared.py` payroll-exclusion
filters.

**Task I (the migration + parity harness) was NOT executed** — same
deferral class as every prior phase's highest-risk cutover. Rule 3 of
Phase 4 ("access must not change... prove it with the parity harness")
and Section 6 ("do not approximate scope behaviour you cannot reproduce
exactly") together gate this on tracing the EXACT current behaviour of
~442 `has_perm()` call sites and ~87 `can_manage_team`/`can_manage_branch`
usages first — not something to guess at. `core.permissions.has_perm()`
itself is completely untouched; every existing access-control decision
in production runs exactly as before.

### Role-permission matrix

See `docs/ROLE_MATRIX.md` (generated by `export_role_matrix`, regenerate
after any role/permission change — never hand-edit it).

## Phase 5A addendum — structured employee master data built; NO data migration executed

See `PHASE5A_REPORT.md`, `docs/EMPLOYEE_DATA_MODEL.md` for full detail.
Org masters (`Grade`/`Band`/`JobFamily`/`Designation`/`CostCenter`),
contact methods, addresses, identity documents, bank accounts, emergency
contacts/nominations, skills/certifications/languages, and statutory
enrolments are all built as real, tested, **additive** models alongside
the existing flat `EmployeeProfile`/`User` columns, which remain
completely unchanged and are the only thing any existing endpoint,
payroll calculation, or export reads.

**Task L (the compatibility layer, call-site migration, and parity
harness behind flag `employee.v2`) was NOT executed.** This phase's own
Rule 6 ("byte-for-byte" parity for payroll/bank files) and Rule 4 ("no
plaintext exposure... never copy raw ciphertext between columns")
together mean the actual data migration — decrypting real PAN/Aadhaar/
bank-account ciphertext through the model layer and re-encrypting into
the new tables, for real production data — needs its own dedicated,
carefully verified pass, not something to execute speculatively in the
same sitting as building the schema. No `employee.v2` flag was created
because nothing yet exists for it to switch between.

### Country-pack coverage

Only India is seeded: 9 `IdentityDocumentType` rows
(`seed_identity_document_types`), only PAN's format marked
`is_verified_format=True` (a stable, public government spec) — every
other type explicitly flagged "verify before go-live." No
`Country.address_format` payload was populated for any country.

### Deferred data-quality reports

Not applicable — these reports (ambiguous name splits, unnormalisable
phones, unmatched states, unparseable education scores, skills-split
ambiguities, master-data near-duplicates) are all byproducts of running
the actual data migration against real `EmployeeProfile` rows, which did
not happen in this pass. The validation/derivation FUNCTIONS that would
produce these reports once a migration runs them (`split_full_name()`,
`normalize_phone()`, etc., in `apps/accounts/services_employee_master.py`)
are built and tested.
