# Friday UAT Runbook — Employee Lifecycle (DRAFT, uncommitted)

Use a dedicated test employee, dummy documents (no real PAN/Aadhaar/bank data) and a test mailbox. Never run against production data.

## 1. Demo path

**Primary demo: Path A (HR Hire Employee wizard).** It covers every step of the agreed lifecycle in one pass.
HR hire -> invite email (72h link) -> employee sets password -> onboarding -> activation after first login -> profile -> attendance -> leave request -> manager/HR approval.

**Path B (candidate portal)** is a separate, shorter demo: candidate wizard -> submit -> HR approval. Run it only if the acceptance sentence needs it. Path B has more moving parts (the `_DENIED` defect below sits on this path).

Smallest complete demo = Path A end to end, plus one negative check from Path B only if required.

## 2. Leave balances at hire

- **Pro-rata (joining year):** at hire, `_allocate_leaves_for_employee` creates a balance per active leave policy.
  Formula: `annual_days x (13 - joining_month) / 12`, rounded to the nearest 0.5. The joining month counts as a full month (Jan = 12/12, Jul = 6/12, Dec = 1/12).
  Policies with `minimum_service_period > 0` are skipped. Policies restricted by branch, department, designation or gender are skipped if the employee does not match. It is idempotent (`get_or_create`).
- **Probation:** a policy with `allow_probation_leave = False` rejects leave requests from employees whose employment status is probation ("Employees on probation are not eligible for this leave type."). The balance still exists; the request is refused.
  **Before the demo:** pick the leave type to demo and confirm its `allow_probation_leave` in Leave Policy. If the test employee is on probation, either use a policy that allows it or move the employee out of probation.
- **HR top-up (needs `leave.approve`):**
  1. Find the balance record: `GET /api/leave/balance/?employee_id=<employee id>` (needs `employees.view`).
  2. Adjust it: `PATCH /api/leave/balance/<balance_id>/` with `total_days` (and/or `used_days`). This sets the value, it does not add to it.
  3. Bulk alternative: Opening Balance import (`/api/leave/balance/import/validate/` first, then `/import/`).
  - **Do NOT use `POST /api/leave/balance/credit/` for a single joiner.** It credits the **full annual days** (not pro-rata) to every active, onboarded employee who has no record for that year.
  - Balance records cannot be deleted; correct them with PATCH.

## 3. Environment verification checklist (test employee, dummy documents)

| Area | Check | Pass criteria |
|---|---|---|
| SMTP | Hire the test employee; check invite delivery and the Email Log | Mail arrives in the test mailbox; log status SENT only if no exception; link valid 72h |
| ImageKit | Upload a dummy PDF/JPG (under 5MB) and a profile photo on the test employee | Upload succeeds, file opens via returned URL; wrong type/oversize rejected. (`tests_employee_photo` fails locally with ImageKit 403, so this must be proven on the real env) |
| Live leave policy | Open Leave Policy; note annual days, `allow_probation_leave`, min service, restrictions; compare the test employee's balance to the formula above | Balance equals the formula result; request on an eligible type is accepted, ineligible type refused with the expected message |
| Geofence / Face ID | Clock in inside and outside the geofence; run a Face ID capture with a test face | Inside = allowed, outside = refused with distance message; Face ID policy matches branch setting |
| Redis | Confirm `REDIS_URL` is set on the server; log in twice, change a permission and confirm force re-login works | Cache, channel layer and sessions use Redis, not the in-memory fallback |
| Celery | Trigger an async action (interview-scheduled email or the scheduled employment-action task); check worker and beat logs | Worker connected to the broker; task runs. With no `REDIS_URL` tasks run eagerly (in-process), which would hide a missing worker |

## 4. Measuring blank-branch default-deny and onboarding-gate impact (read-only)

Do not run writes on production. Options, safest first:
1. **Restore a recent backup into a scratch database** and run the counts there.
2. **Read-only transaction on a replica/branch DB** (`BEGIN READ ONLY`) with the counts below.
3. **Django shell with `transaction.atomic()` and a forced rollback** only on a non-production copy.

