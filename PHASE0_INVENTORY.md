# Phase 0 — Hardcoded-Business-Value Inventory

Audit date: 2026-10-06. Pure inventory — no code changed as part of this
document. This is the factual input for any future decision about which
hardcoded values genuinely need to become admin-configurable, and in what
order. Every figure below was verified directly against the code (grep +
manual read), not assumed from a template.

## 1. Hardcoded `choices=` fields in models

| App | Count |
|---|---|
| accounts | 50 |
| attendance | 33 |
| hrms | 30 |
| payroll | 13 |
| performance | 6 |
| recruitment | 5 |
| assessments | 2 |
| notifications | 2 |
| announcements | 2 |
| branch | 1 |
| voice_commands | 0 (no models) |
| dashboard | 0 (no models) |
| **Total** | **144** |

Full field-by-field list is in the audit transcript this document was built
from; grouped highlights below for the fields most likely to matter for any
future "make this configurable" decision:

- **User-identity/employment shape** (`accounts`): `User.employee_type`,
  `User.work_mode`, `User.pay_group`, `User.attendance_scheme`,
  `User.payment_method`, `User.employment_status`, `EmployeeProfile.gender`,
  `EmployeeProfile.marital_status`, `EmployeeProfile.blood_group`,
  `FamilyMember.relationship`, `FamilyMember.gender` (note: a separate
  choices list from `EmployeeProfile.gender` — already an inconsistency).
- **Leave** (`hrms`): `LeaveBalance.leave_type`, `LeaveRequest.leave_type`,
  `LeavePolicy.accrual_frequency`, `LeavePolicy.carry_forward_type`,
  `LeavePolicy.applicable_gender` — see Section 3 for the
  `LeavePolicy`-vs-`LeaveBalance`/`LeaveRequest` asymmetry.
- **Attendance policy shape** (`attendance`): 7 day-of-week booleans on
  `WeeklyDayPolicy`, plus `PunchRulesPolicy.punch_mode`,
  `OvertimePolicy.round_off_rule`/`approval_type`,
  `LateMarkLOPPolicy.lop_deduction_unit`.
- **Payroll** (`payroll`): `SalaryComponent.component_type`/`calculation_type`
  (components are matched by **name string**, e.g. `name.lower() == 'basic'`,
  in `services_estimate.py` — a real fragility: renaming a component breaks
  the calculation silently), `EmployeeTaxDeclaration.tax_regime`.
- **Approval/status chains**: `*.status`, `*.l1_status`/`l2_status` fields
  appear on `AttendanceCorrection`, `LeaveRequest`, `WorkFromHomeRequest` —
  each duplicating the same 2-level approval shape as its own hardcoded
  column pair rather than a shared structure.

## 2. Permission-seeding data migrations

**Total: 39 migrations** that create/grant/revoke `Permission`/`RolePermission`
rows directly (verified via
`grep -rl "RolePermission.objects.(create|get_or_create|bulk_create)\|Permission.objects.(create|get_or_create|bulk_create)" apps/*/migrations/*.py`
— excludes migrations that only seed unrelated data, e.g. email templates,
even if their filename mentions "permission").

| App | Count |
|---|---|
| accounts | 33 |
| hrms | 2 |
| assessments | 1 |
| attendance | 1 |
| branch | 1 |
| payroll | 1 |
| performance | 1 |
| **Total** | **39** |

Notable pattern in the `accounts` list: several migrations exist purely to
correct an earlier migration's permission grant (`0045_remove_payroll_view_from_manager`,
`0070_revoke_settings_edit_from_branch_admin`,
`0092_remove_manager_recruitment_and_payroll_perms`,
`0119_fix_facial_recognition_approve_grants`,
`0120_fix_payroll_run_revoke_from_hr`,
`0174_revoke_edit_own_profile_from_employee_role`) — i.e. access-control
corrections currently require a developer to write and ship a migration,
confirming the master-prompt's underlying concern on this specific point.

