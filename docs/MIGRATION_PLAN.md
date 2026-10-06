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

## Phase 2 addendum — field/form/custom-object engine built, onboarding not yet cut over

See `PHASE2_REPORT.md` for full detail. In short: `EntityDefinition`/
`FieldDefinition`/`FormLayout`/`CustomRecord` and their services are built
and tested, and 6 core entities (employee, branch, org_unit, position,
legal_entity, candidate) are registered with working `attributes` storage.
**The real onboarding wizard (`frontend/app/onboarding/`,
`OnboardingFieldConfig`/`OnboardingSection`) has NOT been touched or
migrated onto this engine** — that is Task J, explicitly deferred behind a
future `forms.v2` feature flag, same reasoning as the Company/NumberSeries
cutovers above: the highest-blast-radius item in the whole prompt (every
new hire goes through it today) gets its own dedicated pass with the flag
OFF by default, not a same-commit cutover.
