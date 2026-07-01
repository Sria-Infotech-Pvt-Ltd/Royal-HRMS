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

### Pending

- Correction approval flow — manager approve/reject corrections
- Attendance reports — CSV/PDF download for HR
- Leave integration — auto-mark `on_leave` status when leave is approved
- Frontend implementation — prompts given to Teerdaveni, not yet started

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
