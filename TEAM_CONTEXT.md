# Royal HRMS — Team Context

This file is updated at the end of each session. Read it at the start of any new session for quick orientation.

---

## Active Branch
`demo` — main working branch. All features merge here before deploy.

## Deployment
- Server: royalhrms.com
- Backend: port 8008 (Gunicorn + Django)
- Frontend: port 3001 (Next.js)
- User: royalhrmadmin
- Repo: Sriainfotech/Royal-HRMS, branch: demo

---

## Session Log — 2026-06-26

### Bug Fixes Shipped

**1. Cross-device cookie / proxy fix**
- Next.js rewrites `/api/*` → backend so browser never sees a cross-origin request
- `skipTrailingSlashRedirect: true` in `next.config.ts` + trailing slash forced in rewrite destination
- `APPEND_SLASH = False` added to `backend/config/settings.py`
- Fixes Django RuntimeError on POST requests coming through the proxy

**2. Flutter mobile auth (dual-source)**
- `backend/apps/accounts/authentication.py` — `CookieJWTAuthentication` now tries cookie first, then `Authorization: Bearer` header
- Login response now returns `access` + `refresh` tokens in body (in addition to cookies) for Flutter
- Token refresh accepts `refresh` from request body OR cookie — whichever is present

**3. Add Employee modal — dropdowns not loading**
- Root cause: branches API was pointing to wrong path (`/branches/` → fixed to `/branch/branches/`)
- Root cause 2: paginated response returns `{ count, results, ... }` not a flat array — code was calling `.filter()` on the object (silent TypeError)
- Fixed in `frontend/app/dashboard/employees/_components/AddEmployeeModal.tsx`

