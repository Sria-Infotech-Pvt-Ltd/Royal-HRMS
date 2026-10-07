# Phase 6A Report — Leave & Holidays: Leave Types, Ledger, Accrual Engine, Holiday Calendars

Delivered 2026-10-07. Same discipline as every prior phase: build real,
tested, additive infrastructure for what this pass's time budget allows;
explicitly defer the largest/riskiest items; document every deferral
plainly rather than approximate it.

## Scoping decision, stated up front

This pass builds: **Task A** (the `LeaveType` master, the actual
`LeaveBalance`/`LeaveRequest.leave_type` field-widening defect fix, and
the `is_unpaid_lwp()` attribute replacing all 7 `LEAVE_LWP` code
comparisons), **Task C** (the `LeaveTransaction` ledger and its balance-
cache recomputation), **Task G** (comp-off earning and expiry, built from
scratch since none existed), **Task H** (holiday calendars, migrated from
the existing `Holiday` table with a zero-mismatch verification command),
and **Task I.3** (`leave_status_for(employee, date)` — the hook Phase 6B's
own prompt explicitly names as a Phase 6A dependency, built now so 6B has
something real to call).

**Not built in this pass** (see Section 9): Task B (leave plans and
per-type rules through the Phase 3A policy engine — eligibility rules,
assignments); Task D's full accrual/carry-forward/lapse/encashment
*engine* integration (the ledger and comp-off expiry exist and are
tested standalone, but the three existing scheduler jobs —
`reset_annual_leave_balances`, `accrue_monthly_leave_balances`,
`expire_unused_carry_forward` — were NOT rewritten to write through the
ledger; they still write `LeaveBalance` directly, exactly as before);
Task E (leave-year configurability beyond calendar year); Task F (leave
request improvements — hourly/short leave, on-behalf applications,
cancellation/extension, team calendar, conflict checks, custom fields);
Task J (admin tools — manual adjustments, bulk opening balances, the
year-end console); and Task K in full (the `leave.v2` flag, the
opening-ledger migration from real `LeaveBalance` data, and the parity/
verification harness) — gated on the same "no real production data to
prove zero-mismatch parity against" reasoning as every prior phase's
deferred cutover.

## 1. What was built, per task

**Task A.** `LeaveType` (code/name/unit day-or-hour/category lookup/
behavior flags `is_paid`, `is_unpaid_lwp`, `affects_attendance_as`,
`is_comp_off`, `counts_towards_service`, `requires_balance`,
`is_encashable`, `is_system`/legal_entity+country applicability/
sort_order). Seeded (`seed_leave_types`): the 8 built-in codes with
attributes reproducing today's behavior exactly (`lwp` is the only
`is_unpaid_lwp=True` row, `comp_off` is the only `is_comp_off=True` row,
`earned` is the only `is_encashable=True` row — matching
`services_settlement.py`'s hardcoded `LEAVE_EARNED`-only encashment,
confirmed by Explore), plus every distinct `LeavePolicy.leave_type` value
not already one of the 8.

