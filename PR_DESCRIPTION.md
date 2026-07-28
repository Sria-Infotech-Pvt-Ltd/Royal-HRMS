# Voice Commands: Attendance, Leave, Approvals & Payroll

## Summary

Adds voice-command support (intent matching + execution) for attendance punches, leave self-service, manager/HR leave & attendance approvals, and — new in this revision — employee payroll self-service (`apps/voice_commands`). Voice input is normalized, matched against a YAML intent registry (`registry/intents_en.yaml`), and dispatched to the relevant domain view via a permission-gated executor. Multi-turn intents (slot-filling, disambiguation, confirmation) are tracked with a short-lived clarification cache so a user can answer a follow-up question in a later request.

## Architecture

```
voice_commands/
  matcher.py             fuzzy intent matching against registry/intents_en.yaml
  normalizer.py          transcript normalization
  slot_extractor.py      apply_leave slot-filling (leave_type, dates, reason)
  mode_extractor.py      attendance mode extraction (office/wfh/field/client_location)
  approval_extractor.py  name/target extraction for approve_leave / reject_leave
  payslip_extractor.py   name extraction + query description for the payroll intents
  clarification.py       Redis-backed pending-intent cache (120s sliding TTL)
  permissions.py         has_required_permission() — role → permission codename check
  conversation.py        turn-by-turn routing for attendance/leave/approval intents
  conversation_payroll.py  turn-by-turn routing for the two conversational payroll intents
  executor.py            thin dispatcher: permission gate + routes intent -> domain executor
  executor_attendance.py execute_clock_in/out, attendance stats/summary, correction request
  executor_leave.py      execute_apply_leave, check_leave_balance/status, cancel_leave
  executor_approval.py   execute_check_team_leave_queue/attendance, approve/reject_leave
  executor_payroll.py    execute_check_my_payslip, acknowledge_payslip, raise_payslip_query,
                         identify_employee_payslip
  executor_result.py     shared ExecutionResult dataclass (split out to avoid circular imports
                         between executor.py and the four domain executor modules)
  registry/intents_en.yaml  intent definitions: phrases, required_permission, conversational
  views.py / urls.py     /api/voice/parse/
```

`executor.py` was previously a single 591-line file handling every domain. It is now a thin
179-line dispatcher: it owns the `INTENT_*` constants and the permission gate, and routes each
intent to one of `executor_attendance.py`, `executor_leave.py`, `executor_approval.py`, or
`executor_payroll.py`. This mirrors the same split applied to `conversation.py`, which now
delegates the two conversational payroll intents to `conversation_payroll.py` rather than
growing past this project's 300-line file convention (`conversation.py` is 299 lines,
`conversation_payroll.py` is 154).

## Intents

| Intent | Permission | Conversational | Notes |
|---|---|---|---|
| `clock_in` / `clock_out` | — | no | `IsAuthenticated` only |
| `check_leave_balance` / `check_leave_status` / `cancel_leave` | — | no | own records only |
| `apply_leave` | — | **yes** | multi-turn slot-filling (leave_type, start_date, end_date, reason) |
| `check_attendance_stats` / `check_attendance_summary` | — | no | own attendance |
| `request_attendance_correction` | — | no | always defers to dashboard (no slot-filling yet) |
| `check_team_leave_queue` | `leave.approve` | no | team's pending leave queue |
| `check_team_attendance` | `attendance.view` | no | team attendance dashboard |
| `approve_leave` / `reject_leave` | `leave.approve` | **yes** | identify-then-**confirm**: fuzzy-match a name against the team's pending queue, ask yes/no, then act |
| `check_my_payslip` | `payroll.view_own` | no | own most recent payslip (`-cycle__cycle_start`), same codename `MyPayslipsView.get()` checks |
| `acknowledge_payslip` | `payroll.view_own` | no | acknowledges own most recent payslip; same codename as above (state-changing, but not a separate mutation codename) |
| `raise_payslip_query` | `payroll.view_own` | **yes** | raises an HR query on own most recent payslip; also the landing intent for "download my payslip"-style phrases |
| `check_employee_payslip` | `payroll.view` | **yes** | HR/admin only, **different** codename from the three above; identify-then-**respond** (see Known limitations) |

The four payroll intents are new in this revision. `check_my_payslip`, `acknowledge_payslip`,
and `raise_payslip_query` all gate on `payroll.view_own` — the same codename their underlying
views (`MyPayslipsView`, `AcknowledgePayslipView`, `PayslipQueryListView`) check, matched exactly
rather than introducing separate mutation-flavored codenames. `check_employee_payslip` gates on
`payroll.view` instead, the codename `PayslipDetailView.get()` requires to view anyone other
than the caller.

## Known limitations / follow-up

- **No payslip download/PDF capability exists anywhere in the codebase.** `EmployeePayslip.payslip_pdf`
  is defined on the model and exposed in the serializer, but nothing in `apps/payroll` — no view,
  service, or task — ever generates or populates it. Rather than a dead-end rejection, phrases like
  "download my payslip", "send me my payslip", "get my payslip pdf" are deliberately routed into
  `raise_payslip_query`: voice explains that payslip downloads aren't available yet and offers to
  raise a query with HR instead, rather than pretending to download anything.
- **`check_employee_payslip` can only look up one employee at a time by name.** There is no
  bulk/team-wide payroll list endpoint — `MyPayslipsView` hardcodes `employee=request.user`, and
  no equivalent view returns payroll records for a set of employees. This is unlike the leave/
  attendance approval intents (`check_team_leave_queue`, `check_team_attendance`), which return a
  whole team-scoped queue or dashboard; payroll has no analogous "pending payroll queue" concept
  to query against, so the voice flow searches the active-employee directory by name instead.
- `request_attendance_correction` still always defers to the dashboard — slot-filling for
  date/punch-type/time/reason hasn't been built.
- ~~Split `executor.py` into per-domain modules (file-size follow-up).~~ **Done** — see Architecture.

## Test plan

- [x] `python manage.py test apps.voice_commands` — 316 tests, OK
- [x] `python manage.py test apps.payroll` — 7 tests, OK
- [x] `python manage.py test apps.hrms` — 10 tests, OK (pre-existing, unrelated to this PR)
- [x] `python manage.py test apps.attendance` — 10 tests, OK (pre-existing, unrelated to this PR)
- [x] `python manage.py test apps.voice_commands apps.hrms apps.attendance apps.payroll` (full
      combined run requested for this PR) — 343 tests, OK
- [x] `python manage.py check` — 0 issues

Two totals matter here and they reconcile exactly — **316 + 7 + 10 + 10 = 343**:

- **323** (316 voice_commands + 7 payroll) is the test count for the two suites this PR actually
  changes, up from 246 before the payroll domain was added. 44 of the 323 are the new
  payroll-specific test files (`test_check_my_payslip.py`, `test_acknowledge_payslip.py`,
  `test_raise_payslip_query.py`, `test_check_employee_payslip.py`); the remainder are pre-existing
  attendance/leave/approval coverage inside `apps/voice_commands`, some of which was touched in
  this PR (import paths updated for the `executor.py` split, new matcher/permission-gate cases
  added).
- **343** is the full combined run across all four apps, adding `apps.hrms` (10 tests) and
  `apps.attendance` (10 tests) — neither touched by this PR, run alongside as a final regression
  check.

## Manual QA

Not yet done in-browser for this revision — reserved for a final manual smoke test before merge.
