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