**4. Employee profile "not found"**
- Page was reading from `MOCK_EMPLOYEES` array (mock IDs had `D` suffix, real IDs don't)
- Added `EmployeeDetailView` to backend (`GET /api/employees/<employee_id>/`)
- Rewrote `frontend/app/dashboard/employees/[id]/page.tsx` to fetch from real API

### Features Shipped

**5. Employee Code Settings** (configurable ID format)
- New singleton model `EmployeeCodeSettings` — prefix, padding, next_sequence
- `generate_employee_id()` uses `select_for_update()` + atomic `F()` increment (safe under concurrent creates)
- Employee creation in `EmployeeListCreateView.post()` now calls `EmployeeCodeSettings.generate_employee_id()` instead of unsafe `count() + 1`
- Settings page: `frontend/app/dashboard/settings/employee-code/page.tsx` — live preview of next 3 IDs
- Card added to `frontend/app/dashboard/settings/page.tsx`
- Migration: `backend/apps/accounts/migrations/0020_employee_code_settings.py` ✅ applied
- `next_sequence` auto-seeded to `max_existing + 1` on deploy (was 6 as of this session)
- API: `GET/PUT /api/settings/employee-code/` — permission: `CanManageRoles`

**6. Branch-scoped employee list**
- `system_admin` sees all employees, gets a branch switcher dropdown in filter bar (derived client-side from employee list — no extra permission required)
- `hr_admin` sees only their branch (server-enforced in `EmployeeListCreateView.get()`) — fixed branch pill in filter bar, non-editable
- Branch column added to employee table
- `branch` field added to `UserInfo` interface and saved at login

**7. Branches sidebar visibility fix**
- `navConfig.ts` and `proxy.ts` — Branches entry was guarded by `settings.view`; `hr_admin` has `settings.view` so they saw Branches but got 403 from the API
- Fixed: both files now guard Branches with `branches.view`
- `hr_admin` no longer sees Branches in sidebar; proxy also blocks direct URL navigation

---

## Session Log — 2026-07-01
**Author: Teerdaveni**

### Features Shipped

**1. Attendance Settings API** (`/api/attendance/settings/`)
- `GET` reads current settings (upsert pattern — creates defaults on first call)
- `PUT` full save of all 6 sections (working hours, punch rules, overtime, weekly off, late mark, absence alert)
- `PATCH` partial update — send only changed sections, others untouched
- `first_error()` in `core/responses.py` rewritten to recursively handle nested serializer errors (previously showed generic "Validation error." for nested fields)
- Files: `attendance/serializers_settings.py`, `attendance/services.py`, `attendance/views/settings_view.py`

**2. My Attendance — Clock In / Clock Out** (`POST /api/attendance/punch/`)
- Immutable `AttendancePunch` model — every punch event stored, never overwritten
- Geofencing validated on every office punch using Haversine formula (pure Python, no library)
- Runs `AttendanceProcessorService` synchronously after each punch to keep `AttendanceRecord` current
- Returns full today-session in same response (no second GET needed from frontend)

**3. My Attendance — Dashboard APIs**
- `GET /api/attendance/today/` — ClockWidget: is_clocked_in, punch list, total_seconds, session_seconds
- `GET /api/attendance/stats/` — Stat cards: days_present, late_arrivals, avg_hours, attendance %
- `GET /api/attendance/summary/` — Monthly summary grid: working_days, days_present, absent, leave, half_day, OT hours
- `GET /api/attendance/calendar/` — Per-day calendar data + history table rows

**4. Attendance Correction Request** (`POST /api/attendance/correction/`)
- Employee submits regularization for missed/wrong punch
- Validates: date not in future, correct_in_time required for IN/BOTH, correct_out_time required for OUT/BOTH
- Guard: blocks duplicate pending correction for same date (409)
- Status flow: pending → approved/rejected (approval UI not yet built)

**5. Enterprise Geofencing**
- `Branch` model extended: `latitude`, `longitude`, `allowed_radius_meters` (default 150m), `geofencing_enabled`
- `GET/PUT /api/branch/branches/<pk>/geofencing/` — dedicated geofence config API
- `services_geofencing.py` — strategy pattern: `_MODE_VALIDATORS` maps attendance mode to validator function
- Office mode: Haversine distance → allow if within radius, reject with distance message
- WFH/field/client/remote modes: GPS stored for audit, no distance check
- Branch resolver: matches `User.branch` (CharField) against `Branch.branch_name`, falls back to `branch_code`

**6. Bug Fixes**
- GPS `DecimalField` → `FloatField` in punch serializer — `navigator.geolocation` returns JS floats with 15+ decimal digits which exceeded `max_digits` on DecimalField
- Branch model lat/lon upgraded to `max_digits=12, decimal_places=8` (was 10,7)
- `browser` field `max_length` 100 → 500, `operating_system` 100 → 200 (raw `navigator.userAgent` exceeds 100 chars)
- `TypeError: unsupported operand type Decimal vs float` in Haversine — fixed by casting `float()` before calculation
- CSRF trusted origins added for Django admin in development

### New Models

| Model | Table | Purpose |
|---|---|---|
| `AttendancePunch` | `attendance_punches` | Immutable raw punch events with full GPS + device audit trail |
| `AttendanceRecord` | `attendance_records` | Processed daily result per employee (present/late/absent/half_day) |
| `AttendanceCorrection` | `attendance_corrections` | Regularization requests submitted by employees |

### Migrations Applied

```
attendance/0008_attendance_transactions   — AttendancePunch, AttendanceRecord, AttendanceCorrection
attendance/0009_punch_geofencing          — GPS + device audit fields on AttendancePunch
attendance/0010_fix_gps_decimal_precision — lat/lon upgraded to DecimalField(12,8) on punch model
attendance/0011_punch_browser_field_length — browser 500, operating_system 200
branch/0004_branch_geofencing             — lat, lon, radius, geofencing_enabled on Branch
branch/0005_fix_gps_decimal_precision     — geofencing_enabled help_text fix
branch/0006_branch_gps_precision_12_8     — branch lat/lon upgraded to DecimalField(12,8)
```

### New Files

```
backend/apps/attendance/
  models.py                        — AttendancePunch, AttendanceRecord, AttendanceCorrection added
  serializers_settings.py          — AttendanceSettingsPatchSerializer added
  serializers_my_attendance.py     — all My Attendance read/write serializers
  services.py                      — partial_update() added to AttendanceSettingsService
  services_attendance.py           — PunchService, AttendanceProcessorService, AttendanceDashboardService
  services_geofencing.py           — GeofencingService, Haversine, branch resolver, mode validators
  views/my_attendance.py           — 6 APIViews for punch, today, stats, summary, calendar, correction
  views/settings_view.py           — PATCH method added
  urls.py                          — 6 new URL patterns
backend/apps/branch/
  models.py                        — geofencing fields added to Branch
  views.py                         — BranchGeofencingView added
  urls.py                          — geofencing URL added
backend/core/
  responses.py                     — first_error() rewritten for nested errors
backend/config/
  settings.py                      — CSRF_TRUSTED_ORIGINS for localhost dev
```

### API Reference — My Attendance

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/attendance/punch/` | Clock In / Clock Out |
| GET | `/api/attendance/today/` | ClockWidget session data |
| GET | `/api/attendance/stats/?month=&year=` | Stat cards |
| GET | `/api/attendance/summary/?month=&year=` | Monthly summary grid |
| GET | `/api/attendance/calendar/?month=&year=` | Calendar + history table |
| POST | `/api/attendance/correction/` | Regularization request |
| GET | `/api/branch/branches/<pk>/geofencing/` | Read branch geofence config |
| PUT | `/api/branch/branches/<pk>/geofencing/` | Update branch geofence config |

### Pending (resolved in 2026-07-02 session — see below)

- ~~Correction approval flow~~ — done
- Attendance reports — CSV/PDF download for HR
- Leave integration — auto-mark `on_leave` status when leave is approved
- Frontend implementation — prompts given to Teerdaveni, not yet started

---

## Session Log — 2026-07-02
**Author: Teerdaveni**

### Bug Fixes Shipped

**1. Celery connecting to Render Redis instead of local Redis**
- Root cause: `$env:REDIS_URL` was set as a Windows User-level environment variable, overriding `.env` file values
- Fix 1: Cleared the OS variable — `[System.Environment]::SetEnvironmentVariable('REDIS_URL', $null, 'User')`
- Fix 2: `environ.Env.read_env(BASE_DIR / '.env', overwrite=True)` in `settings.py` — forces `.env` to win over any OS env vars
- Fix 3: Added `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` to silence Celery 6.0 deprecation warning
- File: `backend/config/settings.py`

**2. Geofencing settings not saving (PATCH returned 200 but saved nothing)**
- Root cause 1: `BranchSerializer.Meta.fields` was missing `latitude`, `longitude`, `allowed_radius_meters`, `geofencing_enabled`, `has_coordinates` — DRF silently dropped unknown fields
- Root cause 2: Inline validation blocked enabling geofencing unless lat/lon were re-sent in the same request, even when the branch already had coordinates in DB
- Fix: Added all 5 geofencing fields to `BranchSerializer`; added explicit `has_coordinates = serializers.BooleanField(read_only=True)` (model `@property` not auto-detected by DRF); moved validation to post-assignment check using `branch.has_coordinates`
- File: `backend/apps/branch/serializers.py`, `backend/apps/branch/views.py`

**3. Geofencing not enforcing for Mumbai employees**
- Root cause: Mumbai branch had `geofencing_enabled=False` and no coordinates in DB — geofence code was correct
- Fix: Data configuration — admin must set lat/lon and enable geofencing per branch via `PUT /api/branch/branches/<pk>/geofencing/`
- Hyderabad HQ was the only branch with geofencing configured at time of diagnosis

**4. Punch times showing UTC instead of IST**
- Root cause: `timezone.now()` is UTC-aware; calling `.time()` directly gives UTC wall-clock time; shift_start/shift_end in `AttendanceWorkingHours` are plain IST times — late/early-exit comparisons were wrong
- Root cause 2: `timezone.now().date()` returns UTC date, which can differ from IST date after midnight IST
- Fix: Added `_ist_time(dt)` helper using `dt.astimezone(_IST).time()`; changed all `now.date()` → `timezone.localdate()` (IST-aware)
- Fix 2: `AttendancePunch.punch_date` property and `punch_time_display` property were calling `.date()` and `.strftime()` directly on UTC datetime — both fixed to use `astimezone(_IST)` first
- Files: `backend/apps/attendance/services_attendance.py`, `backend/apps/attendance/models.py`

### Features Shipped

**5. HR Attendance Management — Full API Suite**

All 11 HR endpoints built and wired. Backend only. Frontend prompts provided.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/attendance/dashboard/` | Dashboard stats (present/absent/late/OT counts) |
| GET | `/api/attendance/records/` | Paginated attendance list with filters |
| GET | `/api/attendance/records/<pk>/` | Single record detail + punch timeline |
| GET | `/api/attendance/overtime/` | OT entries list |
| POST | `/api/attendance/overtime/create/` | Create manual OT entry |
| GET | `/api/attendance/invalid-punches/` | Punches outside geofence or missing pair |
| GET | `/api/attendance/un-punches/` | Employees who punched IN but never punched OUT |
| POST | `/api/attendance/import/` | Bulk CSV import (max 5 MB) |
| GET | `/api/attendance/export/` | CSV export with same filters as list |
| POST | `/api/attendance/reprocess/` | Re-run processor for all employees on a date |
| GET | `/api/attendance/corrections/` | List all employee correction requests |
| PATCH | `/api/attendance/corrections/<pk>/review/` | Approve or reject a correction |

**6. HR Corrections Approval Flow**
- `approve_correction()`: creates `AttendancePunch` with `source='manual'` for the requested IN/OUT/BOTH times, then calls `AttendanceProcessorService.process_day()` — status flips from `incomplete` → `present` / `late`; employee drops off the Un-Punches list
- `reject_correction()`: marks rejected, no punch changes
- `_create_punch()` uses `get_or_create` to stay idempotent (safe to re-approve)
- File: `backend/apps/attendance/services_hr_corrections.py` (new, ~120 lines)

**7. Un-Punches ↔ Corrections Integration**
- `get_unpunches()` now also queries `AttendanceCorrection` for each returned employee on that date
- Each un-punch row now includes `correction_pending: bool` and `correction_id: uuid | null`
- Frontend can use these to show "Pending" badge on the un-punch row and link directly to the correction
- File: `backend/apps/attendance/services_hr_audit.py`

**8. Role-Based Branch Scoping**
- `system_admin` role + Django superusers: see all branches, all data
- `hr_admin` and all other roles: scoped to `user.branch` — cannot query outside their branch regardless of `?branch=` query param
- Two helpers added to `views/hr_attendance.py`:
  - `_is_unrestricted(user)` — checks `user.is_superuser` or `user.role.name == 'system_admin'`
  - `_branch_scope(user, requested)` — returns requested branch for unrestricted users, always returns `user.branch` for restricted users
- Applied to all 8 data endpoints: Dashboard, List, OT List, Invalid Punches, Un-Punches, Reprocess, Corrections List, Export
- File: `backend/apps/attendance/views/hr_attendance.py`

### New Files

```
backend/apps/attendance/
  services_hr.py               — get_dashboard_stats, get_attendance_list, get_attendance_detail, reprocess_date
  services_hr_audit.py         — get_invalid_punches, get_unpunches (with correction_pending flag)
  services_hr_ops.py           — list_overtime, create_overtime, import_attendance_csv, export_attendance_csv
  services_hr_corrections.py   — list_corrections, approve_correction, reject_correction
  serializers_hr.py            — all HR read/write serializers incl. CorrectionRowSerializer, UnpunchRowSerializer
  views/hr_attendance.py       — 12 HR APIViews + _is_unrestricted + _branch_scope helpers
```

### Files Modified

```
backend/apps/attendance/
  models.py                    — _ist_time fix for punch_date + punch_time_display properties
  services_attendance.py       — _ist_time() helper, timezone.localdate(), IST-correct late/early-exit checks
  views/__init__.py            — HRCorrectionListView, HRCorrectionReviewView exports added
  urls.py                      — 12 new HR URL patterns added
backend/apps/branch/
  serializers.py               — geofencing fields + has_coordinates added to BranchSerializer
  views.py                     — geofencing enable validation fixed
backend/config/
  settings.py                  — overwrite=True in read_env(), CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP
```

### Frontend Prompts Given (not yet implemented)

- **Geofencing UI**: lat/lon/radius inputs + enable toggle in branch settings form; show `has_coordinates` badge
- **Corrections UI**: Corrections tab in HR Attendance; approve/reject buttons; pending badge on un-punch rows
- **Branch scoping UI**: HR admin sees only their branch (locked dropdown); system_admin sees all; `isUnrestrictedUser()` helper
- **Punch log display**: Show only latest IN + latest OUT in ClockWidget punch log (filter client-side from full `punches[]` array)

### Pending

- Attendance reports — CSV/PDF download for HR
- Leave integration — auto-mark `on_leave` when leave approved
- Frontend implementation of all attendance pages (prompts given above)

---

## Session Log — 02-07-2026
**Author: G.Durga Prasad**
**Branch: Backend/Assignments**

### Changes Made

**1. Onboarding wizard URLs cleaned up**
- Removed redundant HTTP methods from `OnboardingView`
- `PATCH /onboarding/` (no-step) → now returns 405, use `PATCH /onboarding/step/<n>/`
- `PUT /onboarding/step/<n>/` → now returns 405, use `PATCH` instead
- `POST /onboarding/step/<n>/` → now returns 405, use `PATCH` instead
- Deleted dead `_patch_full_profile()` private method
- Wizard now has 7 clean URLs with no duplicate functionality

**2. Assessment participation counts on `GET /api/assessments/`**
- Added `assigned_count`, `pending_count`, `in_progress_count`, `completed_count` to `AssessmentSerializer`
- Added `candidates` array inline — each assessment now returns full list of candidates who took it
- Candidate entry includes: name, email, status, attempt_count, pass_score, score_awarded, pass_percentage

**3. `attempt_count` field added to `CandidateAssignment`**
- New `PositiveSmallIntegerField(default=1)` on `CandidateAssignment` model
- Migration `assessments/0004_candidateassignment_attempt_count` created and applied
- `RetryAssessmentView` now increments `attempt_count` on every retry

**4. `AssessmentCandidateSerializer` added**
- New serializer in `assessments/serializers.py`
- Returns: `candidate_id`, `candidate_name`, `candidate_email`, `status`, `attempt_count`, `pass_score`, `score_awarded`, `pass_percentage`, `completed_at`, `created_at`

### Files Changed

```
backend/apps/assessments/
  models.py                    — attempt_count field added to CandidateAssignment
  serializers.py               — AssessmentSerializer updated with counts + candidates; AssessmentCandidateSerializer added
  views/portal.py              — RetryAssessmentView increments attempt_count
  migrations/0004_*            — migration for attempt_count (applied)

backend/apps/accounts/
  views.py                     — OnboardingView: removed redundant HTTP methods, deleted _patch_full_profile()
```

### API Changes

| Endpoint | Change |
|---|---|
| `GET /api/assessments/` | Now returns counts + full candidates array per assessment |
| `PATCH /onboarding/` | Now returns 405 — use step-based PATCH |
| `PUT /onboarding/step/<n>/` | Now returns 405 — use PATCH |
| `POST /onboarding/step/<n>/` | Now returns 405 — use PATCH |
| `POST /api/assessments/<id>/retry/` | Now increments attempt_count |

### Migrations Applied

```
assessments/0004_candidateassignment_attempt_count  ✅ applied
```

---

## Session Log — 2026-07-03
**Author: Teerdaveni**
**Branch: backend/attendance-leave**

### Bug Fixes Shipped

**1. Attendance Calendar — incomplete month coverage**
- Root cause: `get_calendar()` only iterated over existing `AttendanceRecord` rows — days with no record (weekly off, future, absent days) were missing from the response
- Fix: Full month iteration using `calendar.monthrange()`; 4 up-front queries (records, leaves, pending corrections, weekly-off policy) replace N+1 per-day queries
- Status priority order: Holiday > Weekly Off > On Leave > record status > Absent; future days with no special status are omitted
- `STATUS_INCOMPLETE` now maps to label `"Missing Clock Out"` with `regularization_required: true`
- Added `_STATUS_COLOR` module constant mapping each status to a hex color
- New static methods on `AttendanceDashboardService`: `_build_day()`, `_weekly_off_days()`, `_leave_dates()`, `_pending_correction_dates()`
- `_weekly_off_days()`: reads `WeeklyDayPolicy` default → falls back to legacy `AttendanceWeeklyOff` → defaults to Saturday + Sunday
- `_leave_dates()`: single query for approved `LeaveRequest` rows in month range, expanded to set of dates
- `_pending_correction_dates()`: batch query replacing N per-day `_has_pending_correction()` calls
- File: `backend/apps/attendance/services_attendance.py`

**2. `DayRecordSerializer` — new fields added**
- Added `date` (YYYY-MM-DD string), `color` (hex), `regularization_required` (bool)
- File: `backend/apps/attendance/serializers_my_attendance.py`

**3. Assessment portal — 404 for non-candidate users**
- Root cause: `/api/assessments/my/` returned 404 when logged-in user had no linked `Candidate` record (employees, managers, HR admins)
- Fix: Returns `200 {assignments: [], all_complete: true}` instead of 404; also auto-corrects stale `assessment_status` to `complete` for these users
- Fixed `safurasamreen2003@gmail.com` — employee/manager account had stale `assessment_status: pending`
- File: `backend/apps/assessments/views/portal.py`

**4. Leave requests — managers/HR can't see their own pending requests**
- Root cause: `LeaveRequestListCreateView.get()` defaulted to the approval queue for any user with `leave.approve` permission — their own pending leaves were invisible
- Fix: Default scope changed to own requests for all users; `?scope=team` now required to see the approval queue
- Same fix applied to `LeaveStatsView.get()` — stats now reflect own requests by default
- File: `backend/apps/hrms/views/leave.py`

**5. Approve/reject buttons showing to leave applicant**
- Root cause: Serializer had no action flags — frontend used JWT role to decide button visibility
- Fix: Added `can_approve` and `can_cancel` boolean fields to `LeaveRequestSerializer`
  - `can_approve`: True only if requester has `leave.approve` perm AND is NOT the leave owner AND status is pending/l2_pending
  - `can_cancel`: True only if requester IS the leave owner AND status is pending/l2_pending
- Frontend should render action buttons based on these fields, not on role from JWT
- File: `backend/apps/hrms/serializers.py`

### Debugging Done

- **`/api/assessments/my/` 404**: Used Django shell + temporary debug print to trace the request user (`safurasamreen2003@gmail.com`, role=manager, RSS00008) — confirmed no `Candidate` linked
- **Candidate `portal_user` not found**: Shell confirmed `Candidate.objects.filter(portal_user=user)` returns correct result; issue was wrong email used in test (`@email.com` vs `@gmail.com`)
- **Leave not showing for Safura**: Shell confirmed she has 1 pending leave; root cause was scope defaulting to approval queue for approvers

### Data Fixes Applied

| User | Fix |
|---|---|
| `safurasamreen2003@gmail.com` | `assessment_status` corrected to `complete` |
| `taskforce1569@gmail.com` (Samreen) | `assessment_status` corrected to `complete` |
| `safurasamreenshaik@gmail.com` (Samreen) | `assessment_status` corrected to `complete` |
| Candidate ID 7 (G. Durga Prasad) | `portal_user` linked to `rithwikaveera@gmail.com` for testing |

### API Behaviour Changes

| Endpoint | Before | After |
|---|---|---|
| `GET /api/leave/requests/` | Managers/HR → approval queue | Everyone → own requests |
| `GET /api/leave/requests/?scope=team` | — | Approval queue for approvers |
| `GET /api/leave/stats/` | Managers/HR → team stats | Own stats |
| `GET /api/leave/stats/?scope=team` | — | Team stats for approvers |
| `GET /api/assessments/my/` | 404 for non-candidate users | 200 with empty assignments |
| `GET /api/attendance/calendar/` | Only days with records returned | All month days; weekly off + leaves included |

### Files Modified

```
backend/apps/attendance/
  services_attendance.py     — get_calendar() rewritten; _STATUS_COLOR added; 4 new static helpers
  serializers_my_attendance.py — DayRecordSerializer: date, color, regularization_required added

backend/apps/assessments/
  views/portal.py            — MyAssessmentView: 404 → 200 empty for non-candidate users

backend/apps/hrms/
  views/leave.py             — LeaveRequestListCreateView + LeaveStatsView: scope default fixed
  serializers.py             — LeaveRequestSerializer: can_approve + can_cancel fields added
```

---

## Session Log — 2026-07-06
**Author: Teerdaveni**
**Branch: attendance/back/03**

### Features Shipped

**1. Branch-wise leave visibility for HR users**
- `_approval_scope_filter(user)` now returns branch-scoped Q filter for `hr_admin` — if HR has a branch set, only employees in that branch are visible; otherwise falls back to `employee__hr=user`
- `_user_branch(user)` helper added — safely reads `user.branch` CharField
- `_can_hr_access_request(hr_user, leave_request)` guard added — used in `_get_request`, `LeaveApprovalView.get()`, and `LeaveApprovalView.post()` to block cross-branch access with 403
- File: `backend/apps/hrms/views/leave.py`

**2. Two-level leave approval workflow (Manager L1 → HR L2)**
- `_resolve_approval_chain(employee)` — checks `EmployeeApprovalOverride` first, falls back to `ApprovalWorkflowRule`; returns `(l1_approver, l2_approver)`
- `_resolve_approver(role_str, employee)` — maps rule role string to actual User FK
- `LeaveApprovalView.post()` — handles both `REQ_PENDING` (L1) and `REQ_L2_PENDING` (L2) states; promotes to l2_pending after L1 approval if l2_approver exists; deducts balance only on final approval
- File: `backend/apps/hrms/views/leave.py`

**3. Manager applies leave → routes directly to HR (skip L1)**
- Managers skip L1 — their leave is created with `status=REQ_L2_PENDING`, `l1_approver=None`, `l2_approver=HR`
- Other employees follow normal L1 → L2 path
- File: `backend/apps/hrms/views/leave.py` (`LeaveRequestListCreateView.post()`)

**4. `approved_by` / `approved_at` fields in leave response**
- `LeaveRequestSerializer` now has `approved_by` and `approved_at` computed fields
- `approved_by`: shows L2 approver name if L2 has acted, else L1 approver name
- `approved_at`: shows `l2_actioned_at` if available, else `l1_actioned_at`
- File: `backend/apps/hrms/serializers.py`

**5. Duplicate leave date validation**
- Before creating a new leave request, checks for overlapping dates in any active status (`pending`, `l2_pending`, `approved`)
- Uses `start_date__lte=end, end_date__gte=start` overlap query
- Rejected or cancelled leaves do not block re-application for the same dates
- File: `backend/apps/hrms/views/leave.py` (`LeaveRequestListCreateView.post()`)

**6. System admin pagination + branch-wise filtering**
- `GET /api/leave/requests/` now paginates with `default_page_size=20` for all roles
- `?branch=<branch_name>` query param supported for `system_admin` only — case-insensitive filter
- Same branch filter added to `LeaveCalendarView.get()`
- File: `backend/apps/hrms/views/leave.py`

**7. Week-off validation on leave application**
- `_get_weekly_off_days()` helper reads current DB config:
  1. `WeeklyDayPolicy` (is_active=True, is_default=True) → `weekly_off_days` property
  2. Falls back to legacy `AttendanceSettings → AttendanceWeeklyOff`
  3. Defaults to `{'saturday', 'sunday'}` if no DB config
- `LeaveRequestListCreateView.post()` iterates every date in the selected range; if any date is a configured week-off day, returns error: `"{Day} ({date}) is a configured week-off day. Leave cannot be applied on a week-off day."`
- Config changes take effect immediately (reads DB on every request, no server restart needed)
- File: `backend/apps/hrms/views/leave.py`

### Bug Fixes Shipped

**8. `_deduct_balance_safe` TypeError — Q vs F expression**
- Root cause: `Q('used_days') + days` — Q objects are filter expressions, not field references
- Fix: Changed to `F('used_days') + float(leave_request.total_days)`
- Added `F` to imports (`from django.db.models import Count, F, Q`)
- File: `backend/apps/hrms/views/leave.py`

**9. Rejection remarks not saving**
- Root cause: Backend read `request.data.get('remarks')` but Postman/frontend sent `reason`
- Fix: `remarks = (request.data.get('remarks') or request.data.get('reason') or '').strip()` — accepts both field names
- File: `backend/apps/hrms/views/leave.py`

### API Behaviour Changes

| Endpoint | Before | After |
|---|---|---|
| `GET /api/leave/requests/` | No pagination | Paginated (20/page) |
| `GET /api/leave/requests/?scope=team` | HR sees all statuses | HR sees only `l2_pending`; manager sees only `pending` |
| `GET /api/leave/requests/?branch=X` | Not supported | system_admin only — filters by branch |
| `POST /api/leave/requests/` | No week-off check | Blocks if any selected date falls on configured week-off day |
| `POST /api/leave/requests/approve/` | L1 approve → straight to approved | L1 approve → l2_pending (if l2 exists); L2 approve → approved + balance deducted |
| `POST /api/leave/requests/approve/` | Only reads `remarks` | Accepts `remarks` or `reason` (both work) |
| `GET /api/leave/requests/<id>/` | Response has no approver info | Returns `approved_by` (name) and `approved_at` (timestamp) |

### Files Modified

```
backend/apps/hrms/
  views/leave.py   — _user_branch, _can_hr_access_request, _approval_scope_filter (branch+status scoped),
                     _resolve_approver, _resolve_approval_chain, _get_weekly_off_days,
                     LeaveRequestListCreateView (duplicate check, week-off validation, manager routing, pagination, branch filter),
                     LeaveApprovalView (two-level flow, branch guard, remarks fix),
                     _deduct_balance_safe (F() fix)
  serializers.py   — LeaveRequestSerializer: approved_by + approved_at fields added
```

### Pending

- Leave integration — auto-mark employee as `on_leave` in attendance when leave approved
- Frontend leave pages — prompts not yet given this session
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-07
**Author: Teerdaveni**

### Bug Fixes Shipped

**1. Celery Beat `unknown command HELLO` crash loop**
- Root cause 1: Previous session added `?protocol=2` to Redis URL — kombu rejected it with `TypeError: Connection._init_params() got an unexpected keyword argument 'protocol'`
- Fix: Removed `protocol=2` suffix from `_celery_redis_url()` in `settings.py`
- Root cause 2 (original HELLO error): redis-py ≥ 4.0 sends `HELLO 3` to Redis server < 6.0 which does not support it
- Fix: Downgrade redis-py — `pip install "redis>=3.5.3,<4.0"`
- File: `backend/config/settings.py`

**2. Sandwich Leave calculation counted only working days**
- Root cause: `_calc_working_days()` used hardcoded `weekday() < 5` (Mon–Fri) — weekends always skipped regardless of policy
- Fix: Rewrote `_calc_working_days()` to read `_get_weekly_off_days()` from DB and accept optional `policy` param; when `sandwich_leave_enabled=True`, all calendar days in range are counted (including weekends and holidays)
- Week-off blocking validation is now skipped when `sandwich_leave_enabled=True` or `count_weekoffs_as_leave=True`
- File: `backend/apps/hrms/views/leave.py`

### Features Shipped

**3. Leave Policies Module — Full Implementation**

Extended existing `LeavePolicy` model with 30 new fields across 5 rule sections. No new model or service files created — all changes in existing files only.

**New fields on `LeavePolicy` model:**

| Section | Fields |
|---|---|
| Leave Application Rules | `minimum_leave_duration`, `maximum_leave_duration`, `maximum_consecutive_days`, `minimum_notice_period`, `allow_half_day`, `allow_backdated_leave`, `maximum_backdated_days`, `allow_future_leave`, `maximum_future_days` |
| Holiday & Week-off Rules | `sandwich_leave_enabled`, `count_holidays_as_leave`, `count_weekoffs_as_leave` |
| Eligibility Rules | `applicable_branches`, `applicable_departments`, `applicable_designations`, `applicable_employment_types`, `applicable_gender`, `minimum_service_period` |
| Documentation Rules | `attachment_required`, `medical_certificate_required`, `medical_certificate_after_days` |
| Leave Restrictions | `allow_negative_balance`, `convert_to_lop`, `allow_leave_cancellation`, `cancellation_allowed_until` |
| Additional Rules | `allow_probation_leave`, `allow_notice_period_leave`, `allow_leave_extension`, `allow_leave_combination` |

**New APIs:**

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/leave/policy/` | Returns all 30 new fields per policy |
| PUT/PATCH | `/api/leave/policy/<leave_type>/` | Updates all fields with cross-field validation |
| POST | `/api/leave/policy/` | Creates custom leave type with all fields |
| DELETE | `/api/leave/policy/<leave_type>/` | Custom types only — built-in 6 are protected |

**Leave application validation wired to policy:**
- `_validate_leave_policy()` helper (47 lines) validates every leave request against the saved policy
- Validates: half-day eligibility, min/max duration, max consecutive days, notice period, backdated/future date rules, attachment requirement, eligibility (branch/dept/gender/service period)
- `convert_to_lop=True`: auto-converts leave type to LWP when balance is insufficient instead of rejecting
- `allow_negative_balance=True`: allows overdraft without error
- Custom leave types now accepted in `LeaveRequestCreateSerializer.validate_leave_type()` (checks `LeavePolicy` for non-built-in types)

**Migration:** `hrms/0009_leavepolicy_application_rules` — applied ✅

### Files Modified

```
backend/apps/hrms/
  models.py                   — 30 new fields on LeavePolicy; GENDER_CHOICES constant added
  serializers.py              — LeavePolicySerializer, LeavePolicyCreateSerializer,
                                LeavePolicyUpdateSerializer extended with all 30 fields;
                                _POLICY_RULE_FIELDS shared list; cross-field validation added;
                                LeaveRequestCreateSerializer.validate_leave_type accepts custom types
  views/leave.py              — _calc_working_days() updated (policy param, sandwich/weekoff aware);
                                _validate_leave_policy() helper added;
                                LeavePolicyView.delete() added;
                                LeavePolicyView.post() uses **data spread for new fields;
                                LeaveRequestListCreateView.post() wired to policy validation,
                                LOP conversion, allow_negative_balance
  migrations/
    0009_leavepolicy_application_rules.py  — 30 AddField operations (applied)
backend/config/
  settings.py                 — _celery_redis_url() protocol=2 suffix removed
```

### Frontend Prompts Given

- **Leave Policy APIs**: Full request/response format for all 5 endpoints with field reference table, conditional UI rules (show/hide dependent fields), and leave application error messages
- **Sandwich Leave preview fix**: `calcWorkingDays()` must count all calendar days (not skip weekends) when `sandwich_leave_enabled=True`; read flag from `GET /api/leave/policy/` response for the selected leave type

### Pending

- Frontend implementation of Leave Policies settings page (UI from screenshots provided)
- Frontend day counter fix — "2 working days" preview should show "4 days" when sandwich leave is on
- Leave integration — auto-mark employee `on_leave` in attendance when leave is approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-08
**Author: Teerdaveni**

### Features Shipped

**1. Convert Insufficient Balance to LOP — Full Backend Implementation**

Implemented the split-balance logic so that when `convert_to_lop=True` on a `LeavePolicy`, leave requests that exceed the available balance are allowed — available balance is consumed first, and only the excess days become LOP.

**Business rule implemented:**
- `convert_to_lop=OFF`: block submission if balance insufficient (unchanged)
- `convert_to_lop=ON`: allow submission; record `lop_days = requested - available`; `leave_type` stays as original (e.g. `earned`) — NOT converted to LWP

**Example (from requirement):**
- Earned Leave available: 15 days
- Requested: 18 working days
- `lop_days = 3.0`, `leave_type = earned`, `total_days = 18`
- On final approval: 15 days deducted from earned balance, 3 days treated as LOP

**Old behaviour (wrong):**
```python
if policy.convert_to_lop:
    leave_type = LEAVE_LWP  # converted entire leave to LWP
```

**New behaviour (correct):**
```python
if policy.convert_to_lop:
    lop_days = round(total_days - available, 1)  # only excess; leave_type unchanged
```

**Approval deduction fix:**
`_deduct_balance_safe()` now deducts only `total_days - lop_days` from the original leave balance. Previously it deducted `total_days` which would over-deduct.

### Files Modified

```
backend/apps/hrms/
  models.py            — Added lop_days DecimalField(default=0) to LeaveRequest
  serializers.py       — Added lop_days to LeaveRequestSerializer.Meta.fields
  views/leave.py       — Balance check: lop_days computed instead of switching leave_type to LWP
                         _deduct_balance_safe(): deducts (total_days - lop_days) on approval
  migrations/
    0010_leaverequest_lop_days.py  — AddField lop_days to hrms_leave_requests (applied ✅)
```

### API Response (new fields)

```json
{
  "leave_type": "earned",
  "total_days": 18.0,
  "lop_days": 3.0,
  "is_lwp": false
}
```

Frontend derives: `earned_leave_used = total_days - lop_days`

### Frontend Changes Needed (not yet done)

- Leave application form: when `convert_to_lop=true` and requested > available, show breakdown panel instead of "Exceeds balance by Nd"
- Detail/history card: show split `Earned Leave: 15d / LOP: 3d / Total: 18d` when `lop_days > 0`
- HR/approver view: same split display so approver sees what will be deducted

---

**2. Holiday Calendar — Phase 1 Backend Implementation**

New `Holiday` model and full CRUD API. Wired into leave day calculation.

**Model fields:**
- `id` (UUID PK), `name`, `date`, `holiday_type` (national/regional/company), `is_optional` (bool — separate from type), `description`, `branch` (FK, null = company-wide), `is_active`, `created_at`, `updated_at`
- `is_optional=True` means employee-choice restricted holiday — NOT a fourth holiday type

**API endpoints added:**

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/api/leave/holidays/` | Filters: `year`, `month`, `type`, `optional=true`, `branch` |
| POST | `/api/leave/holidays/` | Requires `settings.edit` or `leave.approve` |
| GET | `/api/leave/holidays/<id>/` | Single holiday detail |
| PUT/PATCH | `/api/leave/holidays/<id>/` | Same permission as POST |
| DELETE | `/api/leave/holidays/<id>/` | Same permission |

**GET response shape:**
```json
{
  "holidays": [
    {
      "id": "...", "name": "Independence Day", "date": "2026-08-15",
      "day": "Sat", "holiday_type": "national", "is_optional": false,
      "mandatory_optional": "Mandatory", "branch_name": null
    }
  ],
  "total": 6
}
```

**Leave calculation integration:**
- `_get_holiday_dates(start, end, branch_name)` — returns set of `date` objects for active holidays in range (branch-scoped)
- `_calc_working_days()` updated: when `count_holidays_as_leave=False`, holiday dates are excluded from the day count (same as week-off exclusion)
- Sandwich leave still overrides all exclusions — sandwich day is always counted

**Seed data (6 records created via Django shell):**

| Name | Date | Type | Optional |
|---|---|---|---|
| Republic Day | 2026-01-26 | national | No |
| Holi | 2026-03-25 | regional | No |
| Good Friday | 2026-04-03 | national | No |
| Ugadi | 2026-04-06 | regional | Yes |
| Independence Day | 2026-08-15 | national | No |
| Diwali | 2026-10-20 | company | No |

### Files Modified

```
backend/apps/hrms/
  models.py              — Holiday model + HOLIDAY_TYPE_CHOICES added;
                           lop_days DecimalField added to LeaveRequest
  serializers.py         — HolidaySerializer (day, mandatory_optional computed fields);
                           HolidayCreateSerializer; lop_days in LeaveRequestSerializer
  views/leave.py         — _get_holiday_dates() helper added;
                           _calc_working_days() updated (count_holidays_as_leave wired);
                           LOP balance split logic implemented;
                           _deduct_balance_safe() deducts (total_days - lop_days)
  views/holidays.py      — NEW FILE: HolidayListCreateView, HolidayDetailView
  views/__init__.py      — HolidayListCreateView, HolidayDetailView exported
  urls.py                — /leave/holidays/ and /leave/holidays/<id>/ routes added
  migrations/
    0010_leaverequest_lop_days.py  — AddField lop_days ✅
    0011_holiday.py                — CreateModel Holiday ✅
    0012_holiday_is_optional.py    — AddField is_optional, removed 'optional' from holiday_type choices ✅
```

---

**3. Employee Profile — Leave & Attendance API Integration**

Added `?employee_id=EMP001` support to 5 existing endpoints so HR can view another employee's full Leave and Attendance profile. No new APIs, no new models — extensions of existing views only.

**Endpoints extended:**

| Endpoint | Before | After |
|---|---|---|
| `GET /api/leave/requests/` | Own requests only | `?employee_id=` returns that employee's full leave history |
| `GET /api/leave/stats/` | Own stats | `?employee_id=` returns target employee's stats + balances + new `lop_days` field |
| `GET /api/attendance/stats/` | Own stats | `?employee_id=` returns target employee's attendance stat cards |
| `GET /api/attendance/summary/` | Own summary | `?employee_id=` returns target employee's monthly summary grid |
| `GET /api/attendance/calendar/` | Own calendar | `?employee_id=` returns target employee's calendar + history |

**Permission gate:** caller must have `employees.view` or `attendance.view` (attendance endpoints) / `leave.approve` (leave endpoints) to use `employee_id` param.

**No change needed for:**
- `GET /api/leave/balance/?employee_id=` — already worked
- `GET /api/employees/<id>/approval-matrix/` — already worked

**New field in leave stats response:**
```json
{ "lop_days": 3.0, "balances": [...] }
```

### Files Modified

```
backend/apps/hrms/views/leave.py
  — Sum added to django.db.models imports
  — LeaveRequestListCreateView.get(): employee_id param resolves target user
  — LeaveStatsView.get(): employee_id param + lop_days aggregate added to response

backend/apps/attendance/views/my_attendance.py
  — _has_perm() helper added (role-based permission check)
  — _resolve_target_user() helper added (resolves employee_id or falls back to request.user)
  — AttendanceStatsView.get(): passes target to service
  — AttendanceSummaryView.get(): passes target to service
  — AttendanceCalendarView.get(): passes target to service
```

### Frontend Changes Needed (for Employee Profile page)

Pass `?employee_id=EMP001` when HR opens another employee's profile tab:
- Leave tab → `GET /api/leave/requests/?employee_id=EMP001`
- Leave tab → `GET /api/leave/stats/?employee_id=EMP001&year=2026` (includes `lop_days` field now)
- Attendance tab → `GET /api/attendance/stats/?employee_id=EMP001&month=7&year=2026`
- Attendance tab → `GET /api/attendance/summary/?employee_id=EMP001&month=7&year=2026`
- Attendance tab → `GET /api/attendance/calendar/?employee_id=EMP001&month=7&year=2026`
- When viewing own profile: omit `employee_id` — endpoints fall back to `request.user`

### Pending

- Frontend UI for LOP breakdown display
- Frontend Employee Profile page — wire `?employee_id=` to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave is approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-09
**Author: Teerdaveni**

### Features Shipped

**1. Attendance Calendar — Frontend Holiday Integration**

Fixed a long-standing silent breakage: `STATUS_CONFIG` used lowercase keys (`'holiday'`, `'present'`) but `STATUS_DISPLAY_MAP` on the backend sends capitalised display strings (`'Holiday'`, `'Present'`). Every `STATUS_CONFIG[record.status]` lookup returned `undefined`, making all calendar cells transparent with no status labels.

Fixes applied:
- `DayRecord` interface updated — added `color: string`, `date: string`, `regularization_required: boolean`; `status` widened from narrow lowercase union to `string`
- `AttendanceCalendar.tsx` — replaced `STATUS_CONFIG` entirely with `STATUS_LABELS` (keyed by capitalised display strings); uses `record.color` (hex from `_STATUS_COLOR` on backend) for foreground; background derived as `record.color + '26'` (15% opacity); `NON_WORKING` set suppresses clock-in/out on Holiday and Weekly Off cells; `canRegularize` already `false` for holidays from backend
- `CalendarAndHistory.tsx` — fixed swapped legend colours: Holiday is `#a855f7` (purple), On Leave is `#3b82f6` (blue) — was reversed

Files changed:
```
frontend/types/attendance.ts                              — DayRecord interface updated
frontend/app/dashboard/my-attendance/_components/
  AttendanceCalendar.tsx                                  — STATUS_LABELS, record.color, NON_WORKING
  CalendarAndHistory.tsx                                  — legend colours corrected
```

---

**2. Leave Validation — Improved Zero-Working-Days Error Messages**

Replaced the generic `"Selected date range results in zero working days."` error with specific user-friendly messages.

New helper `_zero_working_days_reason(start, end, policy, employee)` in `leave.py` diagnoses why a range has no working days:

| Scenario | Message |
|---|---|
| Single day — holiday | "The selected date is a public holiday. Please choose a working day." |
| Single day — week-off | "The selected date falls on a weekly off (Sunday). Please choose a working day." |
| Range — all holidays | "All selected dates are public holidays. Please select at least one working day…" |
| Range — all week-offs | "All selected dates fall on weekly off days. Please select at least one working day…" |
| Range — mixed | "The selected date range contains only holidays and weekly off days. Please select…" |

Policy flags (`count_weekoffs_as_leave`, `count_holidays_as_leave`) are respected — if a policy counts holidays as leave days, holidays are not blamed in the message.

---

**3. LOP Calculation Bug Fix — Spurious Week-off Block Removed**

Root cause: A validation block (lines 532–544 in old code) rejected any leave request whose date range spanned a week-off day when `count_offs=False && sandwich=False`. This prevented Scenario 2 (employee selects 20 calendar days spanning 3 week-offs and 2 holidays; policy excludes them → 15 actual working days → zero LOP).

Fix: removed the entire block. `_calc_working_days()` already correctly excludes week-offs when `count_offs=False`. The existing `total_days <= 0` check handles the edge case where ALL selected days are week-offs.

Business rule order confirmed:
1. `_calc_working_days()` applies sandwich / holiday / week-off policy → actual leave days
2. Compare actual leave days with available balance
3. LOP = `max(0, actual_days - available)` — never uses raw calendar days

---

**4. Leave Preview Endpoint — `GET /api/leave/requests/?action=preview`**

New read-only calculation branch added to the existing `LeaveRequestListCreateView.get()`. No new URL, no new file.

**Query params:** `action=preview`, `leave_type`, `start_date` (YYYY-MM-DD), `end_date`, `duration`

**Response shape:**
```json
{
  "leave_type": "EL",
  "calendar_days": 20,
  "company_holidays": [
    { "date": "15 Aug", "name": "Independence Day" },
    { "date": "19 Aug", "name": "Sri Krishna Janmashtami" }
  ],
  "company_holiday_count": 2,
  "week_offs": [
    { "date": "2026-08-09", "day": "Sunday" }
  ],
  "week_off_count": 4,
  "sandwich_leave_enabled": true,
  "actual_leave_days": 20,
  "available_balance": 15.0,
  "earned_leave_used": 15.0,
  "lop_days": 5.0,
  "lop_enabled": true,
  "sufficient_balance": false,
  "warning": "The selected leave exceeds the maximum consecutive leave limit of 15 day(s). Your available EL balance will be used first…"
}
```

New helpers added to `leave.py` (no new files):
- `_get_holidays_with_names(start, end, branch_name)` — returns `[{date, name}]` for named holidays in range
- `_get_weekoffs_in_range(start, end)` — returns `[{date, day}]` for week-off dates in range
- `_leave_preview(request)` — orchestrates full calculation and builds response

---

**5. Max Consecutive Days — No Longer Blocks When LOP Enabled**

`_validate_leave_policy()` previously hard-blocked any request exceeding `maximum_consecutive_days`, even when `convert_to_lop=True`. This was confusing — employees with LOP conversion enabled expected the excess to become LOP, not a rejection.

Fix: when `convert_to_lop=True`, the max consecutive days check is skipped (treated as informational). The preview endpoint's `warning` field already informs the employee of what will happen. When `convert_to_lop=False`, the hard block still applies.

---

**6. LOP Statistics Added to Leave Stats API**

`LeaveStatsView` aggregate extended with two new fields — approved requests only:

```python
lop_total    = Sum('lop_days', filter=Q(status=REQ_APPROVED))
lop_requests = Count('id', filter=Q(status=REQ_APPROVED, lop_days__gt=0))
```

Response now includes:
```json
{ "lop_days": 5.0, "lop_requests": 2 }
```

Pending requests are excluded. Previously `lop_total` summed all statuses (including pending) — now correctly scoped to approved only.

---

**7. Role-Based Department Filter for Leave Approvals**

Added `department` filter to `GET /api/leave/requests/`:

| Filter | Param | System Admin | HR Admin |
|---|---|---|---|
| Branch | `?branch=HQ` | ✅ Filters freely | ❌ Ignored (branch-scoped by `_approval_scope_filter`) |
| Department | `?department=IT` | ✅ Filters freely | ✅ Filters within their branch |
| Status (multi) | `?status=pending,approved` | ✅ | ✅ |

`department` filter uses `employee__department__iexact=department` — only available when caller has `leave.approve`. HR admin's branch restriction is already enforced by `_approval_scope_filter`, so department filter stacks on top correctly.

Example:
```
GET /api/leave/requests/?scope=team&branch=HQ&department=IT&status=pending,approved   # system_admin
GET /api/leave/requests/?scope=team&department=IT&status=pending,l2_pending           # hr_admin
```

---

### Files Modified This Session

```
backend/apps/hrms/views/leave.py
  — _zero_working_days_reason() helper added
  — Spurious week-off validation block removed (LOP Scenario 2 fix)
  — _get_holidays_with_names() helper added
  — _get_weekoffs_in_range() helper added
  — _leave_preview() function added
  — LeaveRequestListCreateView.get(): ?action=preview branch wired
  — _validate_leave_policy(): max_consecutive_days skipped when convert_to_lop=True
  — LeaveStatsView: lop_total filtered to REQ_APPROVED; lop_requests count added
  — LeaveRequestListCreateView.get(): department filter added

frontend/types/attendance.ts
  — DayRecord: color, date, regularization_required added; status widened to string

frontend/app/dashboard/my-attendance/_components/AttendanceCalendar.tsx
  — STATUS_CONFIG replaced by STATUS_LABELS + record.color (backend hex)
  — NON_WORKING set added (Holiday, Weekly Off suppress clock times)

frontend/app/dashboard/my-attendance/_components/CalendarAndHistory.tsx
  — LEGEND Holiday/On Leave colours corrected (were swapped)
```

### Pending

- Frontend: Leave application preview summary panel (call `?action=preview`, display holidays/week-offs breakdown + LOP warning)
- Frontend: Leave stats page — display `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns (filter-options endpoint may be needed for dropdown population)
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Key Architectural Decisions

| Decision | Reason |
|---|---|
| Next.js rewrites proxy for API | Solves cross-origin cookie problem for all devices on same network |
| `APPEND_SLASH = False` in Django | Prevents 308 redirect loop on POST through proxy |
| Dual-source token auth (cookie + header) | Web uses httpOnly cookies; Flutter mobile uses Bearer header |
| Branch filtering client-side for system_admin | Avoids `branches.view` permission dependency; branches derived from employee list |
| `EmployeeCodeSettings` as singleton (pk=1) | One global format, not per-branch — simpler, consistent employee IDs |
| `select_for_update()` for ID generation | Race-safe under concurrent employee creation |
| `branches.view` guards Branches nav (not `settings.view`) | `hr_admin` has `settings.view` for Settings page — wrong permission caused sidebar leak |

---

## Permissions Reference

| Permission | Who has it |
|---|---|
| `branches.view` | system_admin only |
| `settings.view` | system_admin, hr_admin |
| `employees.view` | system_admin, hr_admin |
| `employees.create` | system_admin, hr_admin |

---

## Files Changed This Session

```
backend/
  apps/accounts/
    authentication.py       — dual-source JWT (cookie + Bearer header)
    models.py               — EmployeeCodeSettings model
    migrations/0020_*       — migration for EmployeeCodeSettings
    serializers.py          — EmployeeCodeSettingsSerializer
    views.py                — EmployeeDetailView, EmployeeCodeSettingsView, branch scoping in list, generate_employee_id()
    urls.py                 — /employees/<id>/, /settings/employee-code/
  config/
    settings.py             — APPEND_SLASH = False

frontend/
  app/
    login/page.tsx                              — branch in UserInfo at login
    dashboard/employees/page.tsx               — branch switcher (admin) / fixed label (hr_admin)
    dashboard/employees/[id]/page.tsx          — real API fetch, replaced mock data
    dashboard/employees/_components/
      AddEmployeeModal.tsx                     — fixed paginated response + correct branch endpoint
    dashboard/settings/page.tsx               — Employee ID Format card added
    dashboard/settings/employee-code/page.tsx — new settings page (prefix, padding, next_sequence)
  lib/
    auth.ts                 — branch added to UserInfo
    api/endpoints.ts        — employees.detail, settings.employeeCode
    navConfig.ts            — branches.view guard for Branches nav item
  proxy.ts                  — branches.view guard for /dashboard/branches route
  next.config.ts            — skipTrailingSlashRedirect, trailing slash in rewrite
```

---

## Session Log — 2026-06-30

**Developer:** Rithwika
**Branch:** frontend/Attendance

### Features Shipped

**1. Admin Attendance Page** (`app/dashboard/attendance/page.tsx`)
- 4-tab layout: Attendance, OT Entry, Invalid Punches, Un-punches
- Badge counts on alert tabs (Invalid Punches, Un-punches)
- Stats grid: Present, Absent, Late Arrivals, On Leave

**2. Attendance Tab Components**
- `AttendanceTab.tsx` — date / branch / dept filters, summary chips, full attendance table with status badges, ImportModal trigger
- `ImportModal.tsx` — CSV/XLS import modal with drag-and-drop upload zone
- `OtEntryTab.tsx` — OT entry form (cols-3) + OT records table (Approved / Pending badges)
- `InvalidPunchesTab.tsx` — 3 invalid punch records with error/warn badges and alert banner
- `UnpunchesTab.tsx` — 4 unpunch records with Add Punch fix button

**3. Attendance Rules → moved to Settings**
- `AttendanceSettings.tsx` — refactored to `.card` pattern matching other settings pages; removed Comp-Off Earning Rule and Regularization Policy sections
- Sections kept: Working Hours, Weekly Off Days, Punch Rules, Overtime Rules, Late Mark & LOP Rule, Absence Alert
- `app/dashboard/settings/attendance-config/page.tsx` — new Settings sub-page that hosts AttendanceSettings
- `settings/page.tsx` — Attendance Rules card added with route to `/dashboard/settings/attendance-config`

**4. My Attendance Page** (`app/dashboard/my-attendance/page.tsx`)
- Employee-facing attendance view (no tabs)
- 4 stat cards: Days Present, Late Arrivals, Avg Hours/Day, Attendance %
- Top row (horizontal): ClockWidget + Monthly Summary card (3×2 grid layout)
- Full-width below: Attendance calendar (CalendarGrid + MonthDetail)

**5. Clock Widget** (`my-attendance/_components/ClockWidget.tsx`)
- Live clock with session timer using `useEffect` + `setInterval`
- Clock In / Clock Out toggle updates punch list in real time
- Request Attendance Correction button opens RegularizationModal

**6. RegularizationModal** (`my-attendance/_components/RegularizationModal.tsx`)
- Correction request form: date, punch type, correct in/out times, reason, notes

**7. My Calendar — integrated into My Attendance**
- `CalendarGrid.tsx` — 7-column color-coded calendar grid (DayStatus: Present, Late, Absent, On Leave, Half Day, Weekly Off, Holiday); today highlighted with primary circle
- `MonthDetail.tsx` — detail table for all recorded days (clock in/out, hours, status badge, note)
- `MyCalendarTab.tsx` — wraps CalendarGrid + MonthDetail with month navigation and color legend; used as the right-column of My Attendance
- Separate "My Calendar" nav item removed — calendar lives inside My Attendance

### Layout Decision
My Attendance uses a stacked (vertical) layout instead of side-by-side:
- Row 1: Stats grid (4 KPI cards)
- Row 2: ClockWidget | Monthly Summary (horizontal, 340px + 1fr)
- Row 3: Full-width attendance calendar

This gives the calendar maximum width for readability while keeping the clock always visible.

### Files Changed This Session

```
frontend/
  app/dashboard/
    attendance/
      page.tsx                          — 4-tab admin attendance page
      _components/
        AttendanceTab.tsx               — main attendance tab
        ImportModal.tsx                 — CSV/XLS import modal
        OtEntryTab.tsx                  — OT entry form + records table
        InvalidPunchesTab.tsx           — invalid punch records
        UnpunchesTab.tsx                — unpunch records
        AttendanceSettings.tsx          — refactored to .card pattern; moved to settings
    settings/
      page.tsx                          — Attendance Rules card added
      attendance-config/page.tsx        — new sub-page hosting AttendanceSettings
    my-attendance/
      page.tsx                          — stacked layout (stats → clock+summary → calendar)
      _components/
        ClockWidget.tsx                 — live clock, punch toggle, correction button
        RegularizationModal.tsx         — attendance correction request form
        MyCalendarTab.tsx               — calendar tab (month nav + grid + detail)
    my-calendar/
      _components/
        CalendarGrid.tsx                — 7-col color-coded calendar grid
        MonthDetail.tsx                 — day-by-day attendance detail table
  components/dashboard/
    DashboardShell.tsx                  — added page titles for my-attendance, attendance-config
  lib/
    navConfig.ts                        — added my-attendance; my-calendar nav entry removed
```

---

## Session Log — 2026-07-01

**Developer:** Rithwika
**Branch:** frontend/dynamic

### Features Shipped

**1. My Attendance Page — Full Backend API Integration**
- Rewrote `app/dashboard/my-attendance/page.tsx` using `useAttendanceDashboard` hook
- Layout: ClockWidget + 2×2 stat cards side by side (top row), 6-cell monthly summary grid, tabbed Calendar / History below
- Month navigator: 1-indexed, wraparound (Dec → Jan), Next disabled on current month
- `CorrectionModal` with `key={correctionDate}` — resets form state for each different date

**2. New Hooks**

| Hook | Purpose |
|------|---------|
| `useAttendanceDashboard` | Parallel `useFetch` for `/attendance/stats/`, `/attendance/summary/`, `/attendance/calendar/`; combined `refetch()` |
| `useAttendanceCorrection` | POST `/attendance/correction/`; shows `response.message` toast; calls `onSuccess` callback |

**3. useClockWidget — Full Rewrite**
- Live timer: `session_seconds` + `total_seconds` both tick via `setInterval`; `isClockedIn` boolean as dependency (not session object) to prevent stale closures; functional updater `setSession(prev => ...)` inside interval
- Geolocation: office mode requires GPS — `PERMISSION_DENIED` (code 1) aborts punch with specific toast; codes 2/3 and unsupported browser proceed without coords
- Session state updated directly from POST response body (`res.data.data`) — no extra GET after punch
- Browser field: `parseBrowser()` sends parsed name (Chrome / Edge / Firefox / Safari / Opera / Unknown)
- Added `operating_system` field: `parseOS()` sends parsed OS (Windows 11/10 / macOS / Android / iOS / Linux / Unknown)

**4. New Components**

| Component | Purpose |
|-----------|---------|
| `_components/ClockWidget.tsx` | Rewritten — real data from `useClockWidget`; date + status badge; live session timer; mode selector (office/wfh/field/client_location/remote_office); punch button; punch log with geofence dots (green inside / red outside / grey N/A) |
| `_components/CorrectionModal.tsx` | Controlled by `isOpen` + `date` (read-only) + `onClose` + `onSuccess`; conditional IN/OUT time fields per punch type; uses `useAttendanceCorrection` |
| `_components/AttendanceCalendar.tsx` | Month grid using backend lowercase statuses directly; spec status colors (present=green, late=amber, absent=red, half_day=orange, weekly_off=grey, holiday=blue, on_leave=purple); Regularize button per day |
| `_components/AttendanceHistoryTable.tsx` | Table with Date/Day/ClockIn/ClockOut/Hours/Status/Action columns; status badges; Regularize buttons passing `date` string |
| `_components/CalendarAndHistory.tsx` | Tabbed wrapper (Calendar / History tabs); month nav header with prev/next + month label; legend chips; Next button disabled on current month |

**5. ClockInButton (Dashboard) — Updated**
- Switched to new `useClockWidget` return shape (`session` / `isLoading` / `isPunching`)
- `RegularizationModal` → `CorrectionModal` with today's ISO date string

**6. endpoints.ts — geofencing added**
- `attendance.geofencing: (branchPk: number) => \`/branch/branches/${branchPk}/geofencing/\``

**7. types/attendance.ts — Created**
- Canonical backend types with lowercase statuses (`present`, `late`, `absent`, `half_day`, `weekly_off`, `holiday`, `on_leave`)
- Nullable fields (`clockIn: string | null`, `is_inside_geofence: boolean | null`, etc.)
- Exported types: `TodaySession`, `PunchEntry`, `AttendanceStats`, `MonthlySummary`, `DayRecord`, `CalendarResponse`, `HistoryRow`, `PunchType`, `CorrectionReason`, `AttendanceMode`

### API Endpoints Wired

| Endpoint | Method | Hook |
|----------|--------|------|
| `/attendance/today/` | GET | `useClockWidget` |
| `/attendance/punch/` | POST | `useClockWidget` |
| `/attendance/stats/` | GET | `useAttendanceDashboard` |
| `/attendance/summary/` | GET | `useAttendanceDashboard` |
| `/attendance/calendar/` | GET | `useAttendanceDashboard` |
| `/attendance/correction/` | POST | `useAttendanceCorrection` |

### Punch Request Body (current shape)

```json
{
  "punch_type":       "IN | OUT",
  "attendance_mode":  "office | wfh | field | client_location | remote_office",
  "source":           "web",
  "latitude":         12.3456,
  "longitude":        78.9101,
  "accuracy":         15.0,
  "device_time":      "2026-07-01T09:00:00.000Z",
  "browser":          "Chrome",
  "operating_system": "Windows 11/10"
}
```

GPS fields are plain JS floats from `GeolocationCoordinates` — no type conversion applied.

### Key Technical Decisions

| Decision | Reason |
|----------|---------|
| `isClockedIn` boolean as `useEffect` dependency for timer | Session object changes every second; boolean only changes on actual clock-in/out — prevents re-creating the interval every tick |
| Session updated from POST body directly | Avoids an extra GET round-trip; POST response already returns the updated `TodaySession` |
| `key={correctionDate}` on CorrectionModal | Forces remount (state reset) each time a different date is selected for regularization |
| `parseBrowser()` / `parseOS()` helpers | Backend field `browser` accepts up to 500 chars — sending parsed name keeps it clean; `operating_system` is a new backend field |
| Error toasts from `response.message` only | No hardcoded backend error strings; only the geolocation denial message is frontend-authored |

### Files Changed This Session

```
frontend/
  types/
    attendance.ts                         — new canonical backend types
  lib/api/
    endpoints.ts                          — attendance.geofencing added
  hooks/
    useClockWidget.ts                     — full rewrite (live timer, geo, parsed browser/OS)
    useAttendanceDashboard.ts             — new: parallel useFetch for stats+summary+calendar
    useAttendanceCorrection.ts            — new: POST correction with response.message toasts
  app/dashboard/my-attendance/
    page.tsx                              — full rewrite (ClockWidget+stats, summary grid, tabs)
    _components/
      ClockWidget.tsx                     — full rewrite (real data, live timer, geofence dots)
      CorrectionModal.tsx                 — new: controlled modal (isOpen, date, onClose, onSuccess)
      AttendanceCalendar.tsx              — new: backend-status calendar grid
      AttendanceHistoryTable.tsx          — new: history table with Regularize actions
      CalendarAndHistory.tsx             — new: tabbed wrapper with month nav
  components/
    ClockInButton.tsx                     — updated to new hook shape + CorrectionModal
```

---

## Session Log — 03-07-2026
**Author: G.Durga Prasad**
**Branch: Backend/Assignment-Update**

### Bug Fixes Shipped

**1. Employee portal blocked on all assessment actions**
- `RespondToItemView`, `CompleteAssessmentView`, `RetryAssessmentView` all returned 404 for users without a `Candidate` profile (i.e. existing employees)
- Fix: added `_resolve_assignment(user, assignment_id)` helper that checks candidate first, then falls back to `employee=user`
- All three views now use this helper — employee path works identically to candidate path

**2. Naive datetime crash with `USE_TZ=True`**
- `parse_datetime("2026-08-31T23:59:59")` returns a timezone-naive datetime
- Django raises `ValueError` when saving with `USE_TZ=True`
- Fix: added `tz.make_aware(deadline)` guard — `if tz.is_naive(deadline): deadline = tz.make_aware(deadline)`
- File: `assessments/views/admin.py` `AssignAssessmentView`

**3. `CandidateAssignment.__str__` crash when `candidate=None`**
- Employee assignments have `candidate=None`; the original `__str__` dereferenced `self.candidate.name` unconditionally → `AttributeError`
- Fix: `if/elif` branch — candidate → `candidate.name`; employee → `employee.email`; else → `'Unknown'`

**4. `CandidateResponse.__str__` crash — same root cause**
- Same unconditional deref pattern in `CandidateResponse.__str__`
- Fix: same `if/elif` branch pattern applied

**5. N+1 on assessment list**
- `AssessmentSerializer.get_candidates()` called `obj.assignments.select_related(...)` directly, bypassing the prefetch cache — every assessment triggered a fresh query
- Fix: added `Prefetch('assignments', queryset=assignments_qs)` in `AssessmentListCreateView.get()` and changed `get_candidates()` to use `obj.assignments.all()` to read from the prefetch cache

### Features Shipped

**6. Assessment Settings API** (global defaults — configure once, apply everywhere)
- New `AssessmentSettings` singleton model (db_table=`assessments_settings`, pk=1)
- Fields: `default_pass_percentage` (default 70), `max_attempts` (default 3, 0=unlimited), `time_limit_mins` (nullable, None=no limit)
- `AssessmentSettings.load()` classmethod — `get_or_create(pk=1)` singleton pattern
- `GET /api/assessments/settings/` — retrieve global defaults (requires `assessments.view`)
- `PUT /api/assessments/settings/` — update global defaults (requires `assessments.edit`)
- Per-assessment overrides: `max_attempts` (nullable) and `time_limit_mins` (nullable) added to `Assessment` model
- `Assessment.effective_max_attempts(settings)` and `Assessment.effective_time_limit_mins(settings)` — return per-assessment override if set, else global default
- Files: `assessments/views/settings.py` (new), `AssessmentSettingsSerializer` added to serializers

**7. Portal enforces max attempts and tracks `started_at`**
- `RetryAssessmentView` checks `effective_max_attempts(settings)` and returns 403 if attempts exhausted (0=unlimited bypasses check)
- `RespondToItemView` sets `assignment.started_at = timezone.now()` on the first response; resets to None on retry
- `PortalAssignmentSerializer` now returns `effective_max_attempts`, `attempts_remaining`, `time_limit_mins`, `time_remaining_secs`, `started_at`

**8. Per-section scoring**
- New `AssessmentSection` model (db_table=`assessments_section`) — `title`, `order`, `score` (total marks for the section)
- `section` nullable FK added to `AssessmentItem` → `AssessmentSection` (SET_NULL on delete — items become unsectioned, not deleted)
- `Assessment.compute_max_score()` — sums section scores if sections exist; falls back to raw quiz count for unsectioned assessments (backwards compatible)
- `AssignAssessmentView` now uses `assessment.compute_max_score()` instead of hardcoded quiz count
- `CompleteAssessmentView` calls `_compute_weighted_result(assignment)`: `round((correct_in_section / total_in_section) × section.score)` per section; writes weighted values to `assignment.score` and `assignment.max_score`
- Unsectioned quiz items fall back to 1 mark each (backwards compatible)
- `sections_breakdown` in `ResultsAssignmentSerializer` and `AssessmentCandidateSerializer` (completed only): `{section_id, title, max_score, achieved_score, correct_answers, total_questions, percentage}`

**9. Section CRUD endpoints**
- `GET  /api/assessments/<id>/sections/` — list sections with item counts
- `POST /api/assessments/<id>/sections/` — create a section
- `PUT    /api/assessments/<id>/sections/<section_id>/` — update section title/order/score
- `DELETE /api/assessments/<id>/sections/<section_id>/` — delete section (items unlinked, not deleted)
- Files: `assessments/views/sections.py` (new)

### New Files

```
backend/apps/assessments/
  views/settings.py              — AssessmentSettingsView (GET/PUT)
  views/sections.py              — AssessmentSectionListCreateView, AssessmentSectionDetailView
```

### Files Modified

```
backend/apps/assessments/
  models.py                      — AssessmentSettings; max_attempts + time_limit_mins on Assessment;
                                   compute_max_score(); AssessmentSection; section FK on AssessmentItem;
                                   started_at on CandidateAssignment; fixed __str__ crashes on both models
  serializers.py                 — AssessmentSettingsSerializer; AssessmentSectionSerializer (+Create);
                                   _section_breakdown() helper; PortalAssignmentSerializer (time/attempts);
                                   ResultsAssignmentSerializer + AssessmentCandidateSerializer (sections_breakdown)
  views/admin.py                 — Prefetch fix (N+1); naive datetime fix; settings context to serializers;
                                   compute_max_score() for assign; sections prefetch on CandidateResultsView
  views/portal.py                — _resolve_assignment(); _sync_user_assessment_status();
                                   _compute_weighted_result(); started_at tracking; max_attempts on retry
  urls.py                        — settings/, <id>/sections/, <id>/sections/<sid>/ routes added
```

### API Changes

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/assessments/settings/` | Retrieve global assessment defaults |
| PUT | `/api/assessments/settings/` | Update global defaults (pass%, max_attempts, time_limit) |
| GET | `/api/assessments/<id>/sections/` | List sections for an assessment |
| POST | `/api/assessments/<id>/sections/` | Create a section |
| PUT | `/api/assessments/<id>/sections/<sid>/` | Update section |
| DELETE | `/api/assessments/<id>/sections/<sid>/` | Delete section (items unlinked, not deleted) |

### Migrations Applied

```
assessments/0008_assessmentsettings_assessment_max_attempts_and_more  ✅ applied
assessments/0009_assessmentsection_assessmentitem_section             ✅ applied
```

**10. `AssignAssessmentView` — employee ID sent as `candidate_id` crashes with 500**
- Root cause: frontend was sending `candidate_id: "RSS00025"` (an employee code string) because the assign modal used the same field for both candidates and employees
- Backend did `Candidate.objects.get(pk="RSS00025")` — Django tried to cast `"RSS00025"` to an integer/UUID, raised `ValueError`, returned 500
- Fix: added UUID format check before routing — if `candidate_id` is not a valid UUID, it is automatically treated as an `employee_id` and routed to the employee lookup path (`User.objects.get(employee_id=...)`)
- No migration required — view-only change
- File: `assessments/views/admin.py` `AssignAssessmentView.post()`

---

## Session Log — 07-07-2026
**Author: G.Durga Prasad**
**Branch: Backend/Assignment-Update**

### Features Shipped

**1. Referral endpoints — 5 new API routes**

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/recruitment/referrals/` | List referrals submitted by the logged-in employee (paginated) |
| POST | `/api/recruitment/referrals/` | Employee submits a new referral |
| GET | `/api/recruitment/referrals/all/` | Admin views all referrals across all employees (paginated) |
| GET | `/api/recruitment/referral-rules/` | List active referral rules (public, for portal) |
| POST | `/api/recruitment/referral-rules/` | Admin creates a new referral rule |
| PATCH | `/api/recruitment/referral-rules/<id>/` | Admin updates a referral rule |
| DELETE | `/api/recruitment/referral-rules/<id>/` | Admin deletes a referral rule |

**2. `ReferralRule` model added**
- New model in `recruitment/models.py` — `icon`, `title`, `body`, `order`, `is_active`
- Uses `AutoField` (int PK) — intentional exception to UUID rule; these are static reference rows
- `db_table = 'referral_rule'`, `ordering = ['order']`
- Migration `0004_referralrule` created ✅

**3. Referral rule seed data**
- Migration `0005_referralrule_seed` seeds 6 default rules (Eligibility, Referral Bonus, No Self-Referral, Cooling Period, Active Referral Limit, Tax & Payroll) using `get_or_create` ✅

**4. Referral email templates seeded**
- Migration `0006_referral_email_templates` seeds 4 templates using `get_or_create`:
  - `referral_submitted_referrer` — sent to referrer when their referral is received
  - `referral_submitted_candidate` — sent to referred candidate confirming referral
  - `referral_interview_scheduled_candidate` — sent to referred candidate when interview is scheduled
  - `referral_interview_scheduled_referrer` — sent to referrer when their referral is shortlisted

**5. Interview scheduled email template for direct candidates**
- Migration `0007_interview_scheduled_email_template` seeds `interview_scheduled_candidate` template — sent to any non-referred candidate when HR schedules their interview ✅

**6. Email triggers — referral submission**
- `_send_referral_submission_emails(candidate)` fires in background thread when a referred candidate is created via `POST /api/recruitment/candidates/`
- Sends 2 emails: one to referrer (`referral_submitted_referrer`), one to candidate (`referral_submitted_candidate`)

**7. Email triggers — interview scheduled**
- `_fire_interview_date_emails_if_needed(candidate, old_interview_date)` fires after any create or update that sets or changes `interview_date`
- Referred candidates → `_send_interview_scheduled_emails()` — 2 emails (candidate + referrer)
- Non-referred candidates → `_send_interview_scheduled_email_general()` — 1 email (candidate only)
- Triggered on: PUT, PATCH of existing candidate, and also on POST (candidate created with interview_date already set)
- Reschedule detection: any change where new `interview_date` is non-null AND different from old value triggers emails (not just null → value transitions)

### Bug Fixes Shipped

**8. Email templates sending variable placeholders instead of values**
- Root cause: migrations 0006 and 0007 used `get_or_create` — if the templates already existed in DB (from a previous dev session or manual creation), the correct bodies in `defaults` were silently skipped
- Fix: migration `0008_fix_email_template_bodies` uses `update_or_create` to force-overwrite subject, body, and `available_variables` for all 5 recruitment email templates regardless of prior DB state ✅

### Files Modified

```
backend/apps/recruitment/
  models.py           — ReferralRule model added
  serializers.py      — ReferralRuleSerializer added
  views.py            — _send_referral_email(), _send_referral_submission_emails(),
                        _send_interview_scheduled_emails(),
                        _send_interview_scheduled_email_general(),
                        _fire_interview_date_emails_if_needed() helpers added;
                        ReferralListCreateView, ReferralAllView,
                        ReferralRuleListCreateView, ReferralRuleDetailView added;
                        interview email triggers wired into POST, PUT, PATCH
  urls.py             — 4 new referral URL patterns added

backend/apps/recruitment/migrations/
  0004_referralrule.py                    — creates referral_rule table ✅
  0005_referralrule_seed.py               — seeds 6 default referral rules ✅
  0006_referral_email_templates.py        — seeds 4 referral email templates ✅
  0007_interview_scheduled_email_template.py — seeds interview_scheduled_candidate template ✅
  0008_fix_email_template_bodies.py       — force-updates all 5 template bodies via update_or_create ✅
```

### Context Keys Sent by Each Email Helper

| Template | Context Keys Sent |
|---|---|
| `referral_submitted_referrer` | `referrer_name`, `candidate_name`, `position_applied`, `branch_name`, `company_name` |
| `referral_submitted_candidate` | `candidate_name`, `referrer_name`, `position_applied`, `company_name` |
| `referral_interview_scheduled_candidate` | `candidate_name`, `position_applied`, `interview_date`, `interview_mode_display`, `branch_name`, `company_name` |
| `referral_interview_scheduled_referrer` | `referrer_name`, `candidate_name`, `position_applied`, `interview_date`, `company_name` |
| `interview_scheduled_candidate` | `candidate_name`, `position_applied`, `interview_date`, `interview_mode_display`, `branch_name`, `company_name` |

---

## Session Log — 07-07-2026
**Author: G.Durga Prasad**
**Branch: Backend/referral**

### Features Shipped

**1. Referral bonus URL wiring — 4 missing routes added**
- `GET  /api/recruitment/referral-bonuses/` — list all referral bonus records (paginated, HR view)
- `GET  /api/recruitment/referral-bonuses/<pk>/` — single bonus record detail
- `POST /api/recruitment/referral-bonuses/<pk>/approve/` — HR approves a pending bonus
- `POST /api/recruitment/referral-bonuses/<pk>/pay/` — HR marks a bonus as paid
- Views (`ReferralBonusListView`, `ReferralBonusDetailView`, `ReferralBonusApproveView`, `ReferralBonusPayView`) already existed in `views.py`; they were just not wired in `urls.py`
- File: `backend/apps/recruitment/urls.py`

**2. Referral bonus migration — `ReferralBonus` model**
- Migration `0009_referralbonus` creates the `referral_bonus` table (OneToOne → Candidate, FK → referrer User, bonus_amount, status, approved_by, paid_by, timestamps)

### Bug Fixes Shipped

**3. `birthday_wish_sent_year` AttributeError — 500 on `/api/hrms/birthdays/`**
- Root cause: migration `0038_employeeprofile_birthday_wish_sent_year` had been applied (DB column existed), but the field was never added to the `EmployeeProfile` model class in `models.py`
- Python raised `AttributeError: 'EmployeeProfile' object has no attribute 'birthday_wish_sent_year'` on every birthdays request
- Fix: added `birthday_wish_sent_year = models.PositiveSmallIntegerField(null=True, blank=True)` to `EmployeeProfile` in `accounts/models.py` — no new migration needed (column already exists)
- File: `backend/apps/accounts/models.py`

### Backend Audit — Full Codebase Review

Comprehensive audit of all 7 Django apps completed. **115+ findings** identified across models, serializers, and views. Key categories:

| Severity | Count | Examples |
|---|---|---|
| Critical | 6 | `error(…, status=X)` TypeError in attendance views → 500; `return first_error()` returns string not Response → 500; `paginate()` called with wrong arg order → 500 |
| High | 28 | Missing `@transaction.atomic` on branch HR cascade / delete / geofence; leave approval not atomic; expense_number race condition; assessments PUT without `partial=True` |
| Medium | 52 | Wrong HTTP status codes (400 vs 409, 400 vs 404); permission checks using view perms for write ops; MIME type trusted from Content-Type header; unguarded service calls → 500 |
| Low | 35 | Missing `updated_at` on several models; integer PKs instead of UUIDs; `getLogger('branch')` instead of `__name__`; non-RESTful POST-aliases-PUT patterns |

**Files with critical/high findings:**

| File | Key Findings |
|---|---|
| `attendance/views/absence_alert.py` | `error(…, status=)` TypeError → 500; wrong `paginate()` arg order; `first_error()` returns string not Response; wrong permission system (`has_perm()` vs role-based) |
| `attendance/views/late_mark_lop.py` | Same 4 critical bugs as above |
| `attendance/views/settings_view.py` | PUT/PATCH use `settings.view` instead of `settings.edit` — view-only users can write |
| `attendance/views/hr_attendance.py` | Bare `except Exception: return False` swallows all DB errors; raw `list(page_obj)` without serializer |
| `assessments/views/admin.py` | PUT without `partial=True` resets boolean fields to defaults; unhandled ValueError for invalid UUID |
| `branch/views.py` | `_cascade_hr` + `branch.delete()` + geofencing save all missing `@transaction.atomic` |
| `branch/views_access.py` | Raw integer HTTP status codes (403, 409, 404) — `rest_framework.status` not imported |
| `announcements/views.py` | HTTP 204 response with JSON body (RFC violation); case-sensitive visibility queries |
| `hrms/views/expenses.py` | `select_for_update().aggregate()` doesn't lock rows → expense_number race → IntegrityError 500 |
| `hrms/views/leave.py` | Leave approval + balance deduction not in `transaction.atomic()`; L2 approver bypass |
| `recruitment/views.py` | HR reject makes no DB change; ₹0 bonus can be approved/paid; no status transition rules |
| `accounts/views.py` | JWT tokens returned in response body (Critical security violation); uncaught DoesNotExist → 500s |

**Fixes are pending — to be applied in the next session.**

### Files Changed

```
backend/apps/accounts/models.py      — birthday_wish_sent_year field added to EmployeeProfile
backend/apps/recruitment/urls.py     — 4 referral bonus URL patterns added
```

---

## Session Log — 2026-07-13
**Author: Teerdaveni**

### Features Shipped

**1. Redis Caching Layer — Master/Configuration Data**

Implemented read-through Redis caching for all frequently-accessed master/configuration data. Cache never stores transactional data (leave requests, attendance records, balances, payroll). All operations wrapped in try/except — if Redis is unavailable, falls back to DB transparently.

**Cache services created in `core/cache_service.py`:**

| Service | Cache Key | TTL | Invalidated By |
|---|---|---|---|
| `LeavePolicyCacheService` | `leave_policy:{leave_type}` | 6h | `LeavePolicy` save/delete |
| `HolidayCacheService` | `holiday:{branch_slug}:{year}` | 24h | `Holiday` save/delete |
| `WeeklyOffCacheService` | `weekly_off` | 24h | `WeeklyDayPolicy`, `AttendanceWeeklyOff` save/delete |
| `ApprovalWorkflowCacheService` | `approval_workflow:{workflow_type}` | 6h | `ApprovalWorkflowRule` save/delete |
| `AttendanceSettingsCacheService` | `attendance_settings` | 6h | `AttendanceSettings` + all 4 child models save/delete |
| `BranchCacheService` | `branches:all` | 12h | `Branch` save/delete |
| `DepartmentCacheService` | `departments:all` | 12h | `Department` save/delete |
| `DesignationCacheService` | `designations:all` | 12h | `Designation` save/delete |

**Holiday cache design:**
- Caches full year of holidays per branch in a single key (no per-request range queries)
- `get_holiday_dates(start, end, branch_name)` filters by range in Python — O(n) over ~20 holidays vs DB round-trip
- Company-wide holiday change (branch=None) → `invalidate_year(year)` → deletes company key + all branch keys for that year
- Branch-specific holiday change → invalidates that branch's key only
- Date ranges spanning 2 years (rare) fall back to direct DB query

**Signals wired for immediate invalidation on every CUD operation:**
- `apps/hrms/signals.py` — `Holiday`, `LeavePolicy`
- `apps/attendance/signals.py` — `WeeklyDayPolicy`, `AttendanceWeeklyOff`, `AttendanceSettings`, `AttendanceWorkingHours`, `AttendancePunchRules`, `AttendanceOvertimeRules`
- `apps/branch/signals.py` — `Branch`
- `apps/accounts/signals.py` — `Department`, `Designation`, `ApprovalWorkflowRule`
- All signals registered via `AppConfig.ready()` using string sender labels (e.g. `'hrms.Holiday'`) — no circular import risk

**Call sites updated — leave.py helpers now delegate to cache:**
- `_get_holiday_dates()` → `HolidayCacheService.get_holiday_dates()`
- `_get_holidays_with_names()` → `HolidayCacheService.get_holidays_with_names()`
- `_get_weekly_off_days()` → `WeeklyOffCacheService.get()`
- `_resolve_approval_chain()` → `ApprovalWorkflowCacheService.get_rule('leave')`
- `_leave_preview()` LeavePolicy lookup → `LeavePolicyCacheService.get(leave_type)`
- `LeaveRequestListCreateView.post()` LeavePolicy lookup → `LeavePolicyCacheService.get(leave_type)`

**Call sites updated — services_attendance.py delegates to cache:**
- `_get_settings()` → `AttendanceSettingsCacheService.get()`
- `AttendanceDashboardService._weekly_off_days()` → `WeeklyOffCacheService.get()`
- `AttendanceDashboardService._holiday_dates()` → `HolidayCacheService.get_holiday_dates()`

**What is NOT cached (by design):**
- `LeaveBalance`, `LeaveRequest`, `AttendanceRecord`, `AttendancePunch`, `AttendanceCorrection`
- Payroll transactions, notifications, approval status, employee clock-in state
- `EmployeeApprovalOverride` — per-employee override, not global config

### New Files

```
backend/core/
  cache_service.py            — 8 cache service classes + CacheTTL constants

backend/apps/hrms/
  signals.py                  — Holiday + LeavePolicy cache invalidation

backend/apps/attendance/
  signals.py                  — WeeklyDayPolicy, AttendanceWeeklyOff, AttendanceSettings,
                                AttendanceWorkingHours, AttendancePunchRules,
                                AttendanceOvertimeRules cache invalidation

backend/apps/branch/
  signals.py                  — Branch cache invalidation

backend/apps/accounts/
  signals.py                  — Department, Designation, ApprovalWorkflowRule cache invalidation
```

### Files Modified

```
backend/apps/hrms/apps.py         — ready() added → imports hrms.signals
backend/apps/attendance/apps.py   — ready() added → imports attendance.signals
backend/apps/branch/apps.py       — ready() added → imports branch.signals
backend/apps/accounts/apps.py     — ready() added → imports accounts.signals

backend/apps/hrms/views/leave.py  — 4 helper functions + 2 LeavePolicy lookups delegate to cache
backend/apps/attendance/
  services_attendance.py          — _get_settings(), _weekly_off_days(), _holiday_dates() delegate to cache
```

### Infrastructure Note

Redis is already configured: `django-redis==5.4.0`, `redis==8.0.1`, CACHES block in `settings.py` points to `REDIS_URL` env var. Falls back to `LocMemCache` (in-process, no sharing between workers) if `REDIS_URL` is not set — caching still works in development without Redis running.

### Pending

- Frontend: Leave application preview summary panel
- Frontend: Leave stats page — `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns
- Frontend: Employee Profile page — `?employee_id=` wiring to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-16
**Author: Teerdaveni**

### Bug Fixes Shipped

**1. HR & Manager List APIs returning empty data**

**Endpoints affected:**
- `GET /api/employees/hrs/?branch=<branch_name>`
- `GET /api/employees/managers/?branch=<branch_name>`

**Root causes:**
- `HRListView` was filtering `role__name='hr_admin'` — actual DB value is `'hr'`
- `ManagerListView` was filtering `role__name='manager'` — actual DB value is `'manager__team_lead'`
- Branch filter was AND-only; HR users may be linked to a branch via the `Branch.hr` FK (`managed_branches` reverse relation), not just their own `user.branch` field

**Fixes applied — `backend/apps/accounts/views.py`:**
- `HRListView`: role filter → `'hr'`; branch filter → `Q(branch__iexact=branch) | Q(managed_branches__branch_name__iexact=branch)` with `.distinct()`
- `ManagerListView`: role filter → `'manager__team_lead'`; branch filter → `Q(branch__iexact=branch) | Q(direct_reports__branch__iexact=branch)` with `.distinct()`

**Note:** Branch name is stored as full string (e.g. `"Vijayawada Branch"`) — query must pass full name, not partial.

---

### Features Shipped

**2. System Admin Dashboard APIs (8 endpoints)**

New Django app `apps/dashboard` created. All endpoints under `GET /api/dashboard/system-admin/`.
Permission guard: `role.name == 'system_admin'` — all others get 403.

| Endpoint | Description |
|---|---|
| `system-admin/kpis/` | Total employees, pending approvals, onboarding count, active branches, system health flags (DB/mail/storage) |
| `system-admin/announcement/` | Latest announcement from DB |
| `system-admin/pending-approvals/` | Leave, expense, onboarding, separation counts |
| `system-admin/department-headcount/` | Per-department active employee count (cached 12 h) |
| `system-admin/employee-lifecycle/` | New joiners (last 30 days) + work anniversaries this month |
| `system-admin/birthdays/today/` | Employees whose birthday is today (cached 6 h) |
| `system-admin/birthdays/upcoming/` | Birthdays in the next 30 days (cached 6 h) |
| `system-admin/audit-logs/` | Paginated audit log with optional `?module=` filter |

---

**3. HR Dashboard APIs (9 endpoints)**

All added to the existing dashboard module. Endpoints under `GET /api/dashboard/hr/`.
Permission guard: `role.name in ('hr', 'system_admin')` — others get 403.

| Endpoint | Description |
|---|---|
| `hr/kpis/` | Total workforce, pending actions, active interviews, correction count, requester's today attendance |
| `hr/action-queue/` | Counts per queue: candidate reviews, leave approvals, corrections, expenses, onboarding |
| `hr/recruitment-funnel/` | Interview → selected → onboarded funnel counts (cached 10 min) |
| `hr/department-headcount/` | Shared headcount helper (same cached data as system-admin) |
| `hr/employee-lifecycle/` | New joiners + work anniversaries with designation (cached 1 h) |
| `hr/birthdays/today/` | Shared birthday helper (same cache as system-admin) |
| `hr/birthdays/upcoming/` | Shared birthday helper |
| `hr/attendance-summary/` | Company-wide today attendance counts by status |
| `department-headcount/` | Shared alias at root level accessible to both HR and System Admin |

---

**4. Employee Dashboard APIs (7 endpoints)**

All endpoints under `GET /api/dashboard/employee/` plus one shared endpoint.
Permission: `IsAuthenticated` — no role restriction. All data is always scoped to `request.user`; cross-employee access is impossible by design.

| Endpoint | Description |
|---|---|
| `employee/kpis/` | days_present, working_days, absent_days, pending_action_items, pending_expense_claims, pending_documents, clocked_in, today_attendance |
| `employee/leave-balances/` | All leave type balances for the year + LOP days consumed (cached 10 min) |
| `employee/action-items/` | Profile completeness, missing docs, pending corrections, recent leave decisions (cached 5 min) |
| `employee/recent-requests/` | Last 10 requests across leave, expense, and attendance correction — sorted by date |
| `employee/attendance-summary/` | Month-level stats via `AttendanceDashboardService`; supports `?month=&year=` params |
| `employee/attendance-status/` | Today: clocked-in state, clock-in/out times (HH:MM), working hours as HH:MM |
| `announcement/` | Shared latest announcement — accessible to all authenticated roles |

**Caching:**
- Monthly attendance summary → `dashboard:employee:kpis:{id}` — 5 min TTL
- Leave balances → `dashboard:employee:leave_balance:{id}` — 10 min TTL
- Action items → `dashboard:employee:action_items:{id}` — 5 min TTL
- Attendance status, recent requests — always fresh (no cache)

**Key reused services:**
- `AttendanceDashboardService.get_stats(employee, year, month)` — returns `days_present`, `late_arrivals`, `lop_pending`, `avg_hours_per_day`, `attendance_percentage`, `working_days`
- `AttendanceDashboardService.get_monthly_summary(employee, year, month)` — returns `working_days`, `days_present`, `days_absent`, `leave_days`, `half_days`, `ot_hours`
- `AttendanceRecord.first_punch_in`, `last_punch_out`, `total_working_minutes` — used for attendance status

---

### Files Created / Modified

| File | Change |
|---|---|
| `backend/apps/accounts/views.py` | Fixed `HRListView` and `ManagerListView` — role names + branch OR filter |
| `backend/apps/dashboard/__init__.py` | Created (empty) |
| `backend/apps/dashboard/apps.py` | Created — `DashboardConfig` |
| `backend/apps/dashboard/urls.py` | Created — 25 URL patterns (System Admin + HR + Employee) |
| `backend/apps/dashboard/views/__init__.py` | Created — exports all 23 view classes |
| `backend/apps/dashboard/views/overview.py` | Created — System Admin KPIs, announcement, pending approvals, headcount, HR KPIs, action queue, recruitment funnel, HR attendance summary, shared announcement, all 5 employee overview views |
| `backend/apps/dashboard/views/people.py` | Created — lifecycle, birthday, audit log (System Admin + HR), employee action items, employee recent requests |
| `backend/config/settings.py` | Added `'apps.dashboard'` to `INSTALLED_APPS` |
| `backend/config/urls.py` | Added `path('api/dashboard/', include('apps.dashboard.urls'))` |

### All 25 Active Dashboard Routes

```
GET /api/dashboard/system-admin/kpis/
GET /api/dashboard/system-admin/announcement/
GET /api/dashboard/system-admin/pending-approvals/
GET /api/dashboard/system-admin/department-headcount/
GET /api/dashboard/system-admin/employee-lifecycle/
GET /api/dashboard/system-admin/birthdays/today/
GET /api/dashboard/system-admin/birthdays/upcoming/
GET /api/dashboard/system-admin/audit-logs/
GET /api/dashboard/department-headcount/
GET /api/dashboard/announcement/
GET /api/dashboard/hr/kpis/
GET /api/dashboard/hr/action-queue/
GET /api/dashboard/hr/recruitment-funnel/
GET /api/dashboard/hr/department-headcount/
GET /api/dashboard/hr/employee-lifecycle/
GET /api/dashboard/hr/birthdays/today/
GET /api/dashboard/hr/birthdays/upcoming/
GET /api/dashboard/hr/attendance-summary/
GET /api/dashboard/employee/kpis/
GET /api/dashboard/employee/leave-balances/
GET /api/dashboard/employee/action-items/
GET /api/dashboard/employee/recent-requests/
GET /api/dashboard/employee/attendance-summary/
GET /api/dashboard/employee/attendance-status/
```

### Frontend Prompts Given

Full API request/response documentation provided for:
- System Admin Dashboard (8 endpoints) — types, hooks, layout, role-based visibility
- HR Dashboard (9 endpoints) — types, hooks, layout
- Employee Dashboard (7 endpoints) — types, hooks, layout, status badge colors

### Pending

- Frontend implementation of all 3 dashboard pages (prompts given above)
- Frontend: Leave application preview summary panel
- Frontend: Leave stats page — `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns
- Frontend: Employee Profile page — `?employee_id=` wiring to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-20
**Author: Teerdaveni**

### Bug Fixes Shipped

**1. `GET /api/employees/<employee_id>/` — `hr` and `reporting_manager` always returning null**

**Root causes identified and fixed:**

| # | Location | Bug | Fix |
|---|---|---|---|
| 1 | `_auto_assign_managers` | HR assignment block removed with incorrect comment "Branch has no hr FK field" — `Branch.hr` FK exists in `branch/models.py` | Restored: tries `Branch.hr` first; falls back to first active `role='hr'` user in same branch |
| 2 | `_auto_assign_managers` | `role__name='manager'` — no DB role with that name exists; actual value is `'manager__team_lead'` — query always returned 0, `count() != 1` guard always bailed | Fixed: `'manager'` → `'manager__team_lead'` |
| 3 | `_auto_assign_managers` | Manager guard used `role_name == 'manager'` — same wrong name; managers were not skipping the assignment loop | Fixed: `'manager'` → `'manager__team_lead'` |
| 4 | `EmployeeDetailView.get` | Wrong inline auto-assign: only fired for `hr_admin` viewers AND assigned the viewing user as the employee's HR (wrong person) | Replaced with `_auto_assign_managers(employee)` — runs for all viewers, assigns correct branch HR |
| 5 | `_get_employee` | `select_related` missing `'hr'` — extra DB query per GET when `_employee_dict` read `user.hr` | Added `'hr'` to `select_related` |
| 6 | `_employee_dict` | `hr.id` and `mgr.id` returned UUID (`str(uuid)`) — expected response uses `employee_id` (e.g. `RSS00001`) | Changed `str(_hr.id)` → `_hr.employee_id`; `str(mgr.id)` → `mgr.employee_id` |
| 7 | `_employee_dict` | `if role_name != 'manager'` — wrong role name; managers incorrectly got a `reporting_manager` field | Fixed: `'manager'` → `'manager__team_lead'` |

**How assignment now works on GET:**
1. `_get_employee()` fetches employee with `select_related('role', 'profile', 'reporting_manager', 'hr')`
2. `_auto_assign_managers(employee)` runs (in-memory):
   - HR: if `employee.hr_id is None`, looks up `Branch.hr` for the employee's branch; if not set, falls back to first active `role='hr'` user in same branch
   - Reporting manager: if `employee.reporting_manager_id is None` AND exactly 1 `manager__team_lead` is in the branch, checks department manager; assigns if in same branch
3. If any fields changed, `employee.save(update_fields=changed + ['updated_at'])` persists the assignment
4. `_employee_dict(employee)` builds response using the now-resolved FK objects

**Expected response (after fix):**
```json
{
  "hr": { "id": "RSS00001", "name": "Human Resources" },
  "reporting_manager": { "id": "RSS00002", "name": "Vignesh Kumar Saka" }
}
```

**Note on reporting_manager:** If a branch has multiple `manager__team_lead` users (e.g. Hyderabad has 2), auto-assign correctly skips (ambiguous) — HR must assign manually in that case. This is intentional behaviour.

### Files Modified

```
backend/apps/accounts/views.py
  — _auto_assign_managers(): HR block restored; role names corrected ('manager' → 'manager__team_lead')
  — _get_employee(): 'hr' added to select_related
  — EmployeeDetailView.get(): wrong inline auto-assign replaced with _auto_assign_managers() call
  — _employee_dict(): hr.id and mgr.id changed from UUID to employee_id; role guard fixed
```

---

## Session Log — 2026-07-20 (continued)
**Author: Teerdaveni**

### Features Shipped

**3. Bulk Candidate Import** (`POST /api/recruitment/candidates/bulk-import/`)

New endpoint added to the existing Interview List / Recruitment module. No new Python files, no new models.

**Accepted formats:** `.csv` and `.xlsx` (via `openpyxl`). Maximum 1 000 rows / 5 MB per upload.

**Column headers accepted (case-insensitive, with aliases):**

| Canonical field | Accepted header aliases |
|---|---|
| `name` | Full Name, Candidate Name, Name |
| `email` | Email, Email Address |
| `phone` | Phone, Mobile, Phone Number, Mobile Number |
| `position_applied` | Position, Position Applied, Job Title, Role |
| `branch_name` | Branch, Branch Name |
| `interview_date` | Interview Date, Date |
| `interview_mode` | Interview Mode, Mode |
| `notes` | Notes, Remarks, Comments |

**Validation per row:**
- `name`, `email`, `position_applied` are required
- Email: valid format; duplicate check against DB and within the file
- Phone: valid format; duplicate check if provided
- `interview_date`: today or future only; accepts `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`
- `interview_mode`: `in_person` / `video_call` / `phone`; also accepts aliases `In Person`, `Online`, `Video Call`
- `branch_name`: resolved to existing `Branch` by name or code; missing branch returns row error (never creates new branches)

**Import behaviour:**
- Continues processing all rows after an error — does NOT stop at first failure
- All valid rows inserted with `bulk_create()` inside `transaction.atomic()`
- HTTP 200 if all rows succeed; HTTP 207 if any rows failed

**Permission:** role must be `system_admin`, `hr`, or `hr_admin`; superusers always allowed; others get 403.

**Response shape:**
```json
{
  "status": "success",
  "message": "Bulk import completed.",
  "data": {
    "total_rows": 50,
    "success": 46,
    "failed": 4,
    "errors": [
      { "row": 8,  "field": "email",  "message": "Duplicate email." },
      { "row": 15, "field": "branch", "message": "Branch \"HQ\" not found. Use an existing branch name or code." }
    ]
  }
}
```

### Files Modified

```
backend/requirements.txt                         — openpyxl==3.1.5 added
backend/apps/recruitment/serializers.py          — CandidateBulkImportRowSerializer added
                                                   (+ _BULK_MODE_ALIASES, _VALID_IMPORT_MODES constants)
backend/apps/recruitment/views.py                — import csv, io, MultiPartParser added;
                                                   CandidateBulkImportRowSerializer imported;
                                                   _IMPORT_COL_MAP, _normalize_import_headers(),
                                                   _parse_csv_rows(), _parse_xlsx_rows(),
                                                   CandidateBulkImportView added
backend/apps/recruitment/urls.py                 — candidates/bulk-import/ URL pattern added
```

### Pending

- Frontend implementation of all 3 dashboard pages (prompts given above)
- Frontend: Leave application preview summary panel
- Frontend: Leave stats page — `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns
- Frontend: Employee Profile page — `?employee_id=` wiring to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-17
**Author: G.Durga Prasad**
**Branch: Testing---Fixes**

### Bug Fixes Shipped

**1. Assessments sidebar nav — clicking redirected to dashboard instead of opening page**
- Root cause: `proxy.ts` had `"/dashboard/assessments": "recruitment.view"` — employees only hold `assessments.view`, so the route guard redirected them to `/dashboard` before the page could load
- Fix: changed to `"/dashboard/assessments": "assessments.view"` to match `navConfig.ts` and the backend permission check
- File: `frontend/proxy.ts`

**2. Permissions page — save errors showed generic HTTP message instead of API validation message**
- Root cause: Axios wraps HTTP error responses inside `err.response.data`; reading `err.message` directly gives the generic `"Request failed with status code 400"` string, hiding the actual API error
- Fix: added `apiErr()` helper that reads `err.response?.data?.message` first, falls back to `err.message`
- Applied to both `editRole` and `addRole` catch blocks
- File: `frontend/app/dashboard/settings/permissions/page.tsx`

**3. Permissions page — no feedback after saving role permissions**
- Added `saveMsg` state and a dismissable success banner shown after a successful role edit
- Banner message: "Permissions saved. Users in this role must log out and back in for changes to take effect." (informs admin of the JWT token caching behaviour)
- File: `frontend/app/dashboard/settings/permissions/page.tsx`

### Features Shipped

**4. Attendance nav item hidden for employee role**
- `NavItem` interface extended with optional `excludeRoles?: string[]` field
- Attendance entry marked `excludeRoles: ["employee"]` — employees never see the Attendance sidebar item (they use My Attendance instead)
- `buildNav(permissions, role?)` updated to filter by `excludeRoles` in addition to the existing permission check
- File: `frontend/lib/navConfig.ts`

**5. Employee assessments page**
- New component `EmployeeMyAssessments` — fetches `GET /api/assessments/my/` and renders 3 stat cards (Total / Pending / Completed), a pending section with progress bars and deadline info, and a completed section with score percentage and pass/fail badges
- `/dashboard/assessments` page now branches by role: users with any `recruitment.*` permission see the existing admin management UI; all other users (employees) see `EmployeeMyAssessments`
- `useFetch` calls for admin-only endpoints are conditionally skipped (`null`) for employee users to avoid unnecessary requests
- File: `frontend/app/dashboard/assessments/_components/EmployeeMyAssessments.tsx` (new)
- File: `frontend/app/dashboard/assessments/page.tsx`

### Files Changed

```
frontend/
  proxy.ts
    — ROUTE_PERMISSIONS: /dashboard/assessments changed from "recruitment.view" to "assessments.view"

  lib/navConfig.ts
    — NavItem interface: excludeRoles?: string[] added
    — Attendance entry: excludeRoles: ["employee"] added
    — buildNav(permissions, role?): role-based filtering on excludeRoles added

  components/dashboard/DashboardShell.tsx
    — buildNav() call now passes session.role as second argument

  app/dashboard/assessments/
    page.tsx
      — isAdminView check using useAnyPermission("recruitment.view", "recruitment.create", "recruitment.edit")
      — Early return: non-admin users render <EmployeeMyAssessments /> instead of admin UI
      — useFetch calls for list + settings endpoints skip (null) for non-admin users
    _components/EmployeeMyAssessments.tsx  (NEW FILE)
      — Fetches API.assessments.my via useFetch
      — Stat cards: Total, Pending, Completed
      — Pending section: progress bar, deadline, attempt count, in_progress vs pending badge
      — Completed section: score percentage, pass/fail pill badge

  app/dashboard/settings/permissions/page.tsx
    — saveMsg state added
    — apiErr() helper added (reads err.response?.data?.message)
    — editRole catch: uses apiErr() instead of err.message
    — addRole catch: uses apiErr() instead of err.message
    — Success banner rendered when saveMsg is set (dismissable)
```

---

## Session Log — 2026-07-20 (Part 2)
**Author: Teerdaveni**

### Fixes Shipped

**1. Candidate Bulk Import — branch is now a mandatory field**

`branch_name` in `CandidateBulkImportRowSerializer` was `required=False, allow_blank=True`. Changed to `required=True` so any row missing a branch value is immediately rejected with a validation error.

```
backend/apps/recruitment/serializers.py
  — CandidateBulkImportRowSerializer.branch_name: required=False → required=True
```

---

### Features Shipped

**2. Employee Bulk Import** (`POST /api/employees/bulk-import/`)

Verified the endpoint did not exist. Implemented from scratch inside existing files — no new Python files, no new models.

**Accepted formats:** `.csv` and `.xlsx`. Maximum 1 000 rows / 5 MB per upload.

**Permission:** `system_admin` and `hr_admin` only — others get 403.

**Column headers accepted (case-insensitive, with aliases):**

| Canonical field | Accepted header aliases |
|---|---|
| `first_name` | First Name, Firstname |
| `last_name` | Last Name, Lastname |
| `email` | Work Email, Email, Email Address |
| `phone` | Phone, Mobile, Phone Number |
| `role` | Role |
| `department` | Department, Dept |
| `designation` | Designation |
| `branch` | Branch, Branch Name |
| `employee_type` | Employee Type, Emp Type, Type |
| `date_of_joining` | Date of Joining, Joining Date, DOJ |
| `gender` | Gender, Sex |
| `date_of_birth` | DOB, Date of Birth, Birthdate |
| `blood_group` | Blood Group, Blood |
| `address` | Address, Current Address |

**Validation per row (all independent — one failure never stops the rest):**
- `first_name`, `last_name`, `email`, `role`, `department`, `designation`, `branch`, `date_of_joining` — required
- Email: valid format; duplicate check against DB and within the uploaded file
- Phone: valid format if provided
- Branch: must match existing `Branch.branch_name` or `Branch.branch_code` (case-insensitive)
- Department: must match an active `Department` (case-insensitive)
- Designation: must exist AND belong to the selected department
- Role: matched by `role.name` or `role.display_name`; `system_admin` cannot be assigned via import
- Date formats: `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`, Excel date objects

**For each valid row:**
- `EmployeeCodeSettings.generate_employee_id()` generates employee ID atomically
- `User.objects.create_user()` creates the account with `must_change_password=True`
- `_auto_assign_managers()` runs to auto-assign HR and reporting manager
- `EmployeeProfile` created if any optional profile fields (gender, DOB, blood group, address) are present

**Audit log written** with `total_rows`, `created`, `skipped`, `failed` counts.

**Files modified:**
```
backend/apps/accounts/serializers.py
  — EmployeeBulkImportRowSerializer added (+ _EMP_PHONE_RE, _EMP_IMPORT_DATE_FMTS,
    _EMP_VALID_GENDERS, _EMP_VALID_BLOOD constants)

backend/apps/accounts/views.py
  — import csv, io added at top
  — EmployeeBulkImportRowSerializer added to serializer import block
  — _EMP_IMPORT_COL_MAP, _EMP_MAX_IMPORT_ROWS, _EMP_MAX_IMPORT_BYTES, _EMP_ALLOWED_ROLES added
  — _normalize_employee_import_headers(), _emp_xlsx_cell_to_str(),
    _parse_employee_xlsx_rows(), _parse_employee_csv_rows(), EmployeeBulkImportView added

backend/apps/accounts/urls.py
  — EmployeeBulkImportView imported
  — employees/bulk-import/ URL pattern added (before employees/<str:employee_id>/ to prevent conflict)
```

---

**3. Bulk Import — Enterprise re-upload behaviour (both modules)**

**Problem:** When a user uploaded a file, fixed the failures, and re-uploaded the same file, previously-imported rows came back as "Duplicate email" errors. This blocked the corrected rows from being visible in the results.

**Fix applied to both `CandidateBulkImportView` and `EmployeeBulkImportView`:**

Duplicate rows (email already in DB or already seen in this file) are now **skipped silently** instead of being treated as failures. They appear in a new `skipped_rows` section of the response.

**New response shape (both modules):**

```json
{
  "status": "success",
  "message": "Bulk import completed.",
  "data": {
    "total_rows": 10,
    "created": 7,
    "skipped": 2,
    "failed": 1,
    "created_rows": [
      { "row": 2, "identifier": "alice@company.com" }
    ],
    "skipped_rows": [
      { "row": 3, "identifier": "bob@company.com", "reason": "Already exists" }
    ],
    "errors": [
      { "row": 5, "field": "branch", "identifier": "charlie@company.com", "message": "Branch \"XYZ\" not found." }
    ]
  }
}
```

**Enterprise behaviour:**

| Upload | Alice | Bob (bad email) | Charlie (bad branch) |
|---|---|---|---|
| Upload 1 | ✅ Created | ❌ Failed | ❌ Failed |
| Upload 2 (fixed) | ⏭ Skipped | ✅ Created | ✅ Created |

**Additional improvement:** All error entries now include `identifier` (email) field to support client-side Error Report CSV generation.

**Candidate import:** `AuditLog` entry was missing entirely — now added with `created/skipped/failed` counts.

**Files modified:**
```
backend/apps/recruitment/views.py
  — CandidateBulkImportView: email/phone duplicates → skipped_rows (not row_errors)
  — to_create_meta list added to track created_rows
  — AuditLog.objects.create() added (was missing)
  — Response: success/failed → created/skipped/failed + created_rows/skipped_rows/errors

backend/apps/accounts/views.py
  — EmployeeBulkImportView: email duplicates → skipped_rows (not row_errors)
  — created_rows list added with {row, identifier, employee_id}
  — AuditLog updated to include skipped count
  — Response: success/failed → created/skipped/failed + created_rows/skipped_rows/errors
```

### Frontend Prompts Given

- Candidate Bulk Import full implementation prompt (endpoints, request format, response shape, TypeScript types, component spec, error/skipped table, download error report)
- Employee Bulk Import full implementation prompt (same structure, employee-specific columns and types)

### Pending

- Frontend implementation of Employee Bulk Import modal
- Frontend implementation of Candidate Bulk Import modal
- Frontend implementation of all 3 dashboard pages
- Frontend: Leave application preview summary panel
- Frontend: Leave stats page — `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns
- Frontend: Employee Profile page — `?employee_id=` wiring to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-21
**Author: Teerdaveni**

### Features Shipped

**1. Carry Forward Leave — Configuration & Process** (backend complete)

Full carry-forward leave workflow implemented. Extends the existing `can_carry_forward` / `max_carry_forward_days` partial implementation with type, mode, expiry, manual execution APIs, and audit log.

---

#### Model Changes

**`LeavePolicy` — 3 new fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `carry_forward_type` | CharField | `limited` | `limited` = cap at `max_carry_forward_days`; `unlimited` = carry all unused days |
| `carry_forward_mode` | CharField | `automatic` | `automatic` = handled by Celery on 1 Jan; `manual` = HR/Admin executes via API |
| `carry_forward_expiry_days` | PositiveIntegerField | `0` | Days before carry-forwarded balance expires (0 = never) |

**`LeaveBalance` — 1 new field:**

| Field | Type | Description |
|---|---|---|
| `carry_forward_expiry_date` | DateField (nullable) | Set when carry forward is applied; `null` if `expiry_days == 0` |

**`CarryForwardLog` — new audit model** (`hrms_carry_forward_logs`):

| Field | Description |
|---|---|
| `from_year` / `to_year` | Year range of the carry-forward run |
| `leave_type` | Leave type (blank = all types) |
| `executed_by` | FK to User who triggered the run |
| `process_mode` | `execute` |
| `total_processed` | Balances successfully created |
| `total_skipped` | Rows skipped (already existed, ineligible, or zero unused) |
| `total_failed` | Rows that raised an exception |
| `is_completed` | `True` on successful run completion |
| `notes` | Free-text field for run notes |

Migration: `0014_carry_forward` — applied ✓

---

#### API Endpoints

All 4 endpoints require `system_admin`, `hr_admin`, or `hr` role — others get 403.

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/hrms/leave/carry-forward/years/` | Available from/to year pairs derived from existing `LeaveBalance.year` values; includes `default_from` and `default_to` based on current year |
| `POST` | `/api/hrms/leave/carry-forward/preview/` | Dry-run — shows every row that would be processed without writing to DB |
| `POST` | `/api/hrms/leave/carry-forward/run/` | Executes carry forward; returns `409` if this `from_year→to_year` pair was already completed |
| `GET` | `/api/hrms/leave/carry-forward/history/` | Paginated audit log of all past runs |

**Preview request / response:**
```json
// POST /api/hrms/leave/carry-forward/preview/
{ "from_year": 2025, "to_year": 2026 }

// Response
{
  "from_year": 2025, "to_year": 2026,
  "total_rows": 12, "pending_count": 10, "already_processed_count": 2,
  "preview_rows": [
    {
      "employee_id": "RSS00001", "employee_name": "Arun Kumar",
      "leave_type": "earned", "leave_type_display": "Earned Leave",
      "unused_days": 8.0, "carry_forward_amount": 5.0,
      "expiry_date": "2026-12-31", "already_processed": false
    }
  ]
}
```

**Run request / response:**
```json
// POST /api/hrms/leave/carry-forward/run/
{ "from_year": 2025, "to_year": 2026 }

// Response (CarryForwardLog)
{
  "id": "...", "from_year": 2025, "to_year": 2026,
  "process_mode": "execute", "executed_by_name": "Teerdaveni",
  "total_processed": 10, "total_skipped": 2, "total_failed": 0,
  "is_completed": true, "created_at": "2026-07-21T..."
}
```

---

#### Carry Forward Logic

**For manual run (`/run/`):**
- Only processes policies where `carry_forward_mode = manual`
- Skips employees who already have a `to_year` balance for a given leave type (idempotent)
- `carry_forward_type = unlimited` → carries all unused days; `limited` → capped by `max_carry_forward_days`
- If `carry_forward_expiry_days > 0` → sets `carry_forward_expiry_date = today + expiry_days` on the created balance
- Duplicate-run guard: returns `409` if a completed log already exists for the same `from_year→to_year`

**For Celery automatic run (`reset_annual_leave_balances`):**
- Skips policies where `carry_forward_mode = manual` (those are HR-managed only)
- Respects new `carry_forward_type` (unlimited removes the `max_carry_forward_days` cap)
- Sets `carry_forward_expiry_date` on each new balance when `expiry_days > 0`
- Remains idempotent (`get_or_create`)

---

#### Files Modified

```
backend/apps/hrms/models.py
  — CARRY_FORWARD_* constants added
  — LeavePolicy: carry_forward_type, carry_forward_mode, carry_forward_expiry_days added
  — LeaveBalance: carry_forward_expiry_date added
  — CarryForwardLog model added

backend/apps/hrms/migrations/0014_carry_forward.py     (NEW — applied)

backend/apps/hrms/serializers.py
  — CarryForwardLog imported
  — LeavePolicySerializer, LeavePolicyCreateSerializer, LeavePolicyUpdateSerializer:
      carry_forward_type, carry_forward_mode, carry_forward_expiry_days added
  — LeaveBalanceSerializer: carry_forward_expiry_date added
  — CarryForwardInputSerializer, CarryForwardLogSerializer added

backend/apps/hrms/views/leave.py
  — imports: timedelta, CARRY_FORWARD_UNLIMITED, CARRY_FORWARD_MANUAL,
      CarryForwardLog, CarryForwardInputSerializer, CarryForwardLogSerializer added
  — _eligible_for_policy(), _build_carry_forward_rows() helpers added
  — CarryForwardYearsView, CarryForwardPreviewView, CarryForwardRunView,
      CarryForwardHistoryView added

backend/apps/hrms/views/__init__.py
  — All 4 carry-forward views exported

backend/apps/hrms/urls.py
  — All 4 carry-forward views imported
  — 4 URL patterns added under leave/carry-forward/

backend/apps/hrms/tasks.py
  — timedelta imported
  — CARRY_FORWARD_MANUAL, CARRY_FORWARD_UNLIMITED imported from hrms.models
  — reset_annual_leave_balances: excludes manual-mode policies; respects carry_forward_type;
      sets carry_forward_expiry_date on created balances
```

### Pending

- Frontend implementation of Carry Forward Leave UI (years selector, preview table, run button, history log)
- Frontend implementation of Employee Bulk Import modal
- Frontend implementation of Candidate Bulk Import modal
- Frontend implementation of all 3 dashboard pages
- Frontend: Leave application preview summary panel
- Frontend: Leave stats page — `lop_days` and `lop_requests` fields
- Frontend: Leave approvals — Branch + Department + Status filter dropdowns
- Frontend: Employee Profile page — `?employee_id=` wiring to leave + attendance tabs
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-21 (Part 2)
**Author: Teerdaveni**

### Features Shipped

---

**1. Financial Year Configuration**

Single source of truth for Financial Year is `Company.financial_year_start_month` (CharField, default `'April'`). Computed FY strings are never persisted — always derived at runtime.

**Endpoints:**

| Method | URL | Roles |
|---|---|---|
| `GET` | `/api/settings/company/financial-year/` | Any authenticated user |
| `PUT` | `/api/settings/company/financial-year/` | `system_admin` only |

**Response shape:**
```json
{
  "financial_year_start_month": "April",
  "previous_financial_year": "FY 2025-26",
  "current_financial_year": "FY 2026-27",
  "next_financial_year": "FY 2027-28"
}
```

- Cached 24 h via `FinancialYearCacheService` in `core/cache_service.py`
- Cache invalidated on every `Company` model `post_save` signal (`apps/accounts/signals.py`)
- All modules consume `get_company_financial_year_config()` from `apps/accounts/utils.py`
- `_current_year()` in `apps/hrms/views/leave.py` updated to return FY start year (not calendar year)
- Migration: `apps/accounts/migrations/0043_company_financial_year.py`

**Files modified:** `apps/accounts/models.py`, `apps/accounts/utils.py`, `apps/accounts/views.py`, `apps/accounts/urls.py`, `apps/accounts/signals.py`, `apps/accounts/migrations/0043_company_financial_year.py`, `core/cache_service.py`, `apps/hrms/views/leave.py`

---

**2. Sample Template Downloads — All 3 Bulk Import Modules**

Shared utility `core/file_utils.py` with `build_sample_csv()` and `build_sample_xlsx()`:
- CSV: UTF-8 BOM so Excel opens without encoding prompts
- XLSX: bold/blue header row, first row frozen, auto column widths via `openpyxl`

| Endpoint | View | Roles |
|---|---|---|
| `GET /api/employees/bulk-import/sample/?format=csv\|xlsx` | `EmployeeBulkImportSampleView` | `system_admin`, `hr_admin` |
| `GET /api/attendance/import/sample/?format=csv\|xlsx` | `HRAttendanceImportSampleView` | `attendance.create` permission |
| `GET /api/recruitment/candidates/bulk-import/sample/?format=csv\|xlsx` | `CandidateBulkImportSampleView` | `system_admin`, `hr`, `hr_admin` |

Column headers verified to exactly match each module's `_COL_MAP` aliases — imports work from any downloaded template without header edits.

**Files modified:** `core/file_utils.py` (new), `apps/accounts/views.py`, `apps/accounts/urls.py`, `apps/attendance/views/hr_attendance.py`, `apps/attendance/views/__init__.py`, `apps/attendance/urls.py`, `apps/recruitment/views.py`, `apps/recruitment/urls.py`

---

**3. Leave Opening Balance Import (Migration Tool)**

Enterprise-scale one-time import for onboarding leave history from a previous HRMS. Writes directly to the existing `LeaveBalance` model — no new models.

**Endpoints:**

| Method | URL | Roles |
|---|---|---|
| `POST` | `/api/leave/balance/import/` | `system_admin`, `hr_admin`, `hr` |
| `GET` | `/api/leave/balance/import/sample/?format=csv\|xlsx` | `system_admin`, `hr_admin`, `hr` |

**POST request:** `multipart/form-data`, field `file` — CSV or XLSX, max 5 MB

**POST response:**
```json
{
  "success": true,
  "message": "Import complete. 45 created, 0 failed, 2 skipped.",
  "data": {
    "total_rows": 47,
    "created": 45,
    "failed": 0,
    "skipped": 2,
    "processing_time_ms": 312,
    "error_report_csv": "<base64 UTF-8 BOM CSV, present only when failures > 0>"
  }
}
```

**CSV template columns:**
`Employee ID`, `Leave Type`, `Financial Year`, `Opening Balance`, `Leave Allocated`, `Leave Availed`, `Leave Balance`, `Carry Forward Days`, `Remarks`

**Key implementation details:**
- Flexible header aliasing via `_LEAVE_IMPORT_COL_MAP` — accepts `emp_id`, `employee code`, `cf_days`, `carried forward`, etc.
- FY parsing: `"FY 2026-27"` / `"2026-27"` / `"2026"` all normalise to integer start year `2026`
- `LeaveBalance` mapping: `total_days = opening_balance + carry_forward + allocated`, `used_days = availed`, `carried_forward = carry_forward`
- N+1 free: 3 queries pre-load all reference data (employees, leave types, existing balances) before row loop
- `unique_together = (employee, leave_type, year)` — existing rows reported as errors, not silently overwritten
- Intra-file duplicates: first occurrence wins; subsequent rows skipped with count increment
- 500-row batches via `LeaveBalance.objects.bulk_create()` inside `transaction.atomic()`
- `AuditLog` created on every import call (including partial failures)
- `error_report_csv` is base64-encoded UTF-8 BOM CSV — frontend decodes and offers as file download
- URL ordering: `leave/balance/import/` and `leave/balance/import/sample/` placed **before** `leave/balance/<str:balance_id>/` to prevent static paths being matched as the wildcard

**Files modified:** `apps/hrms/views/leave.py`, `apps/hrms/views/__init__.py`, `apps/hrms/urls.py`

---

**4. Dev Server Orphan Process — Documented Gotcha**

Django `runserver` spawns a child request-handler process. Killing the parent with `Ctrl+C` does not always terminate the child. The orphan keeps port 8000 bound with old code — subsequent restarts may attach a second process that never receives traffic, causing newly registered URLs to 404 even though `manage.py shell resolve()` confirms the pattern exists.

**Fix — kill all manage.py processes before every restart:**
```powershell
Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like "*manage.py*" } | Stop-Process -Force
python manage.py runserver 0.0.0.0:8000
```

---

### Pending

- Frontend: Leave Opening Balance Import modal (file upload, progress indicator, error CSV download button)
- Frontend: Financial Year Configuration settings page
- Frontend: Carry Forward Leave UI (years selector, preview table, run button, history log)
- Frontend: Employee Bulk Import modal
- Frontend: Candidate Bulk Import modal
- Leave integration — auto-mark employee `on_leave` in attendance when leave approved
- Attendance reports — CSV/PDF export for HR

---

## Session Log — 2026-07-21
**Author: SandalaNithin**

### Changes Shipped

**1. Approvals page — removed "My Requests" tab**

Removed the self-service "My Requests" tab from `/dashboard/approvals` per request. The page now shows only "Team Approvals" and "Attendance Approval", each still gated by permission (`leave.approve`/`expenses.approve` and `payroll.view`/`payroll.approve` respectively).

All code that became dead as a result was deleted rather than left unused: `MyRequestsSection`, `NewLeaveModal`, `NewExpenseModal`, `StatusFilter` dropdown, `CategoryOption` interface, `LEAVE_TYPES`/`DURATIONS` constants, and the now-unused `useToast` import.

Tab list and default active tab are now derived from permissions (`useMemo`), with a `useEffect` guard that switches to the first available tab if the currently-selected one is no longer valid (e.g. permissions resolve after the first render).

**Files modified:**
```
frontend/app/dashboard/approvals/page.tsx
  — Section type: "my-requests" | "approvals" | "attendance" → "approvals" | "attendance"
  — Removed MyRequestsSection, NewLeaveModal, NewExpenseModal, StatusFilter,
    CategoryOption, LEAVE_TYPES, DURATIONS (dead code after tab removal)
  — sections list wrapped in useMemo(canApprove, canApproveAttendance)
  — useEffect added: corrects `section` state to sections[0] if the active
    section is no longer in the permitted list
  — Removed unused `useToast` import
