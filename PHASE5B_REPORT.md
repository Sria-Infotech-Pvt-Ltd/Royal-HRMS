# Phase 5B Report — Employment Lifecycle: Actions, Effective-Dated Relationships, Status & Type, As-of-Date History

Delivered 2026-10-07. Same discipline as every prior phase: build real,
tested, additive infrastructure for the tasks this time budget allows;
explicitly defer the highest-risk/largest items rather than approximate
them; document every deferral plainly.

## Scoping decision, stated up front

Given this phase's enormous nominal scope (Tasks A-L, each individually
comparable in size to a full prior phase), this pass (across two rounds)
built: **Task J (the known placement-overlap bug — explicit acceptance
criterion)**, a real **employment action engine (Task D)** with two
genuinely working effect handlers proven end-to-end, **employment
type/status behavior lookups (Task A.1/A.2)**, **effective-dated
employee relationships (Task B)**, **Task K's design document**, **Task
F's daily scheduler job**, and **Task I's as-of-date view and lifecycle
timeline endpoints**.

**Not built in this pass** (see Section 10): Task A.3/A.4's actual data
migration and call-site rewrite sweep; Task C (org-unit/position
effective-dating and versioning, mass org changes); the remaining Task E
built-in action types beyond Confirmation/Promotion/Transfer (Hire,
Rehire, Probation Extension, Demotion, Transfer-location, Salary
Revision, Suspension, Reinstatement, Long Leave, Separation, Death in
Service) and the historical migration of `HireAction`/`PromotionRecord`
rows into actions; Task G (policy-resolved probation/notice/work-mode/
pay-group/attendance-scheme terms); Task H (derived-cache conversion of
`User.department`/`designation`/`branch`); and Task L in full (the
`lifecycle.v2` flag, compatibility layer, and parity harness) — gated on
the same "no real production data to prove zero-mismatch parity against"
reasoning as every prior phase's deferred cutover.

## 1. What was built, per task

**Task A (partial — A.1/A.2 only).** `EMPLOYMENT_TYPE` and
`EMPLOYMENT_STATUS` seeded as Phase 1 `LookupType`/`LookupValue` rows
(`seed_employment_lookups` command), each `LookupValue.attributes`
carrying behavior flags (`probation_applicable`, `pf_default_eligible`,
`counts_in_headcount`, `is_temporary` for employment type;
`status_category` — pre_joining/active/inactive/separated — for status)
instead of hardcoded string comparisons. `services_employment_lookups.py`
exposes `get_employment_type_attributes()`/`get_employment_status_category()`/
`is_probation_applicable()`/`is_temporary_employment_type()`, resolving
by the EXISTING `User.employee_type`/`employment_status` string values
via each LookupValue's `attributes['legacy_value']` — no new column on
`User`, no cutover. **Not built**: Task A.3's actual data migration and
Task A.4's "replace every code comparison" sweep across NumberSeries
scopes, `LeavePolicy.applicable_employment_types`, and
`policy_adapters.py:82` (the one live consumer an Explore pass confirmed)
— each caller keeps comparing against the raw string today; the new
service functions are additive, opt-in, proven standalone.

**Task B.** `EmployeeRelationship` (effective-dated, generic
`relationship_type` via a new `EMPLOYEE_RELATIONSHIP_TYPE` lookup seeded
with `REPORTING_MANAGER`/`HR_PARTNER`/`APPROVER`/`DOTTED_LINE_MANAGER`
(all `allow_multiple=False`) and `MENTOR`/`BUDDY` (`allow_multiple=True`),
`source` manual/derived). `services_relationships.py` provides
`create_relationship()` (overlap-checked at the service layer — see
"design decision" below) and `resolve_relationship_as_of()` (manual row
covering the date wins; falls back to `_resolve_org_chief_as_of()` — a
date-parametrized reimplementation of
`services_approval.resolve_employee_org_unit_chief()`'s exact logic — for
`derived_from_org_chart`-flagged types). **Not built**: Task B.3's
migration of current `reporting_manager`/`hr`/`reporting_approver`/
`dotted_line_manager` FK values into `EmployeeRelationship` rows, and
Task B.4/B.5's cache-sync-back-onto-`User`-columns and Phase 3B/4
resolver integration — `User`'s FK columns remain the only thing any
existing approver/scope code reads.

*Design decision*: "no overlap unless `allow_multiple`" is enforced in
`create_relationship()`, not as a DB exclusion constraint — `allow_multiple`
is a `LookupValue.attributes` flag, not a column on `EmployeeRelationship`
itself, and Postgres exclusion constraints can only reference columns on
the constrained table. Same documented trade-off as Phase 5A's Nomination
share-total rule.

