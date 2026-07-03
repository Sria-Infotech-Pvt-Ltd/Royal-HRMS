# Team Context — Assessment Feature

**Author:** Safura Samreen
**Date:** 2 July 2026
**Branch:** Frontend/Assessment

---

## Overview

This document covers all frontend work done on the assessment feature. No backend changes were made — all changes are frontend-only.

---

## 1. Login Page — Redirect Simplification

**File:** `app/login/page.tsx`

Removed the extra `GET /assessments/my/` API call that was being made after login just to check assessment status. The backend already returns `assessment_status` inside the login response under `d.user.assessment_status`.

**Redirect logic:**
```typescript
saveAuth(user);
let dest = "/dashboard";
if (user.onboarding_status !== "complete")     dest = "/onboarding";
else if (user.assessment_status === "pending") dest = "/onboarding/assessments";
window.location.href = dest;
```

`LoginApiResponse` interface updated to include `assessment_status: string` in the user object.

---

## 2. Auth Helpers

**File:** `lib/auth.ts`

Added `setAssessmentStatus(newStatus: string)` — updates `assessment_status` inside the `royal_hrms_user` cookie so the proxy stops redirecting after all assessments are complete.

```typescript
export function setAssessmentStatus(newStatus: string) {
  const user = getStoredUser();
  if (user) saveAuth({ ...user, assessment_status: newStatus });
}
```

---

## 3. API Endpoints

**File:** `lib/api/endpoints.ts`

Added under `assessments`:

| Key | URL | Method |
|-----|-----|--------|
| `my` | `/assessments/my/` | GET |
| `respond(assignmentId, itemId)` | `/assessments/<id>/respond/<itemId>/` | POST |
| `complete(assignmentId)` | `/assessments/<id>/complete/` | POST |
| `retake(assignmentId)` | `/assessments/<id>/retry/` | POST |
| `results(assessmentId)` | `/assessments/<id>/results/` | GET |
| `candidateResults(candidateId)` | `/assessments/candidates/<id>/results/` | GET |

> **Important:** The backend retry endpoint uses `retry` not `retake` in the URL path.

**Onboarding step fix:** Step 4 now posts to `/onboarding/` (the main profile endpoint) instead of `/onboarding/step/4/`. Steps 1–3 still use `profileStep(step)`.

```typescript
tab === 4 ? API.onboarding.profile : API.onboarding.profileStep(tab)
```

---

## 4. Candidate Assessments Page — Full Redesign

**File:** `app/onboarding/assessments/page.tsx`

Fully rebuilt into a **two-column exam portal layout**. No modals — everything is inline.

### Layout

```
┌─── Sidebar (280px) ─────┬──────── Main Content ────────────────┐
│  Assessment Portal      │  [Selected item renders here]        │
│  ─────────────────────  │                                      │
│  TEST 1          2/3    │  or                                  │
│  ─────────────────────  │                                      │
│  ✓ 1. Intro Video       │  "Select an item from the sidebar    │
│  ● 2. Policy Quiz  ←    │   to begin your assessment."         │
│  🔒 3. HR Quiz          │                                      │
│                         │                                      │
│  [Submit Assessment]    │                                      │
└─────────────────────────┴──────────────────────────────────────┘
```