## 3. Hardcoded business constants (outside models)

Each of these was independently re-verified, not assumed:

- **`apps/payroll/services_estimate.py`** — `_PF_DEFAULT_RATE = Decimal('12.00')`,
  `_PF_DEFAULT_CEILING = Decimal('15000.00')` (fallback-only, used when a
  branch has no `BranchPayrollConfig`). **Metro HRA is hardcoded**: 50% for
  metro / 40% for non-metro, as a literal `Decimal('50')`/`Decimal('40')` in
  two places in this file.
- **`apps/payroll/services_income_tax.py`** — confirmed to exist and fully
  hardcode India's FY2025-26 income-tax rules as module-level constants:
  standard deduction (old/new regime), rebate thresholds, 80C/80D/80CCD(1B)
  caps, a flat 4% cess rate, and the complete new-regime (115BAC) and
  old-regime slab tables as literal Python tuples. **Every one of these
  needs updating by a developer, in code, every financial year** — the
  single clearest "a tax consultant should be able to do this, not an
  engineer" case in the whole codebase.
- **`config/settings.py` `CELERY_BEAT_SCHEDULE`** — a hardcoded dict with 8
  scheduled jobs (missing-clockout checks, absence alerts, birthday wishes,
  annual leave reset, monthly leave accrual, carry-forward expiry, payroll
  approval reminders, review-cycle closing). Changing any job's schedule
  requires a code deploy.
- **`apps/notifications/models.py` `NotificationSettings`** — 8 hardcoded
  per-module boolean fields (`is_leave_enabled`, `is_expense_enabled`,
  `is_separation_enabled`, `is_payroll_enabled`, `is_approval_enabled`,
  `is_document_enabled`, `is_attendance_enabled`, `is_system_enabled`).
  Adding a 9th notification-emitting module needs a migration.
- **`Company` model** (`apps/accounts/models.py`) — docstring asserts
  "Single legal entity. Only one record ever exists in this table," and
  carries India-specific statutory fields (CIN, TAN, EPFO code, ESIC code,
  Professional Tax registration) directly on the model. **Confirmed: unlike
  `EmployeeCodeSettings` and `BirthdaySettings` (both explicit `pk=1`
  singletons with `get_or_create(pk=1)` enforced in code), `Company` has NO
  code-level enforcement of its own singleton-ness** — it's a convention
  only, not a guarantee. A second row could technically be created today
  with no error.
- **`LeaveType` asymmetry (confirmed, exact field definitions):**
  - `LeavePolicy.leave_type` — `CharField(max_length=50, unique=True)`, free
    text, no `choices=`. An admin can type any leave-type name here.
  - `LeaveBalance.leave_type` — `CharField(max_length=20, choices=LEAVE_TYPE_CHOICES)`
    — fixed, hardcoded enum.
  - `LeaveRequest.leave_type` — same fixed `LEAVE_TYPE_CHOICES` enum.
  - **Practical effect**: an admin can create a new leave type in
    `LeavePolicy` (e.g. "Marriage Leave") that can never actually be
    balanced or requested, because `LeaveBalance`/`LeaveRequest` only accept
    the ~8 values baked into `LEAVE_TYPE_CHOICES`. This is the one item from
    the whole master-prompt document that's both clearly real and clearly
    scoped enough to fix on its own, independent of any larger platform
    decision — flagged here, not fixed in this pass.

## What this document is for

This is a map, not a to-do list. None of the items above are urgent on their
own — they're all currently-working code with a specific category of
inflexibility. Decisions about which (if any) to convert into
admin-configurable data belong to a future, separately-scoped conversation
once there's a concrete business need driving the choice (see
`SECURITY_REMEDIATION.md` for the Phase 0 security half of this audit, and
chat history for why the full platform rewrite described in the original
master prompt was not undertaken wholesale).