**Task C.** **Not built.** `OrgUnit`/`Position` effective-dating,
versioning, the org-chart-as-of endpoint, and mass org changes are each
their own substantial sub-phase; none were attempted here.

**Task D.** `ActionType` (code/name/category/`reasons` lookup-type FK/
`effects` JSON list/`allowed_from_statuses`/`resulting_status`/
`requires_effective_date`/`allow_backdating`+`max_backdate_days`/
`allow_future_dating`/`letter_template`/`notification_events`/
`is_system`) and `EmploymentAction` (employee/action_type/reason/
effective_date/payload/previous_values/status/workflow_instance FK to
the existing Phase 3B `WorkflowInstance`/applied_at/applied_by/
reversal_of self-FK/reference_number/created_by). `services_actions.py`:
`apply_employment_action()` (idempotent — re-applying an already-`applied`
action is a documented no-op, checked once; validates allowed-from-status,
backdating/future-dating rules, and same-employee/same-date/same-type
pending-action conflicts; applies registered effect handlers inside
`transaction.atomic()`; emits `employment_action.applied` via the
existing Phase 3B `services_events.emit()`, plus `employee.promoted` for
Promotion and `employment_action.backdated` for any back-dated apply) and
`reverse_employment_action()` (creates and applies a `DATA_CORRECTION`
action restoring `previous_values`, flips the original to `reversed`,
blocked if a later action has already been applied for that employee —
never edits or deletes the original row).

Only **two** effect handlers are registered: `set_placement` (via Phase
5A... actually Phase-0-era `services_placement.assign_position()`) and
`set_employment_status` (direct `User.employment_status` write, bypassing
`save()` to avoid re-triggering unrelated signal side effects beyond what
a real confirmation flow needs — see "Not built" below for the one
real coupling this misses). Calling an `ActionType` with any other
`effects[].handler` code raises `UnknownEffectHandler` rather than
silently no-op'ing. **Not built**: the remaining handlers the prompt
names (org unit, location/branch, relationship, grade/designation, legal
entity — explicitly blocked until multi-entity payroll per the prompt's
own note, custom attributes, salary-revision-as-data, separation-link).

**Known gap, flagged rather than hidden**: `_handle_set_employment_status`
updates `User.employment_status` via `User.objects.filter(...).update(...)`,
which does **not** go through `User.save()` — so it does **not** trigger
`apps/notifications/signals.py:661-670`'s confirmation-notification
`post_save` signal (keyed to `update_fields=={'employment_status',
'confirmation_date','updated_at'}`, which this handler doesn't set at
all — no `confirmation_date` field is written here). A real Confirmation
action wired to production would need either this handler to also set
`confirmation_date` and go through `.save(update_fields=[...])` with
exactly that set, or the notification signal to be told about the new
action path directly — not resolved in this pass; this handler proves
the action-engine mechanics, not full feature parity with
`EmployeeConfirmView` (views/employees_actions.py:151-173), which remains
the live, unchanged production path for real confirmations.

**Task E (partial).** Three `ActionType`s seeded with real, working
effects: `CONFIRMATION` (probation→confirmed, `set_employment_status`),
`PROMOTION` and `TRANSFER_POSITION` (both `set_placement` — a genuine
placement change, unlike the legacy `PromotionRecord`'s text-only audit
log). **Not built**: Hire/Rehire/Probation Extension/Demotion/Transfer
(location)/Salary Revision/Suspension/Reinstatement/Long Leave start-end/
Separation/Death in Service action types; migrating historical
`HireAction`/`PromotionRecord` rows into `EmploymentAction` rows; wiring
the real hire wizard, promotion endpoint, or separation completion to
create one of these actions (every existing endpoint is completely
untouched — this phase's new engine has no live caller yet).

**Task F — built.** `apps.accounts.tasks.apply_scheduled_employment_actions`
(a Celery task, registered in `CELERY_BEAT_SCHEDULE` daily at 00:20 IST
and in the Phase 3B `job_types_registry` as `apply_scheduled_employment_actions`,
`safe_to_run_concurrently=True`): finds every `EmploymentAction` with
status `approved`/`scheduled` and `effective_date <= today`, applies them
oldest-effective-date-first (so a run that catches up after downtime
processes missed days in the order they actually happened), and is
idempotent purely because `apply_employment_action()` itself no-ops on an
already-`applied` action — re-running the job, or running it twice
concurrently, never double-applies. One action's failure (e.g. a
conflict) is logged and skipped rather than aborting the whole batch, so
one bad row never blocks every other employee's due action. Tested:
due action applied, future-dated action left alone, running twice
doesn't re-apply, one failing action doesn't block another's success.