### Sidebar
- Lists all assigned assessments as collapsible sections
- Each item shows: step circle (✓ done / 🔒 locked / number active), title, type badge
- Items lock until the previous one is completed (sequential)
- Mini progress bar + score per assessment section
- "Submit Assessment" button when all items answered
- "Retake Assessment" button when assessment failed
- Attempt history table (attempt #, score, date)

### Main Content States

| State | What renders |
|-------|-------------|
| Nothing selected | Landing — "Select an Item to Begin" prompt |
| Video selected (unwatched) | 16:9 iframe + "Mark as Watched" button |
| Video selected (watched) | iframe + "Already watched" banner + "Next Item →" |
| Quiz selected (unanswered) | Question card + A/B/C/D option rows + "Submit Answer" |
| Quiz selected (answered) | Result (correct/incorrect) + running score + "Next Item →" |

### YouTube Embed Conversion
HR saves share URLs; this function converts them to embeddable format for the iframe:
```typescript
function toEmbedUrl(url: string): string {
  // youtu.be/ID?si=...  → youtube.com/embed/ID
  // youtube.com/watch?v=ID → youtube.com/embed/ID
  // vimeo.com/ID → player.vimeo.com/video/ID
}
```

### Completion Flow
1. All items done → "Submit Assessment" button in sidebar
2. Click → `POST /assessments/<id>/complete/`
3. `CompletionModal` overlay appears with SVG circular score ring
4. **Pass:** "Go to Dashboard" → `router.push("/dashboard")`
5. **Fail:** "Re-take Assessment" ONLY — no dashboard option until passed
6. Retake → `POST /assessments/<id>/retry/` → clears state → refetch

### Cookie Unlock
```typescript
useEffect(() => {
  if (data?.all_complete) setAssessmentStatus("complete");
}, [data?.all_complete]);
```
Updates the `royal_hrms_user` cookie so the proxy stops redirecting once all assignments are passed.

### Key Types
```typescript
interface AssignmentItem {
  id, item_type, title, order, video_url, duration_secs,
  question, option_a, option_b, option_c, option_d,
  correct_option, pass_score, created_at
}

interface Assignment {
  id, assessment_title, status, score, max_score, passed,
  total_items, completed_items, attempt_number,
  items: AssignmentItem[],
  responses: ItemResponse[],
  attempts: AttemptRecord[]
}

interface RespondData {
  item_id, item_type, is_correct, score_awarded, assignment_score
}

interface AttemptRecord {
  attempt_number, score, max_score, passed, completed_at
}
```

---

## 5. HR Assessments Dashboard

**File:** `app/dashboard/assessments/page.tsx`

### Actual API Response Shape (`GET /assessments/`)
```json
{
  "data": {
    "results": [
      {
        "id": "e2339b03-...",
        "title": "TEST",
        "is_active": true,
        "is_default": true,
        "item_count": 2,
        "assigned_count": 2,
        "pending_count": 0,
        "in_progress_count": 0,
        "completed_count": 2,
        "candidates": [
          {
            "id": "...",
            "candidate_id": 24,
            "candidate_name": "Shashi",
            "candidate_email": "...",
            "status": "complete",
            "attempt_count": 1,
            "pass_score": 10,
            "score_awarded": 10,
            "pass_percentage": "100%",
            "completed_at": "2026-07-02T17:10:06...",
            "created_at": "2026-07-02T16:46:30..."
          }
        ],
        "items": [...]
      }
    ]
  }
}
```

> Candidate data is **embedded in the list response** — no separate results API call is needed.

### Page Layout

**Header area — Overall stats (aggregated across all assessments):**
4 stat cards: Total Assigned / Pending / In Progress / Completed

**Each assessment card (collapsed):**
- Title + Active/Default badges
- Action buttons: Results (toggle) | Items | Assign | Edit | Delete
- No extra padding when collapsed

**Each assessment card (expanded via Results button):**
- 5 stat tiles: Items / Assigned / Pending / In Progress / Completed
- Candidate results table:

  | Column | Source field |
  |--------|-------------|
  | Candidate | `candidate_name` + `candidate_email` |
  | Status | `status` (badge) |
  | Score | `score_awarded / pass_score` |
  | Pass % | `pass_percentage` |
  | Attempts | `attempt_count` |
  | Assigned | `created_at` |
  | Completed | `completed_at` |

### Types Added to `Assessment`
```typescript
interface AssessmentCandidate {
  id: string;
  candidate_id: number;
  candidate_name: string;
  candidate_email: string;
  status: "pending" | "in_progress" | "complete";
  attempt_count: number;
  pass_score: number;
  score_awarded: number;
  pass_percentage: string;
  completed_at: string | null;
  created_at: string;
}

// Assessment interface additions:
assigned_count: number;
pending_count: number;
in_progress_count: number;
completed_count: number;
candidates: AssessmentCandidate[];
```

### Removed
- `AssessmentResultsModal` component — no longer needed since data is embedded in list
- Separate `GET /assessments/<id>/results/` call — redundant

---

## 6. Proxy Behaviour (unchanged — documented for reference)

**File:** `proxy.ts`

```
if assessment_status === "pending" && path !== /onboarding/assessments
  → redirect to /onboarding/assessments
```

Reads from the signed `royal_hrms_user` cookie (httpOnly). After all assessments pass, `setAssessmentStatus("complete")` updates the cookie client-side and the redirect stops on the next navigation.

---

## Rules Followed

| File | Change |
|------|--------|
| `backend/apps/hrms/models.py` | Added `expense_number` PositiveIntegerField (unique, nullable, db_index) |
| `backend/apps/hrms/migrations/0006_expense_number.py` | **NEW** — schema migration |
| `backend/apps/hrms/migrations/0007_backfill_expense_number.py` | **NEW** — data migration (backfill) |
| `backend/apps/hrms/serializers.py` | Added `expense_ref` SerializerMethodField; replaced `id` → `expense_number` in `Meta.fields` |
| `backend/apps/hrms/views/expenses.py` | Full rewrite: added `ExpenseCategoryListView`, `ExpenseStatusListView`; full CRUD on `ExpenseDetailView`; `_handle_approval()` merged into PUT/PATCH; removed `ExpenseApprovalView`; `_get_expense` uses `expense_number`; `_fresh()` and `_validate_receipts()` helpers |
| `backend/apps/hrms/views/__init__.py` | Updated exports — `ExpenseCategoryListView`, `ExpenseStatusListView` added; `ExpenseApprovalView` removed |
| `backend/apps/hrms/urls.py` | Added `expenses/categories/`, `expenses/status/`; detail URL changed to `<int:expense_number>/`; removed `expenses/<str:expense_id>/approve/` |
| `backend/apps/accounts/views.py` | Logger fixed to `__name__`; inline stdlib imports moved to top; `PermissionListView` paginated; `_ensure_default_rules()` rewritten to 1 SELECT + bulk_create; redundant inline imports removed |

---

### Notes for Next Developer (01 July 2026)

- **All expense URLs use `expense_number` (integer), not UUID** — e.g. `/api/expenses/1/`. The UUID (`id`) is the database primary key and is still used internally by `_fresh()` for re-fetch after save, but it is not in the API response and not in the URL.
- **Approval = PUT/PATCH with `status` field** — sending `{ "status": "approved" }` or `{ "status": "rejected" }` on any PUT/PATCH triggers `_handle_approval()`. Any other PUT/PATCH (without `status` key) is treated as an edit.
- **PUT replaces all receipts; PATCH appends** — if you send files on a PUT, all old receipts are deleted first. If you send files on a PATCH, new receipts are added to existing ones.
- **Single receipt delete** — `DELETE /api/expenses/<number>/?receipt_id=<uuid>`. The `receipt_id` is the UUID of the `ExpenseReceipt` record (still UUID — only the expense URL uses integer).
- **`expense_number` is race-condition-safe** — `select_for_update()` + `transaction.atomic()` in `post()`. Never assign `expense_number` manually outside this block.
- **`_ensure_default_rules()` now runs 0 DB writes on every GET** — only 1 SELECT. `bulk_create` fires only once when rules are genuinely missing. No performance concern on repeated calls.
- **Backfill is idempotent** — migration 0007 only touches rows where `expense_number IS NULL`. Re-running it is safe.

---

## Session 15 — Rithwika (02 July 2026)

**Branch:** `frontend/02-07`

---

### 1. HR Attendance Management — Full Frontend Build-out (`app/dashboard/attendance/`)

Wired the entire HR Attendance page (previously a static mock screen) to the real backend across 9 endpoints.

#### `lib/api/endpoints.ts` — new `attendance` keys
```
dashboard, records, record(id), overtime, overtimeCreate,
invalidPunches, unPunches, import, export, corrections, correctionReview(id)
```
Paths omit the `/api` prefix — `API_BASE` (`lib/config.ts`) already supplies it as the axios `baseURL`.

#### `types/attendance.ts` — new types
`StatCards`, `SummaryChips`, `TabBadges`, `DashboardData`, `AttendanceRow`, `PaginatedResponse<T>` (generic, reused for all 4 paginated lists), `AttendanceDetailPunch`, `AttendanceDetail`, `OvertimeRow`, `OvertimeCreatePayload`, `InvalidPunch`, `UnpunchRow`, `ImportResult`/`ImportRowError`, `CorrectionRow`, `CorrectionStatus`, `CorrectionReviewAction`.

> **Naming collision:** the backend's punch shape for the detail drawer is also called `PunchEntry` in the spec I was given, but that name already exists in this file for the live clock-in/out session (`type/location/attendance_mode/is_inside_geofence/calculated_distance` — a completely different shape). Renamed the new one to `AttendanceDetailPunch` with a comment explaining why.

#### `app/dashboard/attendance/page.tsx`
- Top 4 stat cards + tab badge counts wired to `GET /attendance/dashboard/`.
- Tab bar: **Attendance · OT Entry · Invalid Punches · Un-punches** (kept to exactly these 4 — see §4 and §5 below for how Corrections fits in).

#### `AttendanceTab.tsx`
- Real branch/department dropdowns, paginated records table from `GET /attendance/records/`, summary chips from the dashboard endpoint (called a second time with the tab's own filters), Prev/Next pagination.
- **View** button opens `AttendanceDetailDrawer` (see §2) — disabled when `record_id` is `null` (absent employees have no record).
- **Export CSV** — blob download via `clientApi.get(url, { responseType: "blob" })`.
- **Import** — real multipart upload wired in `ImportModal.tsx`; shows a result summary with a collapsible per-row error table before closing.

#### `OtEntryTab.tsx`
- Add OT Entry form posts to `POST /attendance/overtime/create/`; employee/approver dropdowns sourced from `/employees/` and `/employees/hrs/`.
- OT Records table from `GET /attendance/overtime/`.

---

### 2. Attendance Detail Drawer — Comprehensive View (`AttendanceDetailDrawer.tsx`)

The "View" button on the Attendance List originally opened a small centered modal with just clock in/out + a punch timeline. Rebuilt into a full side drawer covering everything HR needs to investigate a day's attendance without leaving the page:

- Switched markup from `.modal-overlay`/`.modal` to the app's existing `.drawer-overlay`/`.drawer` pattern (already used in `candidate-review/OnboardingQueueTab.tsx`, just not reused elsewhere yet).
- **Attendance Calculation** section — clock in/out, total hours, **and overtime** (was fetched but never rendered before).
- **Punch History & Location** — geofence status icon (✓ / ✗ / dashed) + distance-from-geofence per punch, source, mode.
- **Correction Requests** (new) — fetches `GET /attendance/corrections/?employee_id=&date=`, filtered client-side as a safety net in case the backend ignores the query params. Pending requests get inline Approve/Reject buttons (`PATCH /attendance/corrections/<id>/review/`) so HR can resolve a correction without switching tabs.
- **Audit Log** — deliberately left as a labeled "not available yet" placeholder. There is no record-scoped audit endpoint anywhere in the API (the only audit endpoint, `/settings/audit/`, is a global log filtered by module/date/search text, not scopable to one attendance record). Faking that connection would show misleading data — flagged this instead of guessing.

---

### 3. Branch Geofencing (`BranchManagement.tsx`, `useClockWidget.ts`, `ClockWidget.tsx`)

Two rounds of spec came in for this; the second superseded some of the first (documented below so nobody re-does the first version).

#### Branch form (`app/dashboard/branches/_components/BranchManagement.tsx`)
- Added `geofencing_enabled` (toggle switch — built a small self-contained one with inline styles since **no toggle-switch CSS exists anywhere in this codebase**, only checkboxes), `latitude`, `longitude`, `allowed_radius_meters` (min 10 / max 5000, default 150), all shown only when the toggle is on.
- Validation matches exact copy requested: both lat/lon empty → *"Latitude and longitude are required to enable geofencing."*; only one filled → *"Both latitude and longitude must be provided together."*
- Save call switched from `PUT` to **`PATCH`** on branch update, per explicit instruction.
- Badge on each branch card ("Geofencing" row, reused the existing Employees/Status info strip): green **Active** / yellow **No Coordinates** / grey **Disabled**, using the backend's own `has_coordinates` read-only field rather than a client-side null check.
- **No separate branch detail page exists in this app** — branches are cards with one edit modal, no `/dashboard/branches/[id]` route. The "detail row" requirement (radius + coordinates text) was added to the same card rather than inventing a new page.

#### Punch flow — root-cause fix for the geofencing bypass bug
The reported symptom: an employee physically in Mumbai could clock in as if they were at the Hyderabad branch and it would succeed. Root cause found in `hooks/useClockWidget.ts`: the geolocation error handler only handled `GeolocationPositionError.code === 1` (permission denied) — any *other* failure (timeout, position unavailable) fell through silently and the punch request went out with `latitude`/`longitude` = `null`. If the backend only enforces the geofence check when coordinates are present, that null-coordinate path is exactly how a mismatched-location clock-in slips through.

Fixed:
- Unsupported browser and permission-denied now both **block the request** with exact-wording toasts (final wording: *"Your browser does not support location access."* / *"Location access is required for office clock-in. Please allow location in your browser settings."*).
- Any other geolocation error (timeout/unavailable) **also now blocks** instead of silently continuing with null coordinates — this is the actual fix, not explicitly requested in either spec revision but left unguarded would reopen the same hole.
- Added `isLocating` state → "Getting location…" shown on the Clock In/Out button while GPS resolves.

---

### 4. Attendance Corrections Workflow

Built as its own "Corrections" tab first, then merged into "Un-punches" per direct instruction — final tab bar stayed at exactly 4 tabs (Attendance · OT Entry · Invalid Punches · Un-punches).

- **`CorrectionsTab.tsx`** (new) — branch/department/status filters (status defaults to `pending`), full table (Employee ID · Name · Department · Branch · Date · Punch Type · Requested In · Requested Out · Reason · Status · Actions). Pending rows get Approve/Reject (`PATCH /attendance/corrections/<id>/review/`); approved/rejected rows show `reviewed_by`/`reviewed_at` instead.
- **`UnpunchesTab.tsx`** — the original missing-clock-out table (with its own per-row `correction_pending` badge + inline approve/reject) was later removed entirely per instruction; the tab now renders only `<CorrectionsTab />`. `AddPunchModal.tsx` was deleted since it had no other caller once that table was removed.
- `UnpunchRow` type carries the new `correction_pending`/`correction_id` fields.

---

### 5. Invalid Punches — Put on Hold

No resolution/fix endpoint exists for invalid punches (only the `GET` list). Rather than ship a "Fix" button that does nothing, `InvalidPunchesTab.tsx` now renders a "Coming Soon" empty-state (reusing the existing `.empty-state` class). The original table/fetch logic is commented out in place, not deleted, so it's a one-step revert once a resolve endpoint exists.

---

### 6. Branch-Scoped Access Control for `hr_admin`

Backend now enforces branch scoping server-side (`hr_admin` always gets their own branch's data regardless of `?branch=`) — this made the UI need to stay honest about it (locked dropdown, not a silently-ignored "All Branches" option).

> **Adapted the given helper to this app's real user shape.** The spec's `isUnrestrictedUser` checked `user.is_superuser === true || user.role?.name === 'system_admin'`, but this codebase's `UserInfo` (`lib/auth.ts`) has `role` as a **flat string**, not a nested object, and has **no `is_superuser` field at all** anywhere in the frontend. Implemented against the real shape: `user?.role === "system_admin"`. Copying the spec verbatim would have made the check permanently `false`.

- **`lib/auth.ts`** — added `isUnrestrictedUser(user)` / `getEffectiveBranch(user)`.
- **`hooks/useCurrentUser.ts`** (new) — wraps `getStoredUser()` in `useEffect`; this repo already has a documented hydration-mismatch gotcha for calling `getStoredUser()` at render time (see the Session 2 notes above), so this hook exists specifically to not reintroduce that bug in five new places.
- **`components/BranchFilterSelect.tsx`** (new, shared) — full dropdown for `system_admin`; single disabled option + lock icon/tooltip ("Scoped to your branch") for `hr_admin`. Used in Attendance List, OT List, Corrections.
- **`hooks/useDepartmentOptions.ts`** (new, shared) — `system_admin` gets the global `/departments/` list; `hr_admin` gets department names derived from `GET /employees/?branch=<branch>` instead, since departments aren't branch-scoped as master data.
- **Page-level (`page.tsx`)** — dashboard fetch gated on the user object having resolved (never fires unscoped before we know who's asking); light-blue info chip "🏢 Viewing data for `<branch>` only" below the header for `hr_admin` only; page title appends `— <branch>`.
- **Export filename** — `attendance_Mumbai-HQ_2026-07-02.csv` for `hr_admin` (branch name space→hyphen), unchanged `attendance_2026-07-02.csv` for `system_admin`.
- **OT List had no filter UI at all before this** — added a branch filter to it since it was explicitly named as an affected page.

---

### 7. My Attendance — Punch Log Simplified (`ClockWidget.tsx`)

The Punch Log was rendering every punch of the day (could be 8+ rows after a few correction/duplicate punches). Changed to show only the two most relevant rows:
```tsx
const latestIn  = [...punches].reverse().find(p => p.type === "IN")
const latestOut = [...punches].reverse().find(p => p.type === "OUT")
const displayPunches = [latestIn, latestOut].filter(Boolean)
```
Order is always IN then OUT (fixed by array position, not sorted by time).

---

### 8. Production Build Fix — `LeaveDashboard.tsx` TypeScript Error

`npm run build` was failing type-check (unrelated to any of the attendance work above — pre-existing, just never surfaced until a full build was run):

```
./app/dashboard/leave/_components/LeaveDashboard.tsx:53:7
Type error: 'requests' is possibly 'null'.
  51 |   const visibleRequests = selectedBranches.length === 0
  52 |     ? requests
> 53 |     : requests.filter(r => selectedBranches.includes(r.employee_branch));
```

`requests` comes from `useFetch<LeaveRequest[]>(...)`, typed `LeaveRequest[] | null`. Every other read of `requests` in this file already guards with `requests ?? []` — this one ternary didn't. Minimal fix, matching the existing pattern in the same file:

```tsx
const visibleRequests = selectedBranches.length === 0
  ? (requests ?? [])
  : (requests ?? []).filter(r => selectedBranches.includes(r.employee_branch));
```

Confirmed with a full `tsc --noEmit` afterward — this was the only remaining type error in the whole project.

---

### Key Files Changed / Created (02 July 2026)

| File | Change |
|------|--------|
| `lib/api/endpoints.ts` | Added `attendance.{dashboard,records,record,overtime,overtimeCreate,invalidPunches,unPunches,import,export,corrections,correctionReview}` |
| `types/attendance.ts` | Added all HR-management types listed in §1; `AttendanceDetailPunch` (renamed to avoid collision); `CorrectionRow`/`CorrectionStatus`/`CorrectionReviewAction`; `correction_pending`/`correction_id` added to `UnpunchRow` |
| `app/dashboard/attendance/page.tsx` | Real dashboard fetch, branch-scoping (banner, title suffix, gated fetch), tab badges |
| `app/dashboard/attendance/_components/AttendanceTab.tsx` | Full rewrite — real records/summary/export/import, locked branch filter, scoped departments |
| `app/dashboard/attendance/_components/AttendanceDetailDrawer.tsx` | **NEW** — side drawer (calculation, punch/location, corrections, audit placeholder) |
| `app/dashboard/attendance/_components/OtEntryTab.tsx` | Real OT list + create; added branch filter (previously had none) |
| `app/dashboard/attendance/_components/CorrectionsTab.tsx` | **NEW** — corrections table, branch/department/status filters, approve/reject |
| `app/dashboard/attendance/_components/UnpunchesTab.tsx` | Old missing-clock-out table removed; now renders `<CorrectionsTab />` only |
| `app/dashboard/attendance/_components/InvalidPunchesTab.tsx` | Table/fetch commented out; "Coming Soon" empty-state shown instead |
| `app/dashboard/attendance/_components/ImportModal.tsx` | Real multipart upload + result summary with collapsible row errors |
| `app/dashboard/attendance/_components/AddPunchModal.tsx` | **DELETED** — no longer referenced after the Un-punches table was removed |
| `app/dashboard/branches/_components/BranchManagement.tsx` | Geofencing fields (toggle, lat/lon, radius), validation, `PATCH` on save, `has_coordinates`-based badge, radius/coordinates detail text on card |
| `hooks/useClockWidget.ts` | Geolocation error handling fixed to block on *any* failure (root cause of the cross-branch clock-in bug), `isLocating` state added |
| `app/dashboard/my-attendance/_components/ClockWidget.tsx` | "Getting location…" button state; Punch Log now shows only latest IN/latest OUT |
| `lib/auth.ts` | Added `isUnrestrictedUser`, `getEffectiveBranch` |
| `hooks/useCurrentUser.ts` | **NEW** — hydration-safe `getStoredUser()` wrapper |
| `hooks/useDepartmentOptions.ts` | **NEW** — branch-scoped department options for `hr_admin` |
| `components/BranchFilterSelect.tsx` | **NEW** — shared locked/unlocked branch dropdown |
| `app/dashboard/leave/_components/LeaveDashboard.tsx` | Build fix — `visibleRequests` ternary now guards `requests` with `?? []` on both branches (was only guarded in the rest of the file) |

---

### Notes for Next Developer

- **Invalid Punches is intentionally disabled** — see §5. Don't re-enable the commented-out table without a resolve/fix endpoint (`assign` / `convert_to_out` / `discard` — none of these exist yet).
- **Audit Log in the detail drawer is a placeholder** — needs a record-scoped endpoint, e.g. `GET /attendance/records/<id>/audit/`, before it can be wired for real.
- **`isUnrestrictedUser` checks `role === "system_admin"` as a flat string** — if the backend ever changes `UserInfo.role` to a nested object, this helper (and every other `user?.role === "..."` check across the app — `employees/page.tsx`, `announcements/page.tsx`, `ApprovalMatrixTab.tsx`) needs updating together, not just this one.
- **`useDepartmentOptions` assumes `/employees/?branch=<name>` filtering works** — it's the same convention already used by `/employees/hrs/?branch=`, but hasn't been independently verified against `/employees/` specifically.
- **Toggle switch in `BranchManagement.tsx` is a one-off inline component**, not a shared one — if a second toggle is needed anywhere else, promote it to `components/ToggleSwitch.tsx` instead of copy-pasting.
- **OT List and Corrections branch filters are net-new UI** (those tabs had zero filters before today) — worth a design pass if the team wants them visually consistent with the Attendance List's filter bar layout.
- **`npm run build` type-checks clean as of this session** — if it fails again, run `npx tsc --noEmit` first to isolate whether it's a new regression or another pre-existing `?? []` guard gap like §8.

---

- No backend changes in this entire branch
- All API paths from `lib/api/endpoints.ts` — no inline strings
- All data fetching via `useFetch` hook
- `clientApi` used with `withCredentials: true`
- No `localStorage` for tokens
- No `any` types — all shapes explicitly typed

---

## Session — Safura Samreen (03 July 2026)

**Branch:** `Frontend/Assessment-Update`

---

### 1. Assessment Settings Page (new) — `app/dashboard/settings/assessment-config/page.tsx`

Built the global assessment configuration sub-page under Settings.

- Three configurable fields: Default Pass Percentage, Maximum Attempts (0 = unlimited), Time Limit (null = no limit)
- Table layout matching the `approval-rules` pattern — per-row Edit buttons opening an inline modal
- `GET /assessments/settings/` on load; `PUT` on save (full object — no PATCH)
- "Last updated" timestamp shown below the table
- `time_limit_enabled` is UI-only state derived from whether `time_limit_mins !== null`
- Added `settings.assessmentConfig` to `lib/api/endpoints.ts` (corrected URL from `/settings/assessments/` → `/assessments/settings/`)

---

### 2. Assessment Management Page — `app/dashboard/assessments/page.tsx`

Extended assessments to carry per-assessment overrides and richer candidate results.

#### Per-assessment overrides
- New form fields: `pass_percentage`, `max_attempts` (blank = inherit global), `time_limit_mins` (blank = no limit)
- Blank values send `null` to backend — backend falls back to global default
- Card metadata shows effective values with `(global)` label when the field is `null`
- `openCreate` pre-fills form from `GET /assessments/settings/` so new assessments default to the current global config

#### Candidate results table
- **Score column replaced with Result** — shows a green "Passed" or red "Failed" badge
  - Reads `passed: boolean | null` directly from backend (no client-side derivation)
  - Shows `—` when `status !== "complete"` (pending/in-progress candidates have no result yet)
- **Sections Breakdown** — expandable sub-row per completed candidate
  - Renders `sections_breakdown[]` with section title, score, correct answers, percentage
  - Percentage coloured green ≥ 100 / amber ≥ 50 / red < 50

#### Other fixes
- "Items" button on each assessment card renamed to **"Sections"** (icon changed to `ti-layout-list`)
- Fixed React `key` warning in candidates map — replaced `<>` shorthand with `<Fragment key={c.id}>` from React (shorthand does not accept a `key` prop)
- Fixed TypeScript errors in `AssessmentResultsModal.tsx` — fields `candidate_name` / `candidate_email` renamed to `assignee_name` / `assignee_email` to match the updated `AssessmentCandidate` interface

#### New types added
```typescript
interface AssessmentSettings {
  default_pass_percentage: number;
  max_attempts: number;
  time_limit_mins: number | null;
}

// Additions to AssessmentCandidate:
passed: boolean | null;
sections_breakdown: SectionBreakdown[];
attempt_count: number;

// Additions to Assessment:
pass_percentage: number;
max_attempts: number | null;
time_limit_mins: number | null;
effective_max_attempts: number;
effective_time_limit_mins: number | null;

interface SectionBreakdown {
  title: string;
  max_score: number;
  achieved_score: number;
  correct_answers: number;
  total_questions: number;
  percentage: string;
}
```

---

### 3. Sections Modal — `app/dashboard/assessments/_components/ItemsModal.tsx`

Full rewrite from video-order-based section grouping to explicit backend section objects.

#### Architecture change
- **Old:** Sections were inferred by treating each video item as a section header, with quiz items following it grouped under it.
- **New:** Sections are first-class backend objects (`POST/GET/PUT/DELETE /assessments/<id>/sections/`). Items are assigned to sections via a `section_id` field.

#### Fetching
- `useFetch<AssessmentSection[]>(API.assessments.sections(assessment.id))` — sections
- `useFetch<AssessmentItem[]>(API.assessments.items(assessment.id))` — items
- Fallback: if items fetch returns non-array (e.g. paginated wrapper), falls back to `assessment.items` from the list response

#### Section CRUD
- Add / Edit / Delete sections via `POST`, `PUT`, `DELETE` on the sections endpoint
- Each section header row has an edit (pencil) and delete (trash) button — full inline form below the list
- Section form fields: Title, Order, Score (marks allocated)

#### Item-to-section mapping fix
- Backend returns `section_id` in GET responses but the old interface had `section: string | null`
- Filtering `i.section === sectionId` always returned `false` → all items fell into unsectioned
- Fixed: `AssessmentItem` interface gains `section_id: string | null`; filters updated to `(i.section_id ?? i.section) === sectionId`
- POST/PUT still sends `section: forSectionId` (what the backend accepts for writes)

#### Empty-state logic fix
- "No sections yet" message was appearing alongside the unsectioned items list, which was confusing
- Fixed condition: empty state only shown when both `sections.length === 0` AND `items.length === 0`
- Unsectioned items header shows a neutral "Items" label (grey, list icon) when no sections exist; only shows the orange warning triangle when sections exist but some items are unassigned

#### Video display
- Added `VideoLink` helper — renders a clickable external link for video items in the item list
- Added `VideoPreview` helper — renders a 16:9 embedded iframe (YouTube/Vimeo) or `<video>` tag in the edit form
- `toEmbedUrl()` converts share URLs (youtu.be, youtube.com/watch, vimeo.com) to embed format

#### New section endpoint keys in `lib/api/endpoints.ts`
```typescript
sections:      (assessmentId: string) => `/assessments/${assessmentId}/sections/`
sectionDetail: (assessmentId: string, sectionId: string) => `/assessments/${assessmentId}/sections/${sectionId}/`
```

---

### 4. Candidate Portal — `app/onboarding/assessments/page.tsx`

Extended the assignment interface and added a countdown timer with auto-submit.

#### New assignment fields
```typescript
attempt_count:          number;
effective_max_attempts: number;    // 0 = unlimited
attempts_remaining:     number | null;
started_at:             string | null;
time_limit_mins:        number | null;
time_remaining_secs:    number | null;
```

#### Countdown timer
- Initialised once from `time_remaining_secs` in API response (not recalculated client-side)
- Single `setInterval` ticks all active assignment timers in one pass
- Timer turns red when under 60 seconds
- Auto-submits via `POST /assessments/<id>/complete/` when timer hits zero
- `autoSubmitting` ref (a `Set<string>`) prevents duplicate submissions when the interval fires multiple times at `0`
- Sidebar shows attempts remaining and a `MM:SS` formatted countdown

---

### 5. Assign Assessment Modal — Multi-select with Search (`app/dashboard/assessments/page.tsx`)

Replaced the single-candidate dropdown with a searchable multi-select employee list.

#### What changed
- **API source**: `GET /recruitment/candidates/review/` → `GET /employees/?page_size=500`
  - Previous endpoint only returned candidates in the recruitment review stage; assessments can now be assigned to any active employee
- **Interface**: `ReviewCandidate { id, name, email }` → `AssignEmployee { id, employee_id, full_name, email, department }`
- **State**: `assignCid: string` → `assignCids: string[]` + `assignSearch: string`

#### UI
- Search input filters by `full_name`, `email`, or `employee_id` in real time
- Scrollable checkbox list (max height 260px) — each row shows name, employee ID, email, department
- "Select All / Deselect All" button operates on the currently filtered set (not the full list)
- Counter: `N selected · M shown`
- Assign button shows the count when > 1 selected: "Assign (5)"

#### Multi-assign logic
```typescript
for (const empId of assignCids) {
  await clientApi.post(API.assessments.assign, { candidate_id: empId, assessment_id: assignFor.id });
}
```
Loops sequentially; counts successes and first error message. Shows `"Assigned to N employees successfully!"` on full success, or `"N succeeded, M failed: <reason>"` on partial failure.

---

### Key Files Changed (03 July 2026)

| File | Change |
|------|--------|
| `lib/api/endpoints.ts` | Settings URL corrected; `sections` and `sectionDetail` endpoints added |
| `app/dashboard/settings/assessment-config/page.tsx` | **NEW** — global assessment config settings page |
| `app/dashboard/assessments/page.tsx` | Per-assessment overrides; Pass/Fail badge; sections breakdown; Fragment key fix; "Sections" button rename; assign modal rewritten to multi-select employees |
| `app/dashboard/assessments/_components/ItemsModal.tsx` | Full rewrite — explicit sections, video display, empty-state fix, `section_id` mapping fix |
| `app/dashboard/assessments/_components/AssessmentResultsModal.tsx` | `candidate_name`/`candidate_email` → `assignee_name`/`assignee_email` |
| `app/onboarding/assessments/page.tsx` | Countdown timer, auto-submit, attempts remaining display |

---

### Notes for Next Developer

- **`section_id` vs `section`** — backend GET responses use `section_id`; POST/PUT bodies use `section`. Both fields are on `AssessmentItem` with a `??` fallback for compatibility. If the backend normalises to one name, remove the fallback.
- **`passed` comes from backend** — do not derive it client-side from `pass_percentage`. The backend calculates it and sends `true`/`false`/`null`.
- **Countdown timer does not re-sync with backend** — it starts from `time_remaining_secs` on first load and counts down locally. On page refresh, the API re-sends the fresh `time_remaining_secs` and the timer re-initialises. Do not add a re-sync interval.
- **`autoSubmitting` ref** — this `Set<string>` is intentionally a ref (not state) so that adding to it does not trigger a re-render. Do not convert it to state.
- **Assign multi-send is sequential, not parallel** — `for...of` loop with `await` per request. If the backend adds a bulk-assign endpoint (`POST /assessments/assign/bulk/`), replace the loop with a single request.
- **"Select All" operates on filtered set** — if the user has searched for "Roh" and clicks Select All, only the visible filtered employees are selected, not all 500. This is intentional.
- **`tsc --noEmit` was clean at end of session** — only errors were stale IDE diagnostics.