**The actual defect fix (Task A.3)**: `LeaveBalance.leave_type` and
`LeaveRequest.leave_type` were both `CharField(max_length=20,
choices=LEAVE_TYPE_CHOICES)` — hard-capped to the 8 built-in codes, while
`LeavePolicy.leave_type` was always a free `CharField(50, unique=True)`
with no such constraint (Explore confirmed: `leave_policy.py`'s create
view already let admins create arbitrary custom-type policies that could
never get a matching balance or request row). Both fields are now
`CharField(max_length=50)`, no `choices=` — existing data is unaffected
(every legacy code fits within 50 chars) and this alone fixes the defect,
independent of any flag. A `leave_type_ref` FK to `LeaveType` was added
to both models alongside the existing CharField (nullable, not yet
backfilled or required — Task K's job). Tests
(`LeaveTypeDefectFixTests`) prove a custom `LeavePolicy` type can now get
both a `LeaveBalance` and a `LeaveRequest` row.

**Task A.4**: all 7 `LEAVE_LWP` comparisons found by Explore replaced
with `services_leave_ledger.is_unpaid_lwp(code)` (reads
`LeaveType.is_unpaid_lwp`, falling back to the old literal comparison if
the code isn't seeded yet — so behavior is identical even before
`seed_leave_types` runs, never worse than before):
- `apps/hrms/views/leave_policy.py:207` (balance-crediting skip)
- `apps/hrms/views/leave_requests.py:182` (balance-sufficiency check)
- `apps/hrms/views/leave_requests.py:228` (`is_lwp` flag on create)
- `apps/hrms/views/leave_shared.py:446` (`_deduct_balance` early return)
- `apps/hrms/views/leave_shared.py:502` (preview balance lookup)
- `apps/hrms/views/leave_shared.py:509` (LOP calculation skip)
- `apps/hrms/views/leave_shared.py:933` (`is_lwp` flag, second creation path)

**Task B.** **Not built.** Leave plans, per-type `LEAVE_RULES` policy
parameters, and eligibility-as-a-rule (replacing `applicable_*` JSON
lists) are untouched — `LeavePolicy` itself is not migrated onto the
Phase 3A policy engine in this pass.

**Task C.** `LeaveTransaction` (append-only; employee/leave_type FK/
leave_year/txn_type — all 15 types from the prompt's own list/quantity
(signed Decimal)/effective_date/expiry_date for lots/reason/run_id/
generic source link/created_by/reversal_of). `services_leave_ledger.py`'s
`recompute_balance_cache()` maps the ledger onto `LeaveBalance`'s existing
columns with a precisely documented formula (restated here): `total_days`
= sum of quantities for entitlement-affecting types (opening, accrual,
proration, adjustment, carry_forward_in, carry_forward_out, lapse —
lapse and carry_forward_out are stored negative so they net out
correctly); `used_days` = -1 × sum of usage types (availed,
availed_reversal, cancellation); `carried_forward` = sum of
carry_forward_in/out only (the net outstanding lot amount, not full
entitlement); `carry_forward_expiry_date` = the latest expiry among
carry_forward_in entries. **Simplification, stated plainly**: lot-level
partial consumption isn't tracked — a carry-forward or comp-off lot is
treated as a single quantity, not individually-expirable sub-lots:
reasonable for comp-off (nothing yet consumes a specific lot) but would
need real FIFO-by-expiry lot consumption before Task D's carry-forward
engine could honestly replace `expire_unused_carry_forward`.

**`create_transaction()` is NOT called from any existing write path** —
`tasks.py`'s three scheduler jobs and `leave_shared.py`'s
`_deduct_balance` still write `LeaveBalance` directly, unchanged. Only
this phase's own new code (comp-off earning) uses the ledger today.

**Task D.** **Not built** beyond what Task C/G's ledger provides
standalone. No `LeaveRun` model, no preview/commit/reversal workflow, no
rewrite of the 3 existing scheduler jobs to write through the ledger, no
life-event (Phase 5B action) reactions, no back-dated recomputation.

**Task E.** **Not built.** Leave year stays implicitly calendar-year
everywhere (`LeaveTransaction.leave_year` defaults to
`effective_date.year`) — no per-entity/per-plan financial-year or
anniversary-year configuration.

**Task F.** **Not built.** No hourly/short-leave duration type, no
leave-on-behalf, no partial cancellation/extension, no team calendar, no
conflict/staffing/blackout checks, no NumberSeries reference number, no
Phase 2 entity/custom-fields registration for `LeaveRequest`.

**Task G — comp-off, built from scratch.** Explore confirmed `comp_off`
had ZERO earning logic anywhere (a `LEAVE_TYPE_CHOICES` code with
`annual_days=0` and a policy-note admitting "earning mechanism doesn't
exist" — not an extension of anything, genuinely new).
`services_comp_off.grant_comp_off(employee, work_date, hours_worked=...,
is_full_day=..., expiry_days=60)` creates a `comp_off_earned` ledger lot
(>=8 hours -> 1 day, >=4 hours -> 0.5 day, below -> `CompOffError`,
matching the prompt's own example thresholds exactly) with its own
expiry date. `expire_comp_off_lots(as_of)` (a plain function, callable as
a future scheduler job — not yet registered in `job_types_registry`/
`CELERY_BEAT_SCHEDULE`, see Section 9) creates a `comp_off_expired`
reversal for any lot past expiry with none yet, tracked via
`reversal_of` — idempotent (re-running doesn't double-expire, tested).
**Simplification**: a lot is all-or-nothing (no partial consumption by an
availed leave request, since nothing in this pass wires leave-request
approval to the ledger) — stated in the module's own docstring.

**Task H — holiday calendars.** `HolidayCalendar` (code/name/year/
legal_entity/country/optional_holiday_quota), `HolidayCalendarEntry`
(date/name/holiday_type — reusing `Holiday`'s own `HOLIDAY_TYPE_CHOICES`
rather than inventing a lookup/is_optional/is_half_day/region text),
`HolidayCalendarAssignment` (calendar+branch-or-company-wide+effective
range). `migrate_holidays_to_calendars` groups every active `Holiday` row
by (year, branch) into one calendar each, idempotent via `get_or_create`.
`verify_holiday_calendar_migration` checks every legacy `Holiday` row has
a matching calendar entry — **zero mismatches**, confirmed (the dev
database has 0 active `Holiday` rows today, so this ran as a true
zero-row, zero-mismatch pass; the migration/verification logic itself is
proven via `HolidayCalendarMigrationTests`, which seeds a real `Holiday`
row and confirms end-to-end). `services_holiday_calendar.is_holiday_for_employee()`
is opt-in — `core.cache_service.HolidayCacheService` (the real resolver
`leave_shared.py`'s working-days calculation uses) is completely
untouched.

**Task I (partial — I.3 only).** `services_leave_status.leave_status_for(employee,
date)` returns `None` if no `approved` `LeaveRequest` covers the date
(pending/rejected/cancelled correctly excluded, matching every existing
attendance call site's own filter), else `{leave_request_id,
leave_type_code, portion: 'full'|'half', is_paid}` — `is_paid` is read
from the existing, already-correct `LeaveRequest.is_lwp` field, not
re-derived from `LeaveType.is_paid` (documented reasoning: `is_lwp` is
what every existing call site already trusts). **Not built**: Task I.1
(hourly/partial-leave combination — depends on Task F), I.2 (WFH/on-duty
integration), I.4 (the payroll LOP input service — Explore's own finding
that payroll's `lop_days` is entirely attendance-derived and
disconnected from `is_lwp`/`LeaveRequest` today is flagged as a real gap
for a future pass to bridge, not fixed here), I.5 (voice). The 3 existing
independent approved-leave-date resolvers in `apps/attendance`
(`services_absence.py`, `services_attendance.py`, `services_hr_ops.py`)
are untouched — migrating them onto `leave_status_for()` is explicitly
catalogued as deferred, since that's attendance's own processing
pipeline (Phase 6B's domain, not this phase's to touch).

**Task J, K.** **Not built.** No admin adjustment/bulk-import/year-end
console tools; no `leave.v2` flag; no opening-ledger migration from real
`LeaveBalance` data; no parity harness; no verification command beyond
the holiday-calendar one (Task H.4's, built because it was cheap and
self-contained — the much larger balance/eligibility/LOP verification
commands Task K.2 describes were not attempted).

## 2. Files changed and added

New: `apps/hrms/models_leave_ledger.py`, `models_holiday_calendar.py`,
`services_leave_ledger.py`, `services_comp_off.py`,
`services_holiday_calendar.py`, `services_leave_status.py`,
`tests_leave_ledger.py`, `management/commands/seed_leave_types.py`,
`management/commands/migrate_holidays_to_calendars.py`,
`management/commands/verify_holiday_calendar_migration.py`.

Modified: `apps/hrms/models.py` (the `leave_type`/`leave_type_ref` field
changes on `LeaveBalance`/`LeaveRequest`, re-exports the 2 new model
files), `apps/hrms/views/leave_shared.py`, `leave_requests.py`,
`leave_policy.py` (the 7 `LEAVE_LWP` → `is_unpaid_lwp()` replacements).

Migration: `hrms/0037_phase6a_leave_ledger_holiday_calendars.py` (3 new
model groups: `LeaveType`/`LeaveTransaction`,
`HolidayCalendar`/`HolidayCalendarEntry`/`HolidayCalendarAssignment`;
alters `LeaveBalance.leave_type`/`LeaveRequest.leave_type` — widened,
choices removed; adds `leave_type_ref` FK to both). Verification:
`python manage.py check` clean, `makemigrations --check --dry-run` →
"No changes detected". `seed_leave_types` → 8 created. No `LeavePolicy`
rows exist in the dev database beyond the built-ins, so 0 custom types
were found to seed in this run (the code path is tested separately via
`LeaveTypeDefectFixTests`, which creates a real custom `LeavePolicy` and
confirms it gets balance/request rows).

**No bugs found while building this phase** — all 22 new tests passed on
first run (same as Phase 5A, unlike most other phases where a test
revealed something to fix). The `LEAVE_LWP` → `is_unpaid_lwp()`
replacement was verified against the existing `apps/hrms/tests.py` suite
(50 tests combined with the 22 new ones) — see Section 6.

## 3. Mappings

- `LeavePolicy` fields → `LEAVE_RULES` parameters: **not applicable**,
  Task B not built.
- `applicable_*` lists → eligibility rules: **not applicable**, Task B
  not built.
- `LeaveBalance` columns → ledger: see Task C above (the precise
  `total_days`/`used_days`/`carried_forward`/`carry_forward_expiry_date`
  formula, stated once in `services_leave_ledger.py`'s own docstring and
  restated in Section 1 here).
- `Holiday` → calendars and assignments: one `HolidayCalendar` per
  (year, branch-or-company-wide), one `HolidayCalendarEntry` per holiday,
  one `HolidayCalendarAssignment` covering the full calendar year for
  that branch (or `branch=null` for company-wide) — see Task H above.
- Comp-off migration: **not applicable** — Explore confirmed no existing
  comp-off balances or earning mechanism exists to migrate from; comp-off
  is purely new in this pass.

## 4. Catalogue of call sites changed

The 7 `LEAVE_LWP` comparisons listed in Task A.4 above (all in
`apps/hrms/views/`) are the only call sites changed. Attendance's 3
independent approved-leave-date resolvers, payroll's `lop_days`
computation, separation settlement's encashment read, dashboards' and
voice commands' `LeaveBalance`/`LeaveRequest` reads — all catalogued by
the Explore pass that preceded this build, **none modified**.

## 5. Parity and verification results

- **Holiday calendar migration**: `verify_holiday_calendar_migration` →
  `Checked=0 Mismatches=0` in the dev database (no active `Holiday` rows
  exist there today); the logic itself is proven against a seeded test
  `Holiday` row in `HolidayCalendarMigrationTests`.
- **No `leave.v2` flag, no balance/eligibility/LOP parity harness** —
  Task K not executed, per the scoping decision above.

## 6. New endpoints for the frontend team

**None.** Every new model and service is plain Python/Django with no DRF
view wired up in this pass — proving the ledger, comp-off engine, holiday
calendars, and the leave-status hook work correctly, not yet exposing
them. A future pass would need: a balance-as-of/ledger-statement
endpoint (Task C.4), a comp-off grant endpoint (today only callable
directly), and holiday calendar CRUD/import-export (Task H.5).

## 7. Test results, performance, remaining failures

```
apps.hrms.tests_leave_ledger:  22 tests, OK (clean on first run)
```
Combined with the full existing `apps.hrms.tests` suite (28 tests): **50
tests, OK**. An earlier combined run reported `FAILED (errors=5)`, every
one of which was `django.db.utils.InterfaceError: connection already
closed` — the same transient Neon serverless flakiness this session has
documented and confirmed transient multiple times in earlier phases (by
re-running the identical command). Re-running the exact same combined
suite a second time produced a clean 50/50 pass with no code changes in
between, confirming it was environmental, not a regression from the
`LEAVE_LWP` → `is_unpaid_lwp()` replacement. `python manage.py check` —
clean. `makemigrations --check` — clean. No performance testing was done
(no 50,000-employee accrual-run or working-days-service-at-scale work
exists yet to measure, since Task D's engine integration wasn't built).

## 8. Updated docs

**Not updated in this pass** — `docs/MIGRATION_PLAN.md` and a new
`docs/LEAVE.md` were not written. Given the scale of what's deferred
(Tasks B, D's integration, E, F, J, K), a `docs/LEAVE.md` written now
would mostly describe infrastructure nothing calls yet; more useful to
write once Task B/D's integration gives it real behavior to document.

## 9. Risks, limitations, and deferred items

- **Tasks B, E, F, J are not built at all** — leave plans/eligibility
  rules, leave-year configurability, request improvements (hourly leave,
  on-behalf, cancellation/extension, team calendar, conflict checks), and
  admin tools (adjustments, bulk import, year-end console) are the
  headline scope reduction versus the prompt's full ask.
- **Task D's engine is NOT integrated** — the ledger and comp-off expiry
  are real and tested standalone, but `tasks.py`'s three existing
  scheduler jobs still write `LeaveBalance` directly, bypassing the
  ledger entirely. Turning any future `leave.v2` flag ON today would do
  nothing, because nothing reads from the ledger as a source of truth yet.
- **`expire_comp_off_lots` is not registered as a scheduler job** — it's
  a plain, tested function; wiring it into `job_types_registry`/
  `CELERY_BEAT_SCHEDULE` (the exact pattern Phase 5B's
  `apply_scheduled_employment_actions` used) is a small follow-up, not
  done here for scope reasons.
- **Payroll's LOP figure and hrms's `is_lwp`/LWP leave remain
  disconnected** — Explore's own finding, restated: an LWP leave day is
  neither deducted as an hrms balance (correctly) nor counted as payroll
  LOP (a real pre-existing gap, not introduced by this phase, left
  exactly as found).
- **Ledger lot consumption is all-or-nothing, not partial** — fine for
  comp-off today (nothing consumes a specific lot yet); would need real
  per-lot partial consumption before Task D's carry-forward engine could
  honestly replace `expire_unused_carry_forward`.
- **No historical backfill of `LeaveTransaction` from today's real
  `LeaveBalance` rows** — the ledger is empty in production until Task
  K's opening-migration runs.

## 10. Open questions for the owner

1. Given Task D's engine exists but isn't integrated, should the next
   pass prioritize rewriting the 3 existing scheduler jobs to write
   through the ledger (a bounded, testable change) before attempting
   Task B's full policy-engine migration (a much larger one)?
2. Should `expire_comp_off_lots` be wired into the scheduler now (cheap,
   self-contained) even before comp-off earning has a real caller
   (Phase 6B's attendance engine), so the expiry side is ready whenever
   6B starts granting lots?
3. The payroll/LWP disconnection (Section 9) predates this phase — does
   the owner want it bridged as part of Task D/I's eventual integration,
   or left for Phase 7 (payroll) to address from its own side?