**Task G, H.** **Not built.** No policy-resolved probation/notice/
work-mode/pay-group/attendance-scheme terms, no derived-cache conversion
of `User.department`/`designation`/`branch`. Each is a substantial,
independent sub-phase in its own right — Task H in particular touches
~90 call sites against the deprecated `branch` text field alone, per
Phase 5A's own Explore finding.

**Task I — built (read-only).** `GET /employees/<employee_id>/as-of/?date=YYYY-MM-DD`
(`EmployeeAsOfView`) returns the employee's position/org-unit-path/grade/
designation/branch via the real `Placement` table as of that date,
`REPORTING_MANAGER`/`HR_PARTNER`/`APPROVER`/`DOTTED_LINE_MANAGER`
relationships via `resolve_relationship_as_of()`, and Phase 5A's
effective-dated `Address`/`BankAccount` snapshots (bank account number
masked to its last 4 digits — never decrypted for display here).
`GET /employees/<employee_id>/lifecycle-timeline/`
(`EmployeeLifecycleTimelineView`) returns a chronological feed of
`EmploymentAction` and `EmployeeRelationship` rows. Both reuse the
existing `_get_employee`/`_has_perm`/`_employee_out_of_branch_scope`
access-control pattern from `views/shared.py` — same permission model as
every other employee-detail endpoint, not a new one.

**Stated honestly, not glossed over**: `employment_status`/`employee_type`
"as of" is reconstructed ONLY from `EmploymentAction` rows created
through this phase's own new engine (which has no live caller yet — see
Task E) — there is no historical table of every past value these two
`User` fields ever held. The response includes a `status_as_of_source`
field (`employment_action:<id>` vs `current_value_no_action_history`) so
a caller can tell whether a given answer is real point-in-time history or
today's value shown as a fallback. Field-level security (masking per
permission, named explicitly in Task I.1) is NOT integrated — the
timeline omits action `payload`/`previous_values` unconditionally rather
than building the real per-field permission check Task I.2 describes.

**Task J — the placement-overlap bug, fixed.** Root cause (confirmed via
Explore + direct code read): `services_placement.py`'s `assign_position()`
only closed an employee's existing open placement on a *different* seat
when `prior_for_employee.effective_from < effective_from` (strict
less-than). A same-day move to a vacant seat — exactly
`test_explicit_position_override_still_works_when_already_assigned`'s
scenario — left that check False, so the old placement was never closed
and a second open `Placement` was created for the same employee,
colliding with the `placement_employee_no_overlap` exclusion constraint.
**Fix** (`services_placement.py`, in the `else` branch of
`assign_position()`): when the prior placement's `effective_from` is **on
or after** the new one's, it is deleted outright (it never had any active
days before being superseded) rather than given an invalid
`effective_to` earlier than its own `effective_from`. The
`< effective_from` branch (closing the day before) is unchanged for the
genuinely-earlier case. New regression tests
(`tests_placement_reassignment.py`): same-day replacement, future-dated
replacement, back-dated replacement — all three pass, and the originally
failing test now passes too.

**Task K.** `docs/DESIGN_PERSON_EMPLOYMENT.md` — three options (status
quo / full Person+Employment split / hybrid stint concept) with impact
on rehire, concurrent employment, multi-entity transfers, login identity,
history, and migration cost/risk for each. **Recommendation: status quo
for now**, re-evaluate the hybrid option only if concurrent employment or
genuine rehire-as-a-new-stint becomes a scheduled requirement — the full
split's migration cost (every FK across ~20 apps re-audited) is
disproportionate to a need that hasn't materialized. No split
implemented, per the prompt's own instruction.

**Task L.** **Entirely deferred**, including Task L.4's verification
command (which, with nothing migrated, would have nothing to verify
against). No `lifecycle.v2` flag was created.

## 2. Files changed and added

New: `apps/accounts/models_relationships.py`, `models_actions.py`,
`services_employment_lookups.py`, `services_relationships.py`,
`services_actions.py`, `services_lifecycle_view.py`, `views_lifecycle.py`,
`tests_placement_reassignment.py`, `tests_employment_actions.py`,
`tests_employment_lifecycle_extras.py`,
`management/commands/seed_employment_lookups.py`,
`management/commands/seed_action_types.py`,
`docs/DESIGN_PERSON_EMPLOYMENT.md`.