```

**Note for the team:** the standalone `/dashboard/my-requests` page and its sidebar nav link are untouched — that remains the self-service entry point for leave/expense requests. One behavioural side effect: an employee with no approval permission (`leave.approve`, `expenses.approve`, `payroll.view`, `payroll.approve`) who navigates directly to `/dashboard/approvals` will now see an empty tab bar, since "My Requests" was previously the only tab available to them there. Flagged, not addressed — no redirect/fallback was requested.

Verified with `eslint` (0 errors, 0 warnings) and `tsc --noEmit` (0 errors) on the changed file.

---

## Session Log — 2026-07-21
**Author: Swetha**

Full-stack validation and bug-fix pass across Add Candidate, Leave Policy settings, and Holiday Calendar — reported as three separate bug lists, fixed backend + frontend together for each.

### 1. Add Candidate — Field Validation

**Reported:** Full Name accepted numbers; Position Applied accepted numbers/special characters; Phone accepted unlimited length plus letters/symbols; Interview Date accepted past dates.

**Backend** (`backend/apps/recruitment/serializers.py`):
- `_NAME_RE`, `_POSITION_RE` added; tightened `_PHONE_RE` to `^\+?[0-9]{10,15}$` (digits only, optional leading `+`)
- Applied to both `CandidateCreateSerializer` (covers Add Candidate **and** the Refer & Earn submit path — same serializer) and `CandidateUpdateSerializer` (edit path had the identical bug)
- `validate_interview_date()` added to both — rejects any date before `timezone.localdate()` (IST-aware, matches project convention)
- Bulk CSV import serializer left untouched — imports legitimately carry historical dates

**Frontend:**
- New shared `lib/candidateValidation.ts` — `NAME_RE`, `POSITION_RE`, `PHONE_RE`, `sanitizeName/Position/Phone`, `todayDateString()` (mirrors backend regexes exactly)
- `app/dashboard/interview-list/AddCandidateModal.tsx` — inputs sanitize on keystroke (bad chars never land in the field), `handleSave()` re-validates before the API call, date input gets `min={today}`
- `app/dashboard/interview-list/EditCandidateModal.tsx` — same treatment for Name/Position/Interview Date (no phone field here); past-date check only fires when the date is actually *changed* — resaving a candidate with an already-past interview date (interview already happened) must not be blocked

### 2. Leave Policy Settings (`/dashboard/settings/leave-policy`)

**Reported:** Add Leave Type → Display Name accepted numbers/symbols; no delete/deactivate option on leave types; Max Carry Fwd behaved oddly; Add Credit Rule → Leave Type field accepted numbers/symbols and duplicate leave types.

**Backend** (`backend/apps/hrms/serializers.py`):
- `_LEAVE_NAME_RE` + `validate_leave_type_label()` on `LeavePolicyCreateSerializer` — letters/spaces/hyphens only
- `LeavePolicyCreateSerializer.validate()` / `LeavePolicyUpdateSerializer.validate()` — when `can_carry_forward` is off, `max_carry_forward_days` is force-reset to 0 server-side (was silently keeping a stale disabled-field value); when on, must be ≥ 1
- **Correction made mid-fix:** initially also capped `max_carry_forward_days` at `annual_days`, but the real `earned` leave policy already has `annual_days: 15` / `max_carry_forward_days: 30` (multi-year rollover cap, not a per-year figure) — that check would have broken saving existing data, confirmed against the live DB row and reverted
- Delete (`DELETE /api/leave/policy/<leave_type>/`) and deactivate (`is_active` via PUT/PATCH) already existed server-side — the 6 built-in types were already delete-protected. No backend gap here, only frontend was missing the buttons

**Frontend:**
- New shared `lib/leaveValidation.ts` — `LEAVE_NAME_RE` / `sanitizeLeaveName`, used by both tabs below
- `PolicyTab.tsx` — Display Name sanitizes/validates; Actions column gained a working Deactivate/Activate toggle (`ti-toggle-left/right`, same icon convention as `settings/permissions/page.tsx`) and a Delete button (disabled + tooltipped for the 6 built-in types via a local `BUILTIN_TYPES` set mirroring the backend's `_BUILTIN`); unchecking "Allow Carry Forward" now auto-resets Max Carry Fwd to 0 in both Edit and Create forms instead of leaving a stale disabled value
- `CreditTab.tsx` — Leave Type field now sanitizes/validates the same way; duplicate leave types (case-insensitive, excluding the row being edited) now rejected client-side
- **Note:** Credit Rules has no backend API yet — `CreditTab.tsx` is local mock state only (`SEED` array, `setTimeout` fake save), labelled "Automation coming soon" in the UI. Issues 4/5 there were necessarily frontend-only fixes; a real backend for Credit Rules is still unbuilt

### 3. Holiday Calendar

**Reported:** Add Holiday name field accepted numbers/symbols; same holiday name accepted with different dates; holiday name not shown on employee calendar; system admin not seeing branch-wise holidays in the system calendar or the holiday list.

**Backend:**
- `backend/apps/hrms/serializers.py` — `_HOLIDAY_NAME_RE` + `validate_name()` on `HolidayCreateSerializer` (letters/spaces/apostrophe/period/hyphen, must contain a letter); `validate()` blocks creating/renaming a holiday to a name that already exists in the same year for the same branch scope — **but skips the check entirely when editing without touching name/date/branch**, because the live DB already had 3 duplicate "Bonalu" rows for branch 10 (2026-07-23 / 07-30 / 08-19) predating this fix; without the skip, any future edit to those rows (even an unrelated field) would falsely reject as a duplicate against its own siblings
- `backend/apps/hrms/views/holidays.py` — root cause of the two "branch holidays missing for system admin" reports: `HolidayListCreateView.get()` fell back to `qs.filter(branch__isnull=True)` (or the admin's own mismatched `.branch` string) whenever no `?branch=` param was sent. Added `_is_unrestricted(user)` (same pattern as `apps/attendance/views/hr_attendance.py`) so `system_admin`/superuser see every branch's holidays by default. Verified directly against the live `sysadmin@royal.com` account — before the fix they saw only the 1 company-wide holiday; after, all 5 (4 branch + 1 company-wide)
- `backend/apps/attendance/services_attendance.py` + `serializers_my_attendance.py` — the attendance calendar only ever stored the literal string `"Holiday"` per day, never the actual holiday's name. Added `_holiday_name()` (used when building the `AttendanceRecord.note` for a holiday day) and `_holiday_names()` (used by `get_calendar()`, backed by the existing `HolidayCacheService.get_holidays_with_names`); new `holiday_name` field added to each calendar day and to `DayRecordSerializer`

**Frontend:**
- `app/dashboard/my-attendance/_components/AttendanceCalendar.tsx` — now renders the specific holiday name under the day cell when `status === "Holiday"`. Confirmed this is the live, wired-up employee calendar (`my-attendance/page.tsx` → `CalendarAndHistory` → `AttendanceCalendar`) — `/dashboard/my-calendar` and `_components/MyCalendarTab.tsx` are dead/mock-data code with zero real importers, left untouched
- `types/attendance.ts` — `holiday_name?: string | null` added to `DayRecord`
- `app/dashboard/settings/holiday-calendar/_components/HolidayFormModal.tsx` — Holiday Name field sanitizes/validates, mirroring the backend regex
- Issues 4/5 needed **no** frontend change — `holiday-calendar/page.tsx` already calls the same `/leave/holidays/` endpoint and filters branch client-side; once the backend stopped hiding branch-specific rows, both the List and Calendar views picked them up automatically

### Files Changed (2026-07-21)

```
backend/apps/recruitment/serializers.py       — name/position/phone regex, interview_date past-block
backend/apps/hrms/serializers.py              — leave type label regex, carry-forward reset,
                                                 holiday name regex + duplicate-name check
