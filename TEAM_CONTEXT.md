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