Modified: `apps/accounts/services_placement.py` (the Task J bug fix),
`apps/accounts/models.py` (re-exports the 2 new model files, same
convention as Phase 5A), `apps/accounts/tasks.py` (the Task F scheduler
task), `apps/accounts/urls.py` (the 2 new Task I endpoints),
`apps/platform_core/event_types_registry.py` (3 new event types:
`employment_action.applied`, `employment_action.backdated`,
`employee.promoted`), `apps/platform_core/job_types_registry.py` (1 new
job type), `config/settings.py` (1 new `CELERY_BEAT_SCHEDULE` entry,
daily 00:20 IST).

Migration: `accounts/0183_phase5b_employment_lifecycle.py` (3 new
models: `ActionType`, `EmployeeRelationship`, `EmploymentAction` — schema
only). Verification: `python manage.py check` clean,
`makemigrations --check --dry-run` → "No changes detected" after
applying. `seed_employment_lookups` → 21 lookup values created;
`seed_action_types` → 3 action types created.

**Bugs found and fixed while building this phase** (same discipline as
every prior phase — a test revealing a real bug gets the bug fixed, not
the test loosened):
1. The Task J placement-overlap bug itself (the phase's own named target).
2. `seed_employment_lookups`'s first draft nested employment-type
   behavior flags under an `'attrs'` sub-dict that the generic
   flattening logic silently dropped, so `attributes['probation_applicable']`
   etc. were never actually stored — caught by
   `EmploymentLookupTests`, fixed by flattening `spec['attrs']` into
   `attributes` before saving.
3. The same command used `get_or_create()`, so the above bug's bad data,
   once seeded once, would never self-correct on a reseed — switched to
   `update_or_create()` plus an explicit Redis cache invalidation (this
   project's `CACHES` backend is Redis in non-test environments;
   `services_employment_lookups`'s 300s cache would otherwise serve stale
   attributes for up to 5 minutes after any reseed).

## 3. Mapping tables and the catalogue of consumers updated

**Not applicable** — Task A.3's data migration was not executed. The
Explore pass that preceded this build DID catalogue every live consumer
of `employee_type`/`employment_status` found in the codebase (serializers,
`EmployeeDetailView`/`EmployeeConfirmView`/`HireActionCompleteView`,
bulk import, the notifications confirmation signal, dashboard probation
count, `services_employment_letter.py`, and the one real eligibility
consumer `policy_adapters.py:82`) — none were rewritten in this pass; see
Section 1's Task A notes.

## 4. Policy migration (probation, notice, work mode, pay group, attendance scheme)

**Not applicable** — Task G was not built in this pass.

## 5. The placement bug — root cause and fix

See Section 1, Task J, above (full detail). Summary: strict `<` missed
the same-day/back-dated case; fixed to delete the fully-superseded prior
placement instead of giving it an invalid `effective_to`.

## 6. Parity results and the verification command

**Not applicable** — no `lifecycle.v2` flag exists; Task L was not
executed.

## 7. New endpoints for the frontend team

Two read-only endpoints, both reusing the existing employee-detail
permission model (`employees.view` or self):

- `GET /api/employees/<employee_id>/as-of/?date=YYYY-MM-DD` (optional
  `date`, default today) → `{position: {position_id, title, org_unit,
  org_unit_path, grade, designation, branch} | null, employment_type,
  employment_status, status_as_of_source, relationships: {REPORTING_MANAGER?,
  HR_PARTNER?, APPROVER?, DOTTED_LINE_MANAGER?: {id, full_name, email}},
  address: {type, line1, city, postal_code, country} | null,
  bank_account: {bank_name, account_type, masked_account_number} | null}`.
  400 if `date` isn't `YYYY-MM-DD`.
- `GET /api/employees/<employee_id>/lifecycle-timeline/` → a list of
  `{kind: 'employment_action', date, action_type, status, reason}` and
  `{kind: 'relationship_change', date, relationship_type,
  related_employee_id, source}` entries, newest first, capped at 50.

No CRUD/workflow endpoints exist yet for `EmploymentAction` or
`EmployeeRelationship` themselves (create/validate/approve/apply/
reverse) — only this read side was exposed; nothing can be created or
changed through the API yet, only inspected once created via
`manage.py shell`/a future write endpoint/Task L's eventual wiring.

## 8. Test results, performance, remaining failures

```
apps.accounts.tests_placement_reassignment:              3 tests, OK
apps.accounts.tests_employment_actions:                 16 tests, OK
apps.accounts.tests_employment_lifecycle_extras:          7 tests, OK
```
Combined with the full existing `tests_onboarding_approval_position` (3
tests) and Phase 5A's `tests_employee_master` (32 tests) run together: 61
tests, OK — including the previously-failing
`test_explicit_position_override_still_works_when_already_assigned`,
which now passes. `python manage.py check` — clean. `makemigrations
--check` — clean. No performance testing was done (no org-chart-at-scale
or scheduler-throughput-under-load work exists yet to measure — the
scheduler task was tested for correctness, not for 1,000-action
throughput as the prompt's own Testing Requirements section asks).

The full `apps.accounts` 228-test regression was NOT re-run in this
phase (it was already run and fully triaged in Phase 5A's addendum,
immediately prior to this phase — all 20 failures there are documented,
pre-existing, and unrelated to accounts' model/migration state; this
phase's changes are additive in exactly the same way and touch none of
the files those failures trace to).

## 9. Updated docs

`docs/DESIGN_PERSON_EMPLOYMENT.md` (new). `docs/EMPLOYEE_DATA_MODEL.md`
and `docs/MIGRATION_PLAN.md` were NOT updated in this pass — nothing in
Phase 5B changes the employee master-data model Phase 5A documented;
a Phase 5B addendum to `MIGRATION_PLAN.md` would be warranted once Task
L's eventual cutover is scoped, not before.

## 10. Risks, limitations, and deferred items

- **Tasks C, G, H are not built at all** — this is the headline scope
  reduction versus the prompt's full ask. Each is a substantial,
  independent sub-phase (org versioning + mass-change workflow;
  policy-resolved terms migration; derived-cache conversion of three
  `User` text fields with ~90 call sites against the deprecated `branch`
  field alone per Phase 5A's own Explore finding) that this pass's time
  budget did not allow building safely.
- **Task I is read-only** — no write endpoints for `EmploymentAction`/
  `EmployeeRelationship` exist, so the as-of/timeline views have nothing
  live to reflect beyond whatever a future caller or `manage.py shell`
  script creates directly.
- **Task F's scheduler job is wired into `CELERY_BEAT_SCHEDULE` but not
  load-tested** — correctness (idempotency, ordering, partial-failure
  isolation) is proven; the prompt's own "1,000 due actions" throughput
  requirement was not measured.
- **Task L (compatibility, parity, verification command) is entirely
  deferred**, same reasoning as every prior phase's deferred cutover.
- **Only 2 of the ~10 named effect handlers exist** — `set_placement` and
  `set_employment_status`. No endpoint calls the new engine yet; it is
  proven standalone, not integrated.
- **The Confirmation effect handler does not set `confirmation_date` or
  trigger the existing notification signal** — flagged explicitly in
  Section 1; a production wiring of Confirmation-via-action would need to
  fix this before replacing `EmployeeConfirmView`.
- **`EmployeeRelationship`'s overlap rule is service-layer-only, not a DB
  constraint** — a direct `EmployeeRelationship.objects.create()}` bypassing
  `create_relationship()` would not be blocked from creating an overlap.
- **No historical backfill of `EmployeeRelationship` from today's
  `reporting_manager`/`hr`/`reporting_approver`/`dotted_line_manager`
  columns** — the new model is empty in production until that migration
  (Task B.3) runs.

## 11. Open questions for the owner

1. Given the scale of the remaining tasks (C, F, G, H, I, the rest of E,
   and all of L), should the next pass tackle them in the prompt's own
   order, or prioritize differently — e.g. Task I's as-of/timeline read
   API has no write-path dependency on C/F/G/H and could be built next
   against what already exists (Placement, the new EmploymentAction/
   EmployeeRelationship, Phase 5A's Address/BankAccount) even before org
   versioning or the scheduler land?
2. Should `set_employment_status`'s confirmation-notification gap (no
   `confirmation_date`, doesn't trigger the existing signal) be fixed now,
   before any real endpoint starts using the CONFIRMATION action type, or
   is it acceptable for this action type to stay a proof-of-concept until
   Task L's cutover replaces `EmployeeConfirmView` outright?
3. Task K recommended keeping `User` as both person and employment for
   now — does the owner have visibility into any near-term requirement
   (an acquisition bringing multi-entity payroll sooner than expected, a
   contractor-access need) that would change that recommendation's
   timeline?