backend/apps/hrms/views/holidays.py           — _is_unrestricted() branch-visibility fix
backend/apps/attendance/services_attendance.py — _holiday_name(), _holiday_names(), holiday_name field
backend/apps/attendance/serializers_my_attendance.py — DayRecordSerializer.holiday_name

frontend/lib/candidateValidation.ts   (NEW)
frontend/lib/leaveValidation.ts       (NEW)
frontend/app/dashboard/interview-list/AddCandidateModal.tsx
frontend/app/dashboard/interview-list/EditCandidateModal.tsx
frontend/app/dashboard/settings/leave-policy/_components/PolicyTab.tsx
frontend/app/dashboard/settings/leave-policy/_components/CreditTab.tsx
frontend/app/dashboard/settings/holiday-calendar/_components/HolidayFormModal.tsx
frontend/app/dashboard/my-attendance/_components/AttendanceCalendar.tsx
frontend/types/attendance.ts
```

All backend changes verified by direct invocation against the real database (not just synthetic payloads) — including catching and reverting the annual-days carry-forward cap before it could ship and break the existing `earned` leave policy. `npx tsc --noEmit` clean after every frontend batch.

### Pending

- Credit Rules module still has no backend (`GET/POST/PUT/DELETE /api/leave/credit-rules/` or similar) — `CreditTab.tsx` is mock state only
- Everything listed as Pending in the 2026-07-20 (Part 2) entry above is still outstanding

---

## Session Log — 22/07/2026
**Author: G.Durga Prasad**
**Branch: Backend/prasad**

Started the session by merging `origin/demo` (18 commits — carry-forward leave settings, payroll bonus/reimbursement edit modals, candidate bulk import, financial year section) into the working branch. Rest of the session was a mix of permission-architecture fixes, a new dynamic Manager Dashboard, live production debugging (payslips + attendance geofencing), and a broad codebase audit.

### Bug Fixes Shipped

**1. "My Payslips" missing from employee sidebar**
- Root cause: nav item and the `proxy.ts` route guard were both gated on `payroll.view`, which migration `0042` had (correctly) removed from the `employee` role — that permission is for HR's "view every employee's payroll" admin page, not self-service payslips
- Proper fix (not just `permission: null`): added a new, distinct RBAC permission `payroll.view_own`, seeded to all 4 roles by default, kept separate from `payroll.view` so employees still can't see the HR admin Payroll page
- Backend: `MyPayslipsView.get` and `AcknowledgePayslipView.post` now check `payroll.view_own` via a new `_has_perm()` helper (matches the pattern already used in `payroll/views/structures.py`)
- Note: permissions are baked into the JWT at login — anyone already logged in needs to log out/in to pick up the new grant
- Files: `backend/apps/accounts/migrations/0043_seed_payroll_view_own_permission.py` (new), `backend/apps/payroll/views/payslips.py`, `frontend/lib/navConfig.ts`, `frontend/proxy.ts`

**2. Payroll wizard silently skipped employees with no salary configured**
- Root cause: `ProcessPayrollView` (`backend/apps/payroll/views/cycles.py`) already returned a `skipped: [...]` list of employee names lacking an `EmployeeSalaryConfig`, but the frontend "Compute Salaries" step discarded the response body entirely — HR had zero visibility that anyone was excluded
- Fix: capture the response and show a warning banner naming exactly who was skipped and why, with a pointer to fix it (Employees → Salary tab)
- This is how a live bug was diagnosed: `gdurgaprasad065@gmail.com` (joined 2026-07-21) had no payslip because no `EmployeeSalaryConfig` existed when the June 25–July 24 cycle was processed, and that cycle is already `PAID` (closed) — no way to retroactively generate it; will resolve automatically from the next cycle once salary is configured
- Files: `frontend/types/payroll.ts` (new `ProcessPayrollResult` type), `frontend/app/dashboard/payroll/_components/EarningsDeductionsStep.tsx`

**3. Attendance clock-in false 403 ("outside assigned office location")**
- Diagnosed for an employee at the Hyderabad branch (150m geofence radius) whose GPS reading was accurate but imprecise enough to land just outside the radius
- Two real, verified fixes (not a radius change): (a) frontend now requests `enableHighAccuracy: true` from the browser's Geolocation API — previously left at the default `false`, which lets the browser use a fast, low-precision Wi-Fi/IP-based fix instead of real GPS; (b) backend geofence distance check now widens the branch radius by the device's self-reported `accuracy` value, capped at 100m so a wildly imprecise reading (e.g. a laptop's IP-based location, often 1-2km off) still can't bypass geofencing entirely
- Also added a `logger.warning(...)` on rejection (distance, branch, effective radius, reported accuracy) — discovered mid-debugging that this app's logger had no handler wired up in `settings.py` (`LOGGING` only configures the `accounts` logger), so `.info()` calls were being silently dropped everywhere in `attendance`; used `.warning()` so it reaches Python's default stderr fallback and actually shows up in the runserver console
- Verified by simulation against real branch data: a reading 220m away with 90m reported accuracy is now correctly allowed; a reading 2000m away with 2000m reported accuracy is still correctly rejected (the 100m cap holds)
- Separately, a **second, unrelated** 403 case for a different "Nithin" account (`sandalanithinkumar123@gmail.com`) turned out to be a pure data issue, not a code bug: his `branch` field was set to `"TASK"` (code `WGL`), whose registered coordinates are ~185km from Hyderabad, while his real GPS position was essentially exactly at the Hyderabad branch. Needs a manual fix (not done this session): Employees → his profile → change Branch from "TASK" to "Hyderabad"
- Files: `backend/apps/attendance/services_geofencing.py`, `backend/apps/attendance/services_attendance.py`, `frontend/hooks/useClockWidget.ts`

### Features Shipped

**4. Manager Dashboard — replaced 100% hardcoded/fake data with live backend-driven widgets**
- New backend views, all scoped to `request.user.direct_reports` (via the `reporting_manager` FK) and gated by role name (`manager__team_lead`, matching the existing `_is_hr_or_admin`-style convention in this app rather than RBAC codenames): `ManagerKPIView` (team size, pending approvals, on-leave-today, attendance rate), `ManagerPendingApprovalsView` (real top-5 pending leave/expense items, links through to `/dashboard/approvals` for the actual approve/reject — not duplicated here), `ManagerTeamAttendanceTodayView`, `ManagerUpcomingLeaveView`, `ManagerRecentActivityView` (merged clock-in + leave-application feed)
- New routes under `/dashboard/manager/*`
- Frontend: `types/managerDashboard.ts`, `hooks/useManagerDashboard.ts`, 5 new components under `components/dashboard/manager/` (Console, PendingApprovals, TeamAttendance, UpcomingLeave, RecentActivity) — same `useFetch` pattern as the HR/Employee dashboards
- Verified directly against real dev data (a manager with 5 direct reports, and one with 0) — all 5 endpoints return correct data, zero-report edge case handled without errors
- Files: `backend/apps/dashboard/views/manager.py` (new), `backend/apps/dashboard/views/__init__.py`, `backend/apps/dashboard/urls.py`, `frontend/types/managerDashboard.ts` (new), `frontend/hooks/useManagerDashboard.ts` (new), `frontend/components/dashboard/manager/*.tsx` (new, 5 files), `frontend/app/dashboard/_components/ManagerDashboard.tsx` (rewritten)

### Codebase Audit — findings only, NOT yet fixed

Ran a broad audit (error handling / input validation / permission architecture) across `accounts`, `branch`, `recruitment`, `hrms`, `attendance`, `payroll`. The `dashboard`/`assessments`/`notifications` pass was **not completed** — session moved on before it ran. None of the ~65 findings below were fixed this session; this is a punch list for whoever picks it up next. Most notable (full detail was posted in chat, not reproduced here):

- **CRITICAL** — `backend/apps/payroll/views/payslips.py`: `UpdatePayslipReimbBonusView`, `ExpenseSummaryForCycleView`, `ReferralBonusSummaryForCycleView` all call `_is_hr_admin(request.user)`, which is never defined anywhere — every call 500s. Breaks the Bonuses/Reimbursements payroll wizard step completely.
- **CRITICAL** — `backend/apps/attendance/views/late_mark_lop.py` + `absence_alert.py` use Django's built-in `user.has_perm(...)` instead of this project's custom RBAC (`role.role_permissions.filter(...)`) — always `False` for non-superusers regardless of actual role grants, since the two systems are never synced.
- **CRITICAL** — `backend/apps/accounts/serializers.py` (`ForgotPasswordSerializer`): fully enumerates whether an email exists (400 vs 200), contradicting its own anti-enumeration comment.
- **CRITICAL** — `frontend/proxy.ts` `getPermissions()`: falls back to the unsigned, client-writable `royal_hrms_user` cookie when the JWT lacks a `permissions` claim.
- **HIGH** — several `payroll` money-field gaps: no min/max validators on statutory rates or salary component percentages (components can sum >100% of CTC with no rejection), `annual_ctc` can be negative, bonus/reimbursement edits accept negative amounts.
- **HIGH** — `payroll/views/attendance_approval.py` `CycleEmployeeDailyView`: reportee-scoping check compares against the literal string `'manager'`, but the role is actually named `'manager__team_lead'` — the scoping is dead code, any manager can query any employee's daily attendance.
- **HIGH** — `hrms/views/leave.py`: HR approval-queue *list* is correctly scoped by `employee__hr=user` for branchless HR users, but the *detail/approve* endpoints (`_can_hr_access_request`) skip that check entirely for the same case — guessable-UUID bypass of the approval scope.
- Full list (~15 findings per app, ranked by severity) is in the chat history for this session — re-run the audit prompts or ask Claude to recall specifics rather than re-deriving from scratch.

### Uninvestigated — found mid-session, not caused by this session's work

Two unexplained changes appeared in the working tree that neither this session nor any command run in it produced: `backend/apps/recruitment/views.py` had several class docstrings stripped (code unchanged), and a new Django merge migration `backend/apps/hrms/migrations/0015_merge_20260722_1100.py` appeared. Left untouched at the user's instruction pending their own investigation — worth checking before the next session if the source is still unknown.

### Files Changed (22/07/2026)

```
backend/apps/accounts/migrations/0043_seed_payroll_view_own_permission.py  (NEW)
backend/apps/payroll/views/payslips.py           — _has_perm() added; MyPayslipsView + AcknowledgePayslipView
                                                     gated by payroll.view_own
backend/apps/dashboard/views/manager.py           (NEW) — ManagerKPIView, ManagerPendingApprovalsView,
                                                     ManagerTeamAttendanceTodayView, ManagerUpcomingLeaveView,
                                                     ManagerRecentActivityView
backend/apps/dashboard/views/__init__.py          — exports for the above
backend/apps/dashboard/urls.py                    — /dashboard/manager/* routes
backend/apps/attendance/services_geofencing.py    — accuracy-tolerance cap, rejection logging
backend/apps/attendance/services_attendance.py    — passes employee_accuracy through to GeofencingService

frontend/lib/navConfig.ts                         — my-payslip: permission changed to payroll.view_own
frontend/proxy.ts                                 — /dashboard/my-payslip route guard restored, payroll.view_own
frontend/types/managerDashboard.ts                (NEW)
frontend/hooks/useManagerDashboard.ts             (NEW)
frontend/components/dashboard/manager/            (NEW — ManagerConsole.tsx, ManagerPendingApprovals.tsx,
                                                     ManagerTeamAttendance.tsx, ManagerUpcomingLeave.tsx,
                                                     ManagerRecentActivity.tsx)
frontend/app/dashboard/_components/ManagerDashboard.tsx   — rewritten to use the components above
frontend/types/payroll.ts                         — ProcessPayrollResult type added
frontend/app/dashboard/payroll/_components/EarningsDeductionsStep.tsx  — skipped-employees warning banner
frontend/hooks/useClockWidget.ts                  — enableHighAccuracy: true
```

All backend changes verified by direct invocation against the real dev database (not synthetic payloads) — migration applied and role grants confirmed, all 5 new manager dashboard endpoints hit with a real manager account, geofencing tolerance fix verified with distance simulations against the real Hyderabad branch record. `npx tsc --noEmit` and `eslint` clean after every frontend batch.

### Pending

- Fix the `_is_hr_admin` NameError in `payroll/views/payslips.py` (breaks Bonuses/Reimbursements step) — highest-priority carryover
- `gdurgaprasad065@gmail.com`: needs `EmployeeSalaryConfig` created (Salary tab) before the next payroll cycle
- `sandalanithinkumar123@gmail.com`: needs Branch corrected from "TASK" to "Hyderabad"
- Finish the `dashboard`/`assessments`/`notifications` audit pass (not started)
- Work through the ~65 audit findings above — none fixed yet, only diagnosed
- Investigate the source of the unexplained `recruitment/views.py` docstring stripping and the stray `hrms/migrations/0015_merge_20260722_1100.py`

---

## Session Log — 2026-07-22
**Author: Teerdaveni**

### Bug Fixes Shipped

**1. Sample Download 404 — All Bulk Import Endpoints**

All four `?format=csv` / `?format=xlsx` sample download endpoints returned 404 before authentication was even reached.

**Root cause:** DRF 3.15.2 `DefaultContentNegotiation.filter_renderers()` raises `Http404` (not `NotAcceptable`) when `?format=csv` has no matching renderer. This fires inside `APIView.initial()` before any view logic or auth check.

**Fix pattern applied to all four sample views:**
```python
def perform_content_negotiation(self, request, force=False):
    # ?format= selects csv/xlsx file type, not DRF renderer.
    # Bypass renderer filtering to prevent Http404 on unknown formats.
    from rest_framework.renderers import JSONRenderer
    return (JSONRenderer(), 'application/json')
```
These views return `HttpResponse` directly so the renderer is bypassed in `finalize_response` anyway — the override has zero side effects.

**Also fixed:** `_EMP_ALLOWED_ROLES` (accounts) and `_ALLOWED_IMPORT_ROLES` (recruitment) module-level constants were silently removed by a `git pull origin demo` auto-merge, causing `NameError` on every sample request. Restored from view docstrings.

| Endpoint | File |
|---|---|
| `GET /api/employees/bulk-import/sample/?format=csv\|xlsx` | `apps/accounts/views.py` |
| `GET /api/attendance/import/sample/?format=csv\|xlsx` | `apps/attendance/views/hr_attendance.py` |
| `GET /api/leave/balance/import/sample/?format=csv\|xlsx` | `apps/hrms/views/leave.py` |
| `GET /api/recruitment/candidates/bulk-import/sample/?format=csv\|xlsx` | `apps/recruitment/views.py` |

---

**2. Manager / Team Lead Dashboard — New Endpoint**

Single endpoint returns all dashboard data in one request. Designed for enterprise orgs (2,000+ employees) — no N+1 queries.

**Endpoint:** `GET /api/dashboard/manager/`

**Roles allowed:** `manager`, `team_lead`, `hr_admin`, `hr`, `system_admin`

**Response — 8 widgets:**

| Widget | Key | Contents |
|---|---|---|
| Team Overview | `team_overview` | total_members, present_today, absent_today, on_leave_today, remote_today |
| Quick Actions | `quick_actions` | pending_leave_approvals, pending_expense_approvals, correction_requests |
| Pending Approvals | `pending_approvals` | List of leave requests awaiting this manager (L1 or L2) |
| Today's Birthdays | `birthdays_today` | Employees with birthday today |
| Upcoming Birthdays | `upcoming_birthdays` | Employees with birthday in next 30 days |
| Recent Activity | `recent_team_activity` | Last 10 AuditLog entries for team |
| Team Attendance | `team_attendance` | Per-member attendance status for today |
| Upcoming Leaves | `upcoming_leaves` | Approved leaves starting in next 30 days |

**Performance design:**
- Team IDs fetched once: `manager.direct_reports.filter(is_active=True).values_list('id', flat=True)` — reused across all widgets
- Attendance aggregated via `GROUP BY` (single query, not per-row loop)
- Birthday cache: `dashboard:manager:birthdays:today:{hash}` and `upcoming:{hash}` — 6h TTL, keyed by manager ID
- Leave pending query: `Q(l1_approver=manager, status=REQ_PENDING) | Q(l2_approver=manager, status=REQ_L2_PENDING)`
- All list queries use `.only()` to avoid fetching unused columns

**Files changed:**
```
backend/apps/dashboard/views/manager.py      — NEW: ManagerDashboardView + 7 widget builder functions
backend/apps/dashboard/views/__init__.py     — ManagerDashboardView imported + added to __all__
backend/apps/dashboard/urls.py               — path('manager/', ...) added
```

---

**3. Leave Opening Balance Import — Integration Fix**

After a successful import via `POST /api/leave/balance/import/`, the imported balances were not visible in Employee Dashboard, Apply Leave, HR management, reports, or carry forward. Three bugs found and fixed.

**Bug 1 — Cache key ignored `year` parameter** (`apps/dashboard/views/overview.py:450`)

`EmployeeLeaveBalanceView` cached results under `dashboard:employee:leave_balance:{employee.id}`. Because the key had no year, a request for `?year=2026` could return a cached `?year=2025` response (or vice versa). After import, the new data was never served until the 10-minute TTL expired — and even then, the first re-fetch could re-cache the wrong year indefinitely.

```python
# Before:
cache_key = f'dashboard:employee:leave_balance:{employee.id}'
# After:
cache_key = f'dashboard:employee:leave_balance:{employee.id}:{year}'
```

**Bug 2 — No cache invalidation after import** (`apps/hrms/views/leave.py` — `LeaveOpeningBalanceImportView.post()`)

After `_bulk_insert_leave_balances()` completes, the affected employees' cache entries are now explicitly deleted so the dashboard reflects the import on the very next request.

```python
if created > 0:
    from django.core.cache import cache as _cache
    _cache.delete_many(list({
        f'dashboard:employee:leave_balance:{lb.employee_id}:{lb.year}'
        for lb in to_create
    }))
```

**Bug 3 — `valid_lt` label override in `_load_leave_ref_data()`** (`apps/hrms/views/leave.py:1538`)

The second loop (LeavePolicy) could override canonical `LEAVE_TYPE_CHOICES` mappings. Example: if a `LeavePolicy` had `leave_type='earned'` but `leave_type_label='Sick'`, then `valid_lt['sick'] = 'earned'` — any CSV row with "Sick" would be imported as `earned` leave, then fail to match the `sick` balance that apply-leave queries.

```python
# Before (unsafe override):
if p.get('leave_type_label'):
    valid_lt[p['leave_type_label'].lower()] = p['leave_type']

# After (labels only add new aliases, never override canonical codes):
if p.get('leave_type_label') and p['leave_type_label'].lower() not in valid_lt:
    valid_lt[p['leave_type_label'].lower()] = p['leave_type']
```

**Result:** After import, affected employees see their new balances on the next dashboard load (instant if cache was cold, ≤10 minutes if warm). All other leave views — Apply Leave, HR Management, Leave Reports, Carry Forward — read `LeaveBalance` directly with no cache, so they always reflect imports immediately.

**Files changed:**
```
backend/apps/dashboard/views/overview.py   — cache key includes year
backend/apps/hrms/views/leave.py           — cache invalidation after bulk insert; valid_lt label guard
```

### Pending

- Manager Dashboard frontend implementation (API prompt to be provided)
- Credit Rules backend (`GET/POST/PUT/DELETE /api/leave/credit-rules/`) — `CreditTab.tsx` is still mock-only
- Everything listed as Pending in the 2026-07-21 entry above is still outstanding

---

## Session Log — 2026-07-23
**Author: Swetha**

Backend-only follow-up on the payroll permission model, picked up from a frontend Payroll/My Payslips permission audit (5 numbered findings) and from the "_is_hr_admin NameError" item on the 22/07 audit punch list above. Also resolved a live migration-graph conflict that blocked `makemigrations`/`migrate` entirely, and along the way found this backend points at a **shared remote database** other sessions are actively writing to.

### 1. Payroll Permission Model — Audit Findings

**Before writing anything, verified each finding against the actual current code/DB rather than trusting the report at face value** — several had already been fixed or didn't match reality:

- **`_is_hr_admin` NameError** — already fixed before this session (confirmed via `git log`, commit `1ef85c0` era); the three endpoints already called `_is_payroll_admin()` instead. No `_is_hr_admin` reference exists anywhere in the codebase.
- **Remove hardcoded role-name checks in `payslips.py`** — `_is_payroll_admin()` (`user.role.name in ('hr', 'system_admin')`) removed entirely; all 8 call sites replaced with `_has_perm(user, codename)`, split by what each endpoint actually does: `payroll.view` for pure reads (`CyclePayslipListView`, `PayslipDetailView`'s admin branch, `ExpenseSummaryForCycleView`, `ReferralBonusSummaryForCycleView`, `PayslipQueryListView.get()`), `payroll.edit` for mutations (`UpdatePayslipReimbBonusView`, `DispatchPayslipsView`, `PayslipQueryResolveView`).
- **`payroll.view_own`** — permission and its seed migration (`0043_seed_payroll_view_own_permission`, granted to every role) already existed from the 22/07 session above; `MyPayslipsView`/`AcknowledgePayslipView` were already wired to it. The one gap: `PayslipQueryListView.post()` (raising a query) had zero permission check — added the same `payroll.view_own` gate there.
- **Remove `payroll.view` from manager** — added `0045_remove_payroll_view_from_manager.py`.
- **Verify role names before hardcoding (explicit ask)** — confirmed directly against the DB: `hr` is correct (not `hr_admin`); the "manager" role's actual `name` is **`manager__team_lead`**, not `manager` — the same drift already flagged in the 22/07 audit's `attendance_approval.py` finding above (`CycleEmployeeDailyView` comparing against the literal string `'manager'`, permanently dead code) and independently documented in `0043_seed_payroll_view_own_permission`'s own docstring. The new migration targets the real name.

**Caught mid-fix, before it shipped:** `payroll.edit` was granted **only** to `system_admin` — not `hr`. Naively swapping the role check for `_has_perm(user, 'payroll.edit')` on the three mutating endpoints would have silently locked HR out of editing payslips, dispatching them, and resolving queries — a functional regression, not just a cleanup. Added `0044_grant_payroll_edit_to_hr.py` to close this gap. Final grants verified directly against the DB after migrating:

```
payroll.view      -> hr, system_admin
payroll.view_own  -> employee, hr, manager__team_lead, system_admin
payroll.edit      -> hr, system_admin
```

Matches the target matrix exactly.

**Files changed:**
```
backend/apps/payroll/views/payslips.py                      — _is_payroll_admin() removed; 8 call sites → _has_perm();
                                                                 payroll.view_own gate added to PayslipQueryListView.post()
backend/apps/accounts/migrations/0044_grant_payroll_edit_to_hr.py            (NEW)
backend/apps/accounts/migrations/0045_remove_payroll_view_from_manager.py    (NEW)
```

### 2. Migration Graph Conflict — Resolved, and Explains Last Session's "Uninvestigated" Note

`makemigrations`/`migrate` were completely broken project-wide: "Conflicting migrations detected; multiple leaf nodes" across **both** `hrms` (`0014_carry_forward` vs `0015_merge_20260722_1100`) and `attendance` (`0016_attendance_import_log_task_id` vs `0016_seed_missing_clockout_email_template`). This is the same stray `hrms/migrations/0015_merge_20260722_1100.py` the 22/07 session flagged as "uninvestigated, not caused by this session" — now explained: `0015_merge_20260722_1100` is a legitimate auto-generated Django merge migration (from a `git pull origin demo` bringing in a diverged branch), it just never picked up `0014_carry_forward` as a third branch because that migration was created independently around the same time.

Verified both conflicts were genuinely safe to auto-merge (each pair touches entirely different fields/models, zero overlap) before running `makemigrations --merge --noinput`, which created two empty, no-op reconciliation migrations:
```
backend/apps/hrms/migrations/0016_merge_0014_carry_forward_0015_merge_20260722_1100.py   (NEW, empty)
backend/apps/attendance/migrations/0017_merge_20260723_1644.py                            (NEW, empty)
```

**Important discovery while doing this — read before touching migrations on this project again:** this backend's `.env` points at a **shared remote Postgres database** (Neon, `neondb`), not a local dev DB. Mid-investigation, found the hrms merge migration was *already marked applied* in that shared DB under the exact same filename — Django names simple two-branch merges deterministically, so another concurrent session hit the identical hrms conflict and had already pushed the identical fix through. Worse, for `attendance`, the DB had **two migrations applied that don't exist as files anywhere in this checkout or on any pushed branch**: `attendance.0017_merge_20260723_1558` and `attendance.0018_attendancecorrection_l1_actioned_at_and_more` (looks like real schema work — AttendanceCorrection L1/L2 fields — applied directly to the shared DB from someone else's local checkout, not yet committed anywhere).

Checked every branch on `origin` for those two files — not pushed anywhere, so there was nothing to pull. Confirmed with the user before proceeding: since both merge migrations are empty no-ops (no schema/data risk either way), migrated this checkout's own state now; the only follow-up cost is one more trivial merge migration whenever that other work is finally pushed and the two divergent `0017_` files for `attendance` need reconciling in git.

**Action needed from whoever owns that AttendanceCorrection work:** commit and push it — it currently only exists as applied database state, with no corresponding code anywhere in version control. If that database is reset or another merge migration is generated carelessly, that schema change has no source of truth to recover from.

### Pending

- **Get the AttendanceCorrection L1/L2 migration (`attendance.0018_attendancecorrection_l1_actioned_at_and_more` + its `0017_merge_20260723_1558`) committed and pushed** — currently only exists as applied state in the shared Neon DB, not in git anywhere. Next `makemigrations --merge` will need to reconcile two divergent `0017_` files for `attendance` once it lands.
- Frontend already expects `payroll.view_own` for My Payslips (per the 22/07 session) — no further frontend work needed for this session's changes.
- Everything else listed as Pending in the 2026-07-22 entries above is still outstanding.

---

## Session Log — 2026-07-20
**Author: SandalaNithin**

### Bug Fixes Shipped

**1. `_auto_assign_managers()` — wrong HR role name in branch fallback lookup**
- Root cause: when a branch has no `hr` FK set, the fallback query looked up `role__name='hr'` — but the actual role name in this codebase is `hr_admin`, so the fallback silently matched nobody
- Fix: `role__name='hr_admin'`
- File: `backend/apps/accounts/views.py` (`_auto_assign_managers`)

### Features Shipped

**2. Onboarding approval — HR can assign a specific assessment, not just defaults**
- `OnboardingApprovalView.post()` now reads `assessment_id` from the approval request body
- If that assessment isn't already in the default/active list, it's fetched and appended so HR can hand-pick a non-default assessment at approval time instead of only the global defaults
- File: `backend/apps/accounts/views.py`

**3. Assessment emails now deep-link to the assessment page**
- `assessments_portal_url = f'{portal_url}/onboarding/assessments'` computed once and substituted for the plain `portal_url` in both the onboarding-approved email and the assessment-assigned email whenever the candidate has pending assessments
- Previously both emails linked to the bare portal root, leaving the candidate to find the assessments page themselves after logging in
- File: `backend/apps/accounts/views.py`

---

## Session Log — 2026-07-22
**Author: SandalaNithin**

### Features Shipped

**1. Move HR attendance approval into Leave Management**

For the `hr` / `hr_admin` role only: attendance sign-off moves out of the standalone Approvals page and into a new "Attendance Approvals" tab inside Leave Management. Manager and `system_admin` are unaffected — they keep attendance approval on the existing Approvals page.

- `frontend/app/dashboard/approvals/page.tsx`
  - `canApproveAttendance` now excludes HR (`&& !isHR`) so that tab no longer renders there for this role
  - HR visiting `/dashboard/approvals` directly is redirected to `/dashboard/leave` (`useEffect` + `router.replace`; page renders `null` for HR)
- `frontend/app/dashboard/leave/_client.tsx`
  - New `"attendance"` tab added to `TabId`, gated on `isHR && useAnyPermission("payroll.view", "payroll.approve")`
  - Reuses the existing `AttendanceApprovalTab` component from `../approvals/_components/`
- `frontend/lib/navConfig.ts`
  - Approvals nav entry gets `excludeRoles: ["hr", "hr_admin"]` so it disappears from the sidebar for this role

---

## Session Log — 2026-07-27
**Author: SandalaNithin**

### Changes Shipped

**1. Frontend dependency additions — `zod`**
- `zod ^4.4.3` added to `frontend/package.json` dependencies; `caniuse-lite ^1.0.30001806` pinned as an explicit (previously transitive) dependency; `package-lock.json` regenerated to match
- No file in the repo imports `zod` yet — this is a dependency-only change, ahead of upcoming validation work
- Note: the commit was titled "ui changes" but the diff only touches `package.json` / `package-lock.json` — no UI code changed in this commit

### Pending

- Wire up `zod` schemas — not started, dependency only
- Everything listed as Pending in earlier session-log entries above is still outstanding

---


## Session Log — 2026-07-27
**Author: Teerdaveni**

### Features Shipped

**1. Enterprise Redis Caching — Master/Config Data**

Before touching any code, analyzed what already existed: `core/cache_service.py` already had a complete cache-aside layer (`CacheTTL` constants + 9 `*CacheService` classes: LeavePolicy, Holiday, WeeklyOff, ApprovalWorkflow, AttendanceSettings, Branch, Department, Designation, FinancialYear) with `post_save`/`post_delete` signal-based invalidation across 5 `signals.py` files. The gap: several settings/admin **read** endpoints bypassed these services entirely and hit Postgres directly. Wired the existing services into their real read paths instead of duplicating cache logic anywhere.

**Wired to existing/extended cache services:**

| Endpoint | Now reads via | TTL |
|---|---|---|
| `GET /api/leave/policy/` (`LeavePolicyView.get()`) | new `LeavePolicyCacheService.get_all()` | 300s |
| `GET /api/leave/holidays/` (`HolidayListCreateView.get()`) | new `HolidayCacheService.get_list_for_year()`, year-scoped; remaining filters (month/type/optional/branch) applied in Python on the cached list | 600s |
| `GET /api/attendance/settings/` (`AttendanceSettingsAPIView.get()`) | existing `AttendanceSettingsCacheService.get()` (select_related widened to match the write-path service, avoiding N+1 on cache-hit) | 6h (unchanged) |
| `GET /api/settings/approval-rules/` (`ApprovalWorkflowRuleView.get()`) | existing `ApprovalWorkflowCacheService.get_rule()` per workflow type | 6h (unchanged) |
| `GET /api/settings/company/` (`CompanyRetrieveUpdateView.get()`) | new `CompanyCacheService` (singleton — Company has no `company_id`, this app is single-tenant) | 600s |

New cache-invalidation wiring: `CompanyCacheService.invalidate()` added to the existing `on_company_change` signal in `apps/accounts/signals.py`. `LeavePolicyCacheService.invalidate()` and `HolidayCacheService.invalidate_year()`/`invalidate_branch()` extended to also clear the new list-level keys — no signal files needed new receivers for these.

**Deliberately left unwired (investigated in depth, not an oversight):**
- Branch/Department/Designation list endpoints — paginated, filterable (status/state/department/is_active), and combine live per-request employee-count aggregates that must stay fresh. The existing `*CacheService.get_all()` methods cache an unfiltered "all active" list that doesn't match these views' real semantics (e.g. the Designation list shows inactive rows too) — wiring them in would have silently changed API behavior, which was explicitly out of scope.
- WeeklyDayPolicy admin CRUD list — paginated/searchable, low-frequency; the actually-hot read (the *effective* weekly-off set used by attendance/leave calculations) was already fully cached via `WeeklyOffCacheService.get()`.
- Detail-by-id views (Holiday/WeeklyDayPolicy/Department/Designation/Branch) — single indexed PK lookups, already fast, low volume.

**Verified against the real dev DB** (all writes wrapped in a rolled-back transaction/savepoint, nothing persisted): cache miss → DB → cache; cache hit → 0 queries; write → signal fires → cache invalidated → next read re-misses with fresh data; simulated Redis outage (mocked `cache.get`/`cache.set` to raise) → warning logged, DB fallback still serves correct data, no exception reaches the caller; Holiday filter-output parity (old ORM query vs new cache+Python-filter path) verified identical across 7 query-param combinations plus the no-year fallback.

**Files changed:**
```
backend/core/cache_service.py                    — CompanyCacheService added; LeavePolicyCacheService.get_all() added;
                                                     HolidayCacheService.get_list_for_year() added; AttendanceSettingsCacheService
                                                     select_related widened (late_mark_rules, absence_alert, updated_by);
                                                     new CacheTTL.COMPANY / LEAVE_POLICY_LIST / HOLIDAY_LIST constants
backend/apps/hrms/views/leave.py                 — LeavePolicyView.get() reads via LeavePolicyCacheService.get_all()
backend/apps/hrms/views/holidays.py              — HolidayListCreateView.get() reads via HolidayCacheService + Python filters
backend/apps/attendance/views/settings_view.py   — AttendanceSettingsAPIView.get() reads via AttendanceSettingsCacheService
backend/apps/accounts/views.py                   — ApprovalWorkflowRuleView.get(), CompanyRetrieveUpdateView.get() read via cache
backend/apps/accounts/signals.py                 — on_company_change also invalidates CompanyCacheService
```

### Bug Fixes Shipped

**2. Document Center — XLSX/Excel preview crash**

UI showed: `Could not render spreadsheet — Cannot read properties of undefined (reading 'read')`. Confirmed upload/download and the API itself were not the problem — `GET /api/documents/{id}/?t=...` (`DocumentDetailView._stream_file`) correctly streams raw XLSX bytes with the right content-type. Two separate bugs found and fixed, in sequence, in the same component:

**Bug A — `XLSX.read` undefined.** `frontend/app/dashboard/documents/_components/DocPreviewBody.tsx` did:
```ts
const XLSX = (await import("xlsx")).default;
```
SheetJS's `xlsx` package (v0.18.5, already installed — no new library added) has **no `default` export** in either its CJS (`xlsx.js`) or ESM (`xlsx.mjs`) build — confirmed by inspecting both files directly (only named exports: `read`, `utils`, etc.). Next.js/Turbopack resolves the dynamic `import("xlsx")` to the ESM build, so `.default` was genuinely `undefined`, and calling `.read()` on it threw exactly the reported error.
- Fix: `const XLSX = await import("xlsx");` — use the namespace object directly.

**Bug B — empty worksheet crash.** Fixing Bug A revealed a second, different error: `Cannot read properties of undefined (reading 'indexOf')`, thrown inside SheetJS's internal `decode_range()` (called by `sheet_to_html()`) whenever a worksheet has no `!ref` range — i.e. is completely empty. Reproduced against a real uploaded document (downloaded via the actual API and parsed with the exact same SheetJS ESM build used in the browser): the file has 3 sheets — Sheet1 has data (`!ref: "A1:AV61"`), Sheet2 and Sheet3 are empty (`!ref: undefined`). The old code called `sheet_to_html()` on every sheet unconditionally inside one `.map()`, so the first empty sheet crashed the entire preview — including Sheet1, which would have rendered fine alone.
- Fix: skip `sheet_to_html()` for any sheet with no `!ref` and render a "This sheet is empty." placeholder instead.

Both fixes verified end-to-end against the real downloaded file (not synthetic test data) — all 3 sheets now render without throwing. `tsc --noEmit` clean across the project. Diff is 2 small edits in 1 file — upload, download, and PDF/image/DOCX/CSV preview, auth, permissions, and Cloudinary storage were all left untouched.

**Files changed:**
```
frontend/app/dashboard/documents/_components/DocPreviewBody.tsx   — XlsxPreview: namespace import instead of .default;
                                                                      empty-sheet guard before sheet_to_html()
```

### Debugging Done (not yet resolved)

**3. Next.js dev server — login timeout / stale build cache**

Investigated a `/login` page failure: a React Client Manifest error (`global-error.js#default` not found in the bundler manifest) plus an 80–100s first-compile time for the route, followed by a `timeout of 15000ms exceeded` on the login POST with a `400 Bad Request` in the Django log around the same moment. Isolated the cause by testing each layer directly: `curl` straight to Django (`:8000/api/login/`) and through the Next.js rewrite proxy (`:3000/api/login/`) both succeeded in under 2s with the same credentials that failed in the browser — so the login view, the credentials, and the proxy rewrite are all correct. The symptoms (missing manifest entry + abnormally slow first compile) point to a stale/corrupted `.next` dev build cache, not a code bug: a form submit sent while the route is still mid-compile can go out malformed, get a fast `400` from `LoginSerializer` validation, while the browser's own independent 15s axios timeout fires around the same time.
- **Not yet fixed.** Recommended fix: stop the dev server, delete `frontend/.next`, restart clean. Proposed to the user but not actioned — session moved to the Document Center task before confirming.

### Pending

- Next.js dev server `.next` cache clear for the login-page slow-compile/timeout issue (diagnosed above, action pending confirmation)
- Everything listed as Pending in the 2026-07-23 entry above is still outstanding

---

## Session Log — 2026-07-28
**Author: Teerdaveni**

### Features Shipped

**1. Employee "My Corrections" — Attendance Correction / Un-Punch Status API**

Before writing anything, searched the whole attendance module for an existing employee-facing "view my own correction requests" API — confirmed none existed. `POST /api/attendance/correction/` (`AttendanceCorrectionView`) only submits, no `GET`. `GET /api/attendance/corrections/` (`HRCorrectionListView`) requires `attendance.view` permission and is scoped to the manager/HR **approval queue** (`_approval_scope_filter`) — a plain employee gets `403`, and even if permitted it's not "my own requests." No duplicate API created.

**New endpoint:** `GET /api/attendance/corrections/my/` — `IsAuthenticated` only (no special permission; always scoped to the caller). Filters: `status` (`pending`/`l2_pending`/`approved`/`rejected`), `date_from`, `date_to`; standard `?page=`/`?page_size=` pagination envelope; newest-first.

Reused the existing shared row-builder (`_build_row()` in `services_hr_corrections.py`, already used by the HR list) rather than writing a second one — extended it with two new fields, `original_in`/`original_out` (the employee's actual punch times that day, derived from the existing `AttendanceRecord.first_punch_in`/`last_punch_out`, same lookup pattern already used in `_write_correction_audit`), so the response shows original-vs-requested times side by side. This addition is backward compatible — existing HR-list consumers just get two extra keys.

**Files changed:**
```
backend/apps/attendance/services_hr_corrections.py     — list_my_corrections() added; _build_row() extended with
                                                           original_in/original_out (from AttendanceRecord)
backend/apps/attendance/serializers_my_attendance.py    — MyCorrectionsFilterSerializer added (status/date_from/date_to)
backend/apps/attendance/serializers_hr.py               — original_in/original_out added to CorrectionRowSerializer
backend/apps/attendance/views/my_attendance.py          — MyCorrectionsListView added
backend/apps/attendance/views/__init__.py               — export added
backend/apps/attendance/urls.py                         — path('corrections/my/', ...) added
```

**Verified** (real dev DB, wrapped in a rolled-back transaction/savepoint, nothing persisted): real HTTP request through the actual view/URL → `200` with correct pagination envelope; a genuine `role=employee` user gets `200` here and (unchanged) `403` on the HR-wide `/corrections/` endpoint — permission boundary intact; `status`/`date_from`/`date_to` filters all checked against real data; **isolation check** — a different employee cannot see another employee's correction rows; `original_in`/`original_out` populated correctly. `python manage.py check` clean.

**Known gap, flagged not silently dropped:** the spec asked for a `Cancelled` status. This model only has `pending`/`l2_pending`/`approved`/`rejected` — there is no cancel action anywhere in the attendance-correction flow (unlike Leave Requests, which do support cancellation). Did not add one — that's a distinct write-path feature, out of scope for exposing an existing read.

**Frontend prompt given:** endpoint/params/response shape/field meanings/status meanings + suggested UI (new "Corrections" tab on My Attendance, status badges, filter bar) — not yet implemented.

### Debugging Done (not yet resolved)

**2. New endpoint 404'd in the running backend — stale Daphne process, not a code bug**

After implementing the above, `GET /api/attendance/corrections/my/` returned `404` both from a LAN device (`192.168.0.154`) and from a direct local `curl` — ruling out a network/CORS issue. Checked the actual running process (`tasklist` + `wmic process where ProcessId=... get CommandLine`): the backend on port 8000 is running via **`daphne -b 0.0.0.0 -p 8000 config.asgi:application`**, not `manage.py runserver`. Daphne loads the ASGI app and URL config once at startup and does **not** auto-reload on file changes, so the live process is still serving the route table from before `urls.py` was edited — the code on disk is correct (confirmed again via `manage.py check` and an `APIRequestFactory`/`reverse()` test that resolves the new route fine), it just hasn't been picked up by the running server yet.
- **Not yet fixed.** Needs the Daphne process restarted to pick up the new route. Flagged to the user before acting, since it's bound to `0.0.0.0:8000` and reachable from at least one other LAN device that may be actively using it right now (restarting will cause a brief outage for that device too) — action pending confirmation.

### Continued from 2026-07-27 — Next.js dev server instability (still unresolved)

Picked back up the `.next` stale-cache issue from the prior session: stopped the dev server, deleted `frontend/.next`, restarted clean — `/login` compiled fast (`200` in 4.5s, was `500` in 36.7s) and a real login POST succeeded end-to-end. However, the dev server then **crashed silently** (no stack trace, no error in its own log, process just disappeared — confirmed via `tasklist` showing zero matching processes and port 3000 in `TIME_WAIT`) after serving a batch of requests successfully. Restarted a second time; it crashed again the same way, this time surfacing `Cannot find module '@swc/helpers-<hash>/_/_interop_require_default'` in the browser before dying — a content-hashed helper path baked into a Turbopack chunk that no longer resolves, which is a stronger signal than plain cache staleness. Both restarts served 20-30+ successful requests before dying, not immediately, which doesn't match a simple one-off corrupted-cache theory either.
- **Not yet fixed / not yet root-caused.** This increasingly looks like a genuine Next.js 16.2.9 + Turbopack (preview/JIT engine, per its own startup warning) stability bug under this Windows dev setup, rather than something fixable purely by clearing `.next`. A background monitor was set up to catch the next crash with full output but the session moved to the attendance-corrections task before it could be root-caused further.
- **Next step when picked back up:** consider running without Turbopack (plain `next dev` webpack fallback) as a diagnostic to confirm whether Turbopack itself is the crashing component, and capture stderr more reliably (the crashes produce no visible error text at all currently).

### Pending

- Restart the Daphne backend process so `/api/attendance/corrections/my/` (and any other code shipped after Daphne last started) actually goes live — action pending confirmation (see above).
- Next.js dev server repeatedly crashing silently after a period of normal operation — not root-caused yet, worse than the simple stale-cache issue first diagnosed on 2026-07-27 (see above).
- Frontend implementation of the "My Corrections" tab (prompt given, not yet built).
- Everything listed as Pending in the 2026-07-27 entry above is still outstanding.

---

## Session Log — 2026-08-04
**Author: Swetha**

### Investigation (informational, no code changed)

Full-codebase review answering three questions: cause of intermittent request timeouts, presence of security vulnerabilities, and whether the app can support 2000+ concurrent users. Delivered as a structured report only (not persisted to a file) covering: synchronous email sends in the request path instead of Celery, N+1 queries in payroll processing, missing indexes (`User.branch`, `PayrollCycle.status`, `LeaveRequest` composite), unencrypted PAN/Aadhaar/bank fields, a mobile-logout token-blacklist gap, a `proxy.ts` permission-check bypass via the unsigned `royal_hrms_user` cookie, single-VM deployment with no APM/monitoring, and Gunicorn/Celery worker config being entirely outside this repo (unknown from code alone).

### Features Shipped

**1. Add Employee — manual HR / Reporting Manager selection**

`EmployeeStatsView.post()` (the actual Add Employee creation handler — note: this method lives inside a class literally named `EmployeeStatsView`, not `EmployeeListCreateView`; pre-existing naming oddity, not touched) now accepts optional `hr_id` and `reporting_manager_id` in the request body. Both are validated (must be an active user; `reporting_manager_id` rejected if the new employee's role has `can_manage_team=True`) and applied to the new user **before** the existing `_auto_assign_managers()` call, which only fills in fields left unset — so an explicit selection always wins over the automatic guess, and omitting either field preserves the original auto-assign behavior exactly as before.

**2. Manager dropdown (`GET /api/employees/managers/`) — added `department` filter**

Previously required `branch` only. Now accepts `department` and/or `branch` (at least one required). Verified against real data: this org has one manager per department **per branch** (e.g. 3 separate "Engineering Manager" accounts across Hyderabad/Mumbai/TASK) — `department` alone correctly returns all of them company-wide; the Add Employee form needs to send **both** `department` and `branch` together to narrow to the one manager for that specific branch.

**3. HR dropdown (`GET /api/employees/hrs/`) — two real bugs fixed**
- `branch` is now actually required (was silently optional — omitting it returned every HR company-wide).
- Removed a fallback that unconditionally inserted the requesting user into results if they held the HR permission, even when their own branch didn't match the one queried (could leak an unrelated branch's HR into the dropdown).
- Excluded `system_admin` role explicitly — that role is seeded with every permission including `onboarding.approve` (the permission used to identify "who is HR"), so any system admin whose branch happened to match was incorrectly appearing as an HR option. Verified: `EMP002` no longer appears in Hyderabad's HR list.

**4. Department dropdown (`GET /api/departments/`) — added `branch` filter**

`Department` has no branch field of its own (company-wide master list) — the filter derives "departments at this branch" from which departments actually have an active employee there. Verified per-branch: Hyderabad has 6 (incl. Customer Support), Mumbai/TASK have 5 (no Customer Support — nobody's there yet). "Management" won't appear for any branch — it currently has zero employees anywhere, not a bug.

### Bug Fixes Shipped

**5. Root-caused and fixed: wrong HR auto-assigned for the Hyderabad branch**

`User.branch` is free-text with no validation against the master `Branch` table. Some employees had `branch = "Hyderabad HQ"`, which doesn't match the real Branch record `"Hyderabad"` — silently broke HR auto-assignment (which compares exact strings), falling back to assigning whoever created the employee as HR instead. Fix: Add Employee's `branch` is now validated against the active `Branch` table (rejects unrecognized values with a clear 400) and the stored value is canonicalized to `Branch.branch_name`. Same class of fix applied to `department` (see #6) after finding an identical orphaned-string case there too.

**6. Add Employee — added `department` validation + canonicalization**, mirroring #5. Found one existing employee (`EMP002`) with `department = "IT"`, which isn't a real Department row — same bug class as "Hyderabad HQ". Not yet cleaned up in data (flagged below, decision pending).

### Data fixes applied directly (not code — read-only-verified before each write, confirmed with the user first)

```
Branch(branch_name='Hyderabad').hr = hr.hyderabad@example.com (RSS00097)   — was unset
User(employee_id='EMP002').branch: 'Hyderabad HQ' -> 'Hyderabad'           — normalized, confirmed low-impact (system_admin, hr was already None)
Branch.objects.create(branch_name='Mumbai', branch_code='MUM',
                       state=Maharashtra, city=Mumbai, hr=RSS00049)         — 9 employees (3 managers + 1 HR) were using
                                                                              branch="Mumbai" with no matching Branch row at all
```

### Known issues found but not yet fixed (flagged to user, awaiting decision)

- `EMP002`'s `department="IT"` still orphaned (same class as the branch issue) — decision pending.
- `TASK` branch has no HR assigned (`Branch.hr` unset) — flagged, not yet actioned.
- `_auto_assign_managers()`'s reporting-manager fallback (used when no `Department.manager` is set — true for all 7 departments currently) picks "first active manager in that branch by database id," without filtering by department at all. Currently resolves correctly for Hyderabad+Engineering only by luck of id ordering — a branch with managers from multiple departments could silently get the wrong one assigned. Not fixed, since not explicitly requested this session.
- **Operational risk found**: the backend on port 8000 is served by a long-running Daphne process (confirmed via `wmic`, started 2026-08-04 11:02) which — per the 2026-07-28 entry above — does **not auto-reload** on code changes. None of today's `views.py` edits take effect until this process is restarted. Not restarted without confirmation, since it's bound to `0.0.0.0` and may be reachable by other devices on the network right now (same precedent as 2026-07-28).

### Files changed
```
backend/apps/accounts/views.py
  - EmployeeStatsView.post()      — hr_id/reporting_manager_id accepted + validated;
                                     branch validated against Branch table + canonicalized;
                                     department validated against Department table + canonicalized
  - HRListView.get()               — branch now required; system_admin excluded;
                                     removed cross-branch requester-insertion fallback
  - ManagerListView.get()          — department filter added (alongside existing branch filter)
  - DepartmentListCreateView.get() — branch filter added (derived from employee data)
```

### Frontend prompt given (not implemented this session — explicitly backend-only per instruction)

Full cascading-dropdown contract specified for Add Employee: Branch → Department (`?branch=`) → Designation (`?department=<id>`, unchanged/pre-existing) → Reporting Manager (`?department=&branch=` combined) and Branch → HR (`?branch=`). Response shape, param types (name string vs ID), pagination differences between endpoints, and field-clearing rules all specified. Not yet built.

### Pending

- Restart the Daphne backend process so today's changes actually go live — action pending confirmation (see above).
- Frontend implementation of the 4 cascading Add Employee dropdowns (prompt given above).
- Decide on `EMP002`'s orphaned `department="IT"` value.
- Decide on `TASK` branch's missing HR assignment.

---

## Session Log — 2026-08-03
**Author: Teerdaveni**

Two separate bodies of work this session: (1) a full Weekly Off Pattern + per-employee assignment feature, and (2) a multi-phase production performance/scalability/security hardening pass driven by a detailed team spec, executed phase-by-phase with explicit approval gates between phases.

### Features Shipped

**1. Weekly Off Pattern + Employee Weekly Off Assignment (full feature)**

Reusable named weekly-off patterns (`WeeklyDayPolicy`, already partially existing) extended with per-employee assignment and effective-dating, plus a single centralized resolver used everywhere weekly-off status is needed — replacing what had been ad hoc per-module logic.

- New model `EmployeeWeeklyOffAssignment` (`apps/attendance/models.py`) — per-employee, per-policy, `effective_from`/`effective_to` (nullable = current), history preserved by closing out the prior row on reassignment rather than deleting it. Migration `attendance/0020_employeeweeklyoffassignment.py`.
- Centralized resolver added to the *existing* `core/cache_service.py::WeeklyOffCacheService` (two new methods, `get_effective()`/`get_effective_range()`) rather than a new service file — the single unambiguous priority order is: per-employee assignment → `WeeklyDayPolicy.is_default` → legacy `AttendanceSettings.weekly_off` → hardcoded Sat/Sun fallback. Verified byte-identical output to the pre-existing resolver for any org not using per-employee assignment (zero behavior change for the common case).
- Wired into every consumer that used to read weekly-off state independently: `AttendanceProcessorService._is_weekly_off()`, `AttendanceDashboardService` calendar generation, `services_absence.py` consecutive-absence counting, and `apps/hrms/views/leave.py` working-days calculation — all now go through the one resolver.
- New backend service functions in the *existing* `apps/attendance/services_hr.py` (a prior attempt to put this in a new service file was explicitly rejected — reused this file instead): `build_weekly_off_assignment_queryset()`, `bulk_assign_weekly_off()` (O(1)-query bulk close-out + supersede + `bulk_create`, resolves human-readable employee codes internally), `assign_weekly_off()`, `get_weekly_off_assignment_history()`.
- New endpoints: `GET/POST /api/attendance/weekly-off-assignments/`, `POST /api/attendance/weekly-off-assignments/bulk/`, `GET /api/attendance/weekly-off-assignments/<employee_id>/history/`.
- `assigned_employee_count` annotation added to the existing `WeeklyDayPolicy` list/detail serializers (one extra `Count(..., filter=..., distinct=True)` per page, no N+1) and a delete-safety check (blocks deleting an in-use or default pattern, 409 with a clear message).
- Frontend: new `WeeklyOffAssignmentTab.tsx` (5th tab under Attendance & Time), and `WeeklyOffPatternsCard.tsx` replacing the old "Weekly Off Days" 7-day-toggle card in `AttendanceSettings.tsx` — confirmed safe to remove only after verifying a default `WeeklyDayPolicy` already exists as the live fallback.

**2. Weekly Off Patterns UI — cleanup, pagination, compact table**

Three follow-up passes on the same screen, each scoped tightly to what was asked:
- Hid internal `WD-xxx` policy codes from the UI; added "Used by N employees" via the annotation above.
- Added compact pagination (max 3 patterns/page) reusing the existing backend `core/pagination.py` — no new pagination API.
- Replaced individual card rows with a compact `<table>` (reusing the app's existing `.table-wrap`/table CSS, ~55-65px rows), abbreviated day labels ("Mon • Sat • Sun"), icon-only Edit/Delete buttons. Verified via `tsc --noEmit`/`eslint` clean and `git status` confirming the diff was isolated to `WeeklyOffPatternsCard.tsx` each time.

**Known, honestly-flagged gap:** "Alternate Saturday" and "Rotational 4-week" pattern types shown in the original UI mockups are **not** functionally supported by the current `WeeklyDayPolicy` schema (only 7 flat day-type fields, no week-of-month/cycle dimension) — flagged to the user as an existing limitation rather than silently built incomplete or faked.

---

### Production Hardening — Phased Backend Optimization

Driven by a detailed team spec (performance/scalability/security for 2,000+ employees). Executed in the spec's own mandated order, one phase at a time, with an explicit approval gate before starting the next phase. Every phase's testing used the same discipline: real dev-DB data wrapped in `transaction.savepoint()`/`savepoint_rollback()` so nothing was ever persisted by a verification run.

**Phase 0 — Architecture analysis (read-only, no code changes)**

Six parallel research passes across email/Celery/Redis config, payroll/attendance processing, DB indexes, auth/JWT, frontend authorization, sensitive-data storage, and dependency versions. Key confirmed findings that shaped every later phase:
- Announcement bulk-email and one assessment-assignment path were doing synchronous, unbounded SMTP sends in the request path.
- Payroll processing was fully synchronous, ~5-6 queries per employee (~12,000 queries at 2,000 employees), one giant transaction, no job-progress model.
- `LogoutView` only reads the refresh token from a cookie (no header/body fallback) — Flutter/mobile logout never blacklists its refresh token.
- Frontend `proxy.ts` trusts a plain, JS-writable cookie for route/permission gating with zero JWT signature verification.
- Bank account fields (`account_number`, `ifsc_code`, etc.) are stored unencrypted but aren't used in search/export/import, so encrypting them looks safe without a risky migration (not yet implemented — flagged for a controlled follow-up, not attempted this session).
- `next` 16.2.9 has known high-severity CVEs fixed in 16.2.12; `xlsx` has 2 high CVEs with no compliant npm-published fix.

**Phase 1(a) — Announcement bulk email → Celery**
- New `apps/announcements/tasks.py` (`send_announcement_email_task`) — the only new backend file this phase, since no `tasks.py` existed for this app. Recipients batched into ≤90-per-message BCC groups (avoids provider recipient-cap failures at company-wide scale) sent over one SMTP connection.
- `AnnouncementListCreateView.post()` now saves the announcement and queues via `transaction.on_commit(...)` instead of sending inline; queuing failure is logged, not raised, so a broker outage never blocks the already-saved announcement.
- Retries only cover the pre-send setup phase; once a batch has been attempted, failures are logged and skipped rather than retried, so a task retry can never double-send to a batch that already went out.

**Phase 1(b) — Recruitment assessment bulk-assign → Celery + N+1 fix**
- `AssignAssessmentView`'s department/company-wide branch: replaced a per-employee `get_or_create()` loop with one existence-check query + `bulk_create(..., ignore_conflicts=True)`. Measured 26-employee bulk assign: **12 queries after vs. an estimated ~52+ before** (re-running the identical assign, all-already-assigned: 9 queries).
- New `apps/assessments/tasks.py` (`send_assessment_assignment_emails_task`) — reused by all 4 assign paths (single-candidate, single-employee, department, company-wide), calling the existing `_send_assessment_email()` helper rather than duplicating email logic.

**Phase 1(c) — remaining `threading.Thread` → Celery**
- Found and converted the last 4 unmanaged background threads in the codebase: leave-lifecycle email (`apps/notifications/signals.py`), interview-scheduled + referral-submission emails (`apps/recruitment/views.py`), and onboarding-submitted HR notification (`apps/accounts/views.py`).
- Three new task files (`apps/notifications/tasks.py`, `apps/recruitment/tasks.py`, `apps/accounts/tasks.py`) — each a thin dispatcher calling existing, unmodified email-sending functions. Confirmed via repo-wide grep: zero `threading.Thread` remains anywhere in the backend.

**Phase 2 — Payroll processing optimization**
- `ProcessPayrollView`'s per-employee loop (salary config, branch, structure components, statutory config, adjustments — all queried per employee) rewritten as bulk-fetch + per-distinct-structure/state caching + `bulk_create`/`bulk_update` instead of `update_or_create` per employee. All extracted into module-level functions inside the *existing* `apps/payroll/views/cycles.py` (a new `services_processing.py` was drafted and explicitly rejected — moved into the existing file instead).
- Measured (N=23 real employees): **query count 138 → 14 (90% reduction)**; also fixed a previously-hidden extra N+1 (`salary_config.salary_structure` accessed without `select_related`).
- Idempotency: cycle claimed via one atomic `UPDATE ... WHERE status='attendance_approved'` (a real compare-and-swap, not a check-then-write) — two concurrent "Process Payroll" clicks can't both run the heavy loop.
- Rollback safety (found *during* verification, fixed before sign-off): an unexpected mid-write failure now reverts the cycle back to `attendance_approved` instead of leaving it wedged in `processing` forever, with zero partial payslip writes surviving.
- Deliberately **stayed synchronous** rather than moving to Celery: the frontend payroll wizard (`EarningsDeductionsStep.tsx`) reads `skipped` directly from the POST response with no polling mechanism — true fire-and-forget would have broken that screen without a frontend change, which was out of scope. The query-count fix was judged sufficient to keep it well within normal request timeouts.

**Phase 3 — Attendance reprocessing → Celery**
- `HRAttendanceReprocessView` now validates, queues `reprocess_attendance_task` (new, in the *existing* `apps/attendance/tasks.py`), and returns immediately — confirmed via repo-wide search that no frontend UI currently calls this endpoint, so the response-shape change (synchronous results → `{status: "queued", task_id}`) carries no UI risk.
- `reprocess_date()`'s per-employee audit-log write (`AttendanceAuditLog.objects.create()` per employee) batched into one `bulk_create()` — `AttendanceProcessorService` itself was left completely untouched, per the explicit "call it, don't rewrite it" constraint.
- Verified per-employee failure isolation still works, audit-log write failures are swallowed without affecting the reprocess result, and re-running the same date never duplicates `AttendanceRecord` rows (existing `unique_together`/`update_or_create` protection, unchanged).

**Phase 4 — Database index review**
- Four parallel research passes cross-checked `Meta.indexes`/migrations against real ORM query call sites (not guesswork) across User, AttendanceRecord/Punch/Correction, LeaveRequest, EmployeePayslip, PayrollCycle, Notification, Announcement, CandidateAssignment, and every audit-log-style model in the codebase.
- 11 new indexes added across 7 apps (one migration per app, index-only, no data/field changes): `User(branch,is_active)`, `User(onboarding_status,is_active)`, `AuditLog(module,created_at)`, `AttendanceCorrection(status)`, `LeaveRequest(employee,status,start_date,end_date)`, `PayrollCycle(status)`, `PayrollCycle(cycle_start,cycle_end)`, `Notification(user,is_read)`, `Notification(user,created_at)`, `Announcement(is_pinned,created_at)`, `CandidateAssignment(employee,status)` + `(candidate,status)`.
- Several *candidate* indexes were deliberately **not** added, with reasons recorded (e.g. `AttendancePunch`'s dominant `punched_at__date=X` lookup would need a Postgres expression index precisely matching Django's timezone-sensitive `__date` SQL translation — judged higher-risk than this phase's mandate; `CarryForwardLog`'s unindexed guard query stays fine since that table realistically never exceeds a few hundred rows).
- Verified with real `EXPLAIN (ANALYZE, BUFFERS)` before/after using synthetic bulk data generated and rolled back inside a transaction (real dev-DB tables are far too small today for Postgres to ever choose an index over a seq scan). Measured, not estimated: notification list query **5.82ms → 0.06ms**; unread-count bell-poll **0.97ms → 0.04ms**; leave-overlap check on a 5,000-row single-employee history **0.66ms → 0.25ms**. One honest nuance recorded rather than hidden: for one specific skewed-data query shape, the planner's choice between two new indexes was measurably worse than before — reported as-is, not smoothed over.

### Files Changed (hardening phases — high-level; see phase notes above for detail)

```
backend/apps/announcements/views.py, tasks.py (new)
backend/apps/assessments/views/admin.py, tasks.py (new)
backend/apps/notifications/signals.py, tasks.py (new)
backend/apps/recruitment/views.py, tasks.py (new)
backend/apps/accounts/views.py, tasks.py (new)
backend/apps/payroll/views/cycles.py
backend/apps/attendance/views/hr_attendance.py, services_hr.py, tasks.py
backend/apps/accounts/models.py + migrations/0048_phase4_index_review.py
backend/apps/attendance/models.py + migrations/0021_phase4_index_review.py
backend/apps/hrms/models.py + migrations/0018_phase4_index_review.py
backend/apps/payroll/models.py + migrations/0008_phase4_index_review.py
backend/apps/notifications/models.py + migrations/0002_phase4_index_review.py
backend/apps/announcements/models.py + migrations/0002_phase4_index_review.py
backend/apps/assessments/models.py + migrations/0011_phase4_index_review.py
```

### Pending

- Hardening spec Phases 5–15 not yet started: Redis/Celery production-safety validation (fail-safe when `REDIS_URL` is unset), mobile logout refresh-token-blacklist fix, frontend `proxy.ts` JWT-verification fix, attendance CSV upload MIME/header validation, bank-detail field encryption (analysis done in Phase 0, migration not attempted), Gunicorn/ASGI/DB-connection review, monitoring, dependency security fixes (`next` → 16.2.12, `xlsx` CVE decision), and load testing.
- Weekly Off "Alternate Saturday"/"Rotational 4-week" pattern types (see above) — schema doesn't support them yet; no decision made on building this.
- Everything listed as Pending in the 2026-07-28 entry above is still outstanding.

---

## Session Log — 2026-08-05
**Author: Swetha**

Reactive bug-fixing session — each item below was reported live (via browser Network tab / server logs) while exercising the app, fixed, then the next one surfaced. Two of the six are schema-drift issues distinct from anything in prior sessions' hardening work; worth reading if you hit a mysterious "column does not exist" or "not-null constraint" error anywhere else.

### Bug Fixes Shipped

**1. Add Employee — `POST /api/employees/` returned 405**
- Root cause: the codebase has **two** `class EmployeeStatsView(APIView):` definitions in `views.py` — Python silently keeps only the second, so the first is dead code. The employee-creation `post()` method (real logic: validation, `User.objects.create_user`, auto-assign, welcome email) had been pasted into that dead first copy instead of into `EmployeeListCreateView`, which is what `POST /api/employees/` actually routes to — so that view had no `post()` at all.
- Fix: moved `post()` into `EmployeeListCreateView`; deleted the dead duplicate `EmployeeStatsView` shell (its `get()` was already fully superseded by the second, real definition).
- File: `backend/apps/accounts/views.py`

**2. Add Employee modal — `GET /api/employees/hrs/` returned 400**
- Root cause: `HRListView` requires `?branch=`, but the HR dropdown's `useFetch` call fell back to hitting the endpoint with no query string at all when `form.branch` was still empty (e.g. before a branch is picked, or for unrestricted/system_admin users) — a pre-existing "falls back to unfiltered list" comment that doesn't match what the backend actually supports.
- Fix: gated the fetch the same way the Manager dropdown right above it already does — `useFetch(form.branch ? ... : null)`, so it simply doesn't fire until a branch is selected.
- File: `frontend/app/dashboard/employees/_components/AddEmployeeModal.tsx`

**3. Referral submission — `POST /api/recruitment/referrals/` returned 500**
- Root cause: `hrms_candidates.meeting_link` is a **NOT NULL** column with no default and **no corresponding Django model field at all** — it (and a second, nullable `interview_time` column with one real value on an old row) exist in the live DB but were never part of any migration. Classic schema drift: added directly against the DB at some point for a feature that never shipped, then abandoned. Blocked every `Candidate` insert (referrals, direct add, bulk import).
- Fix: `ALTER TABLE hrms_candidates ALTER COLUMN meeting_link DROP NOT NULL` — applied directly (not via `manage.py migrate`, since the migration graph was broken at the time — see #5). Added `backend/apps/recruitment/migrations/0012_fix_meeting_link_not_null.py` so the fix is tracked in version control; it's a no-op if it ever actually runs. `interview_time` left alone (nullable, not breaking anything, explicitly out of scope).

**4. Referral submission — succeeded but the frontend still timed out (axios 15s)**
- Root cause (the real one, took several passes): `Task.apply_async()`/`.delay()` — even with a message broker that's up — implicitly subscribes to a Redis pub/sub channel for the task's result (`on_task_call()` → `result_consumer.consume_from()`) **unless `ignore_result=True` is passed**, regardless of whether anything ever reads that result. When Redis was unreachable, that subscription retried **up to 20 times** against the Redis *result backend* — a completely separate retry loop from anything broker-related, which is why tuning broker settings first (`CELERY_BROKER_TRANSPORT_OPTIONS` socket timeouts, `CELERY_BROKER_CONNECTION_MAX_RETRIES`) didn't fix it alone.
- Confirmed via repo-wide grep that `AsyncResult` (Celery's actual result-lookup API) is **never used anywhere** in this codebase — every "task status" feature (e.g. attendance import progress) is implemented by having the task write progress into its own DB row, not by querying Celery's result backend. So `ignore_result=True` is safe everywhere `.delay()` is called here.
- Fixed **all 7** fire-and-forget Celery dispatch call sites found repo-wide, not just the one that was reported — same `apply_async(..., retry=False, ignore_result=True)` pattern applied to each (two of them return/store the task's `.id` for display/audit purposes only, which still works fine under `ignore_result=True` since the id is generated locally, independent of the broker publish or result backend):
  - `backend/apps/recruitment/views.py` — referral-submission email, interview-scheduled email
  - `backend/apps/announcements/views.py` — announcement email
  - `backend/apps/accounts/views.py` — onboarding-submitted HR notification
  - `backend/apps/assessments/views/admin.py` — assessment assignment emails
  - `backend/apps/attendance/views/hr_attendance.py` — attendance reprocess (keeps `task_id` in the response)
  - `backend/apps/attendance/services_hr_ops.py` — attendance import (keeps `task.id` on `AttendanceImportLog`)
  - `backend/apps/notifications/signals.py` — leave lifecycle emails
- Also added, as defense-in-depth for the broker side specifically: `CELERY_BROKER_TRANSPORT_OPTIONS = {'socket_connect_timeout': 0.2, 'socket_timeout': 0.2}` and `CELERY_BROKER_CONNECTION_MAX_RETRIES = 1` in `backend/config/settings.py`. Note: Kombu treats `max_retries=0` as falsy and silently falls back to its own default retry count — `1` is the smallest value that actually takes effect.
- **Separately diagnosed, not fixed**: Redis itself (via WSL2 Ubuntu's `redis-server`, reachable at `localhost:6379` through Windows' localhost-forwarding) is intermittently unreachable from the Windows-side Python process — confirmed Redis is healthy and `PONG`s fine *inside* WSL the whole time; the flakiness is in the Windows↔WSL2 network relay. `wsl --shutdown` + restart did not fully resolve it (still ~50% connection failures right after). This is why the fixes above focus on bounding retry/timeout behavior rather than assuming Redis will reliably be reachable — that's a real, unresolved gap in this dev environment, separate from anything fixable in the Django/Celery config.

**5. Employee profile — `GET /api/employees/<id>/approval-matrix/` returned 500**
- Root cause: `hrms_approval_workflow_rules.l1_approver_role`/`l2_approver_role` were still the **old string-enum columns**, while the model has expected a `ForeignKey` to `Role` since migration `0049_approval_workflow_role_fk`. That migration was recorded as **applied** in `django_migrations` but its actual `AddField`/`RenameField`/data-population/`RemoveField` steps had never run for real against this DB (fake-applied at some point, cause unknown) — the classic "Django thinks it ran, the DB disagrees" drift, same family of bug as #3 but on the migration-tracking side instead of a raw manual column.
- Also found (already fixed by the time it was checked, possibly by another concurrent session): `backend/apps/announcements/migrations/0002_phase4_index_review.py` depended on `("accounts", "0048_phase4_index_review")`, a migration name that no longer exists after accounts' migrations were renumbered — the real one is `0055_phase4_index_review`. This alone was enough to make `manage.py migrate`/`showmigrations` fail outright with `NodeNotFoundError` for the *entire project*, not just this table.
- Fix: deleted the stray `django_migrations` row for `0049` and re-applied it **for real** via `MigrationExecutor.apply_migration()` called directly (bypasses `manage.py migrate`'s `check_consistent_history` gate, which otherwise refuses to touch `0049` alone once `0050`–`0055` are already — correctly — marked applied; blindly unfaking and rerunning the whole 0049–0055 range risked "already exists" errors against schema that had genuinely already landed).
- Two real bugs found *inside* migration `0049` itself while doing this (fixed in the migration file, since it had never actually executed successfully before):
  - Its data-population step didn't recognize a legacy `l2_approver_role='admin'` value present on the live Leave/Expense rules — would have silently discarded it. Confirmed with the user: maps to the `hr` role, same as `'hr_manager'`/`'hr_admin'`.
  - Its `_find_hr_role()` helper picked *any* role holding `leave.approve` permission from an unordered query — since Manager/System Admin/Branch Admin/HR all hold that permission, it non-deterministically resolved to "Manager" the first time (had to be manually corrected). Rewrote it to prefer the role literally named `hr` first.
- **Regression mid-fix**: after the first successful fix, migration `0049` reverted again — its `django_migrations` row disappeared and the schema went back to plain strings. Root cause: someone (very likely independent troubleshooting of the same `InconsistentMigrationHistory` error, from outside this session) ran a **real** (non-`--fake`) rollback of `0049` — which is not safely reversible, since its data-population step's reverse is a no-op and its `RemoveField` steps permanently drop whatever's in the FK columns on the way back. Re-applied the same way a second time, this time resolving correctly on the first pass since `_find_hr_role()` was already fixed.
- Also found three `django_migrations` rows (`0058_fix_approval_workflow_rule_columns`, `0059_refix_approval_workflow_rule_columns`, `0060_refix_approval_workflow_rule_columns_again`) with **no corresponding files on disk** — evidence someone else attempted to solve this exact problem via new migrations that were later deleted. Confirmed harmless (Django's loader silently ignores DB-recorded migrations it can't find on disk; `showmigrations` and `migrate --check` both run clean) and left alone rather than guessing at further cleanup.
- File: `backend/apps/accounts/migrations/0049_approval_workflow_role_fk.py`

**6. `POST /candidates/<id>/send-email/` — misleading error message**
- Not a bug: Gmail's own daily sending-limit (`550 5.4.5 Daily user sending limit exceeded`) on the configured SMTP account, from the volume of test emails sent throughout this session. No code fix for the limit itself — resets on Gmail's own schedule.
- Fixed the generic catch-all message it surfaced as (`"Failed to send email. Check SMTP configuration."`), which sends HR down the wrong troubleshooting path for this specific failure. Now detects 450/451/452/550-with-"limit" SMTP responses specifically and returns "The sending mailbox has hit its daily email limit. Try again later or contact your administrator." instead.
- File: `backend/apps/recruitment/views.py` (`SendCandidateEmailView.post()`)

### Investigation (informational, no code changed)

**7. Announcements — Branch + Visibility(2-option) + conditional Department create-form redesign**

User described a target UI (mockup screenshots) for the "Post New Announcement" form: an always-visible Branch dropdown ("All Branches" + real branches) alongside a Visibility dropdown with only two options ("All Employees" / "By Department"), with a Department dropdown appearing (and its options filtered by the selected Branch) only when "By Department" is chosen. Asked for backend-only work.

Confirmed by reading `Announcement.visibility`/`target_branch`/`target_department`, `AnnouncementWriteSerializer.validate()`, `DepartmentListCreateView` (already supports `?branch=<name>`), and `BranchListCreateView` that **the backend already fully supports this exact behavior** — the serializer already force-nulls `target_branch` whenever `visibility='department'` (matching the mockup's own helper text: department targeting always spans all branches), so the described 2-axis UI is just a different arrangement of the existing 3-value `visibility` enum, not a new capability. Verified all 3 roles that can create announcements (`hr`, `system_admin`, `branch_admin`) already hold both `branches.view` and `departments.view` — no permission gap either. Zero backend changes made; gave the frontend team the precise 3-case request-payload contract (`all` / `branch`+id / `department`+id) plus the full existing endpoint reference (list/create/detail/update/delete/react/view + the two supporting dropdown endpoints).

### Files Changed

```
backend/apps/accounts/views.py                             — EmployeeListCreateView.post() restored (moved out of dead duplicate class);
                                                               onboarding-submitted notification dispatch: ignore_result=True, retry=False
backend/apps/accounts/migrations/0049_approval_workflow_role_fk.py — _find_hr_role() made deterministic (prefers role name='hr');
                                                               'admin' added to legacy l2 string mapping
backend/apps/recruitment/migrations/0012_fix_meeting_link_not_null.py — NEW; drops stray NOT NULL on hrms_candidates.meeting_link
backend/apps/recruitment/views.py                           — referral + interview-scheduled email dispatch: ignore_result=True, retry=False;
                                                               SendCandidateEmailView: SMTP quota-specific error message
backend/apps/announcements/views.py                         — announcement email dispatch: ignore_result=True, retry=False
backend/apps/assessments/views/admin.py                     — assessment assignment email dispatch: ignore_result=True, retry=False
backend/apps/attendance/views/hr_attendance.py               — attendance reprocess dispatch: ignore_result=True, retry=False (task_id preserved)
backend/apps/attendance/services_hr_ops.py                  — attendance import dispatch: ignore_result=True, retry=False (task.id preserved)
backend/apps/notifications/signals.py                       — leave lifecycle email dispatch: ignore_result=True, retry=False
backend/config/settings.py                                  — CELERY_BROKER_TRANSPORT_OPTIONS, CELERY_BROKER_CONNECTION_MAX_RETRIES added
frontend/app/dashboard/employees/_components/AddEmployeeModal.tsx — HR dropdown fetch gated on branch being selected
```

### Data / DB fixes applied directly (not via `manage.py migrate` — see root causes above for why)

```
ALTER TABLE hrms_candidates ALTER COLUMN meeting_link DROP NOT NULL
django_migrations: accounts.0049_approval_workflow_role_fk re-applied for real via MigrationExecutor
                    (twice — see regression note above)
hrms_approval_workflow_rules: l2_approver_role corrected to the 'hr' Role for all 3 rows
                    (manual patch only needed the first time, before _find_hr_role() was fixed)
```

### Pending

- WSL2 → Windows localhost-forwarding to Redis is genuinely unreliable on this dev machine (confirmed, not root-caused) — email dispatch degrades gracefully now, but emails still won't actually send while it's down. Worth a dedicated pass (native Windows Redis / Memurai, or Docker Desktop, instead of WSL2 relay) rather than more Celery-side tolerance.
- Three orphan `django_migrations` records (`0058`/`0059`/`0060_refix_approval_workflow_rule_columns*`) with no matching files — confirmed harmless, not cleaned up.
- Frontend implementation of the Announcements Branch+Visibility+Department form redesign (backend confirmed ready, contract given above) — not started.
- Gmail SMTP daily send limit will keep tripping until it resets or a higher-volume provider/account is configured for real usage.

---

## Session Log — 2026-08-11
**Author: G.Durga Prasad**
**Branch: Backend/11/08/2026**

### Bug Fixes Shipped

**1. Duplicate candidate records — same email could be added repeatedly**
- Root cause: `Candidate.email` has no `unique=True`, and `CandidateCreateSerializer.validate_email()` did no duplicate lookup at all — confirmed live via two real rows for the same email (one "Interview Scheduled", one "Converted to Employee") showing up twice in the Hyderabad Interview List.
- Fix: `validate_email()` now rejects a create when `Candidate.objects.filter(email__iexact=value).exists()`, naming the existing candidate's name/status/position in the error.
- Verified live via the real serializer with the exact duplicate email (rejected with a clear message) and a fresh email (still passes).
- File: `backend/apps/recruitment/serializers.py`
- Cleaned up the pre-existing stale duplicate row (id=140, "Interview Scheduled") per explicit confirmation — kept id=141 (the real converted-to-employee outcome).

**2. Payroll seed migration crashes on a from-scratch `migrate`**
- Root cause: `hrms/0013_seed_leave_approval_workflow.py` assigns raw strings (`'reporting_manager'`/`'hr_manager'`) to `ApprovalWorkflowRule.l1_approver_role`/`l2_approver_role`, fields that `accounts/0049_approval_workflow_role_fk` later converts to `ForeignKey(Role)`. `0013` only declared a dependency on `accounts/0042`, so Django's planner was free to run `0049` first on a fresh install — confirmed via `MigrationExecutor` simulation (`accounts.0049` at plan position 69, `hrms.0013` at 161) before touching anything. Every real environment was unaffected only because it migrated incrementally in original chronological order.
- Fix: added `run_before = [('accounts', '0049_approval_workflow_role_fk')]` to the already-applied `hrms/0013` file — additive only, no change to its `operations`, so zero effect on databases where it already ran. Explicit, documented exception to the "never edit an applied migration" rule (approved this session) since no new-migration approach could work without breaking `InconsistentMigrationHistory` on every already-migrated environment.
- Verified: `makemigrations --check` clean against the live dev DB (nothing broke), and the fresh-install plan simulation now shows `hrms.0013` before `accounts.0049`.
- File: `backend/apps/hrms/migrations/0013_seed_leave_approval_workflow.py`

**3. Four real test-suite bugs, all traced to the same `l1/l2_approver_role` FK conversion**
- `apps/hrms/tests.py` — referenced the removed `ApprovalWorkflowRule.ROLE_REPORTING_MANAGER` string constant; fixed to assign an actual `Role` instance (`l2_approver_role: None` for the single-level test flow).
- `apps/accounts/factories.py` `make_role()` — had no way to set `can_manage_team`, so every "manager" role built by tests defaulted to `False`, silently breaking `_is_manager()`/`_resolve_approver()` checks. Added an explicit `can_manage_team: bool = False` param; updated the 3 call sites that represent real manager roles.
- `apps/payroll/tests.py` `PayrollCycleCreationNotifiesManagersTests` — `hr_user`/`manager` fixtures had no `branch`, but cycle creation and the manager-notification query both require one. Added a real `Branch`/`State`/`City` fixture.
- `apps/voice_commands/tests/test_approve_reject_leave.py` — 3 `SimpleTestCase` methods crashed with `DatabaseOperationForbidden` because the real approval flow calls `push_leave_update()` (an unmocked `User.objects.filter(...)` query). Mocked it at its source (`apps.dashboard.views.overview.push_leave_update`) rather than switching to a real `TestCase`, to avoid also exercising unrelated cache/channel-layer code.
- All 11 previously-failing tests verified passing; a 555-test regression sweep across `hrms`/`payroll`/`accounts`/`voice_commands` surfaced one unrelated stale-test-database schema-drift failure (`consent_text_version` column missing its default on `test_neondb` only — confirmed the real runtime `neondb` already has the default, so no live user impact; left alone per explicit decision).

### Code Quality — `_has_perm` centralized (major refactor)

- Found `_has_perm(user, codename)` — the core role/permission-codename check — copy-pasted independently across **36 files**. Verified precisely (not just trusted a summary): exact ordering/behavior extracted and tabulated for every copy.
- Confirmed two real, live security inconsistencies from the drift:
  - **33 of 36** copies check `if not user.role: return False` *before* the superuser bypass (11 of those have no superuser bypass at all), vs. 3 copies that correctly check superuser first. Proved a live divergence: `apps/dashboard/views/overview.py` returns `True` for a superuser with no linked `Role` row; `apps/dashboard/views/manager.py` returned `False` for the exact same account.
  - The documented "`settings.edit` overrides every specific codename" rule (comment present verbatim in several files) was only actually implemented in **13 of 36** copies — every single payroll `_has_perm`, plus `branch`, `recruitment`, and 3 `assessments` files, did a strict codename-only check with no fallback.
- Fix: added one `has_perm(user, codename)` to `backend/core/permissions.py` (correct superuser-first ordering + the `settings.edit` bypass), then updated all 36 call sites to `from core.permissions import has_perm as _has_perm` instead of redefining it. `apps/attendance/views/face_registration_hr.py` needed no change — it already imported `_has_perm` from `face_registration.py`.
- Also deduplicated three near-identical "today's clock-in status" blocks inside `apps/dashboard/views/overview.py` (`HRKPIView`, `EmployeeKPIView`, `EmployeeAttendanceStatusView`) into one shared `_todays_attendance(employee, today)` helper, following the file's existing `_headcount_data()` shared-helper pattern.
- Verified: `manage.py check` clean; full test suite re-run in progress at time of writing.

### Repo Cleanup

- `.gitignore` — added `backend/celerybeat-schedule`, `-shm`, `-wal` (Celery Beat's newer SQLite-backed runtime state, same category as the already-ignored `.dat`/`.dir`).
- Removed `royal-hrms (7).html` — a 452KB standalone static mockup that had been committed at the repo root (CDN-loaded fonts/icons, unrelated to the real `frontend/` Next.js app); violated the no-files-in-root rule.

### Nothing committed

All of the above is still local working-tree changes (per this session's standing rule: never commit/push without an explicit request) — ready for review before staging.