Counts to take:
- Blank-branch impact: active employees where `branch` is empty or null, grouped by role and by whether they hold `leave.approve`, `employees.view` or manager scope. Those people lose branch-wide visibility under default-deny.
- Onboarding gate impact: active users whose `onboarding_status` is not `complete`, split by candidate-portal flag (`requires_self_service_onboarding`). Only candidate-portal users with a non-complete status are blocked. Users with `employees.view`, team managers and superusers are exempt.
- Report numbers as counts and ids only; no names or personal data in the report.

## 5. Test database used by the 372-test run

- `DATABASE_URL` pointed at the **local** PostgreSQL `hrms_local` on localhost:5432 with `DB_SSL_MODE=disable`; Redis was local DB 9.
- `TEST_DB_SUFFIX=fresh` with `--keepdb` makes Django use the separate database `test_neondb_fresh` (config/settings.py). Tests never write to `hrms_local` itself.
- No Neon or production connection string was used and `.env` was not modified.
- Not modified by this run: `hrms_local`, `test_hrms_local`, `test_neondb`. The earlier corruption of `test_hrms_local` (permissions 118 -> 37, baseline empty) came from an earlier broad regression run, not this one, and that database was left untouched afterwards.
- The log line shows "Using existing test database for alias 'default'"; the name is derived from settings, not printed. To prove it independently, list databases on the local server (`\l`) and compare table row counts before and after.

## 6. Known failures: release-blocking vs non-blocking

**Release-blocking for the demo or release**
- `_DENIED` NameError: `_DENIED` is used but never defined or imported in five recruitment view files: `referrals.py` (4 uses: ReferralBonusApprove/Pay denial paths), `candidate_portal.py`, `candidate_status.py`, `candidate_review_email.py`, `shared.py`.
  Effect: when the permission check refuses a request, the response is HTTP 500 instead of 403. It fails closed (no action is performed), so it is not a data-exposure defect, but any negative test or accidental denial on Path B or referrals shows a 500. The fix is locally tested, so Path B and referral UAT may proceed, subject to full UAT verification; Path A is not affected.
  **Status: FIXED — locally tested, uncommitted, not deployed.**
  **Evidence:** 9 focused denial tests passed; 166 related recruitment/onboarding tests passed. The tests reproduce the original NameError when the fix is removed.
  **Remaining:** verify the fix during full UAT.

**Known, non-blocking for the Path A demo**
- `tests_approver_route` and 4 leave pending-reservation tests: stale probation fixtures (test setup, not product).
- Carry-forward idempotence test, `tests_correction_review` x1, attendance `tests_face_id_policy` x2 (seed collision), ~5 payroll tests: pre-existing, outside this lifecycle. Payroll is not in the Friday scope.
- `tests_employee_photo`: ImageKit 403 locally; covered by the real-env ImageKit check in section 3.
- Unmocked SMTP error logs in test output: noise.
- Corrupted kept DB `test_hrms_local`: tooling issue; use `test_neondb_fresh`.

## 7. Proposed UAT sequence

0. Preflight (before Friday): section 3 checks, section 4 counts on a scratch copy, confirm the leave policy and probation setting, verify the locally tested `_DENIED` fix during UAT; deployment remains unauthorized.
1. HR hires the test employee through the wizard (dummy documents).
2. Verify invite email in the Email Log and mailbox.
3. Employee sets password, logs in; activation completes.
4. Employee completes onboarding / uploads dummy documents.
5. Check the profile and that masked fields (PAN/Aadhaar/bank) stay masked.
6. Check the pro-rata balance against the formula; HR top-up via PATCH if the demo needs more days.
7. Employee clocks in (geofence, Face ID).
8. Employee requests leave; manager or HR approves; balance updates.
9. Negative checks: blocked leave on probation policy, employee cannot open HR pages.
10. Path B demo is optional and must pass its UAT checks (including the permission-denial paths returning 403).
