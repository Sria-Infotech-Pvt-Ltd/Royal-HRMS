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

---

## Session — Safura Samreen (06 July 2026)

**Branch:** `Frontend/Assessment-Update`

---

### 1. Email Branding Card — `app/dashboard/settings/email-templates/page.tsx`

Added a live Email Header & Footer branding card at the top of the email templates page.

- Fetches company info from `GET /api/settings/company/` on page load
- **Header preview** — shows company logo (or company name fallback) with blue bottom border, mirroring the actual email header
- **Footer preview** — shows `website | address, city, state` text, mirroring the actual email footer
- **Edit form** (toggled by Edit button): logo upload + 6 text fields (company name, website, phone, address, city, state) in a 2-column grid
- `saveBranding()` sends `PATCH /api/settings/company/` as `FormData` (needed for logo file upload); updates `company` state on success
- Logo preview uses `URL.createObjectURL()` for instant local preview before saving

#### New interface and state
```typescript
interface BrandingForm {
  company_name: string; website: string; address: string;
  city: string; state: string; official_phone: string;
}
// States: brandingOpen, brandingForm, brandingSaving, logoFile, logoPreview, logoInputRef
```

#### TypeScript fix for TYPE_META access
`TYPE_META[type as TemplateType]` caused a type error when `type` came from the API as a plain string. Fixed with:
```typescript
const meta = (TYPE_META as Record<string, { label: string; color: string; icon: string }>)[type]
  ?? { ...FALLBACK_META, label: cat?.name ?? type };
```

---

### 2. Email Variable Substitution — `MarkCandidateModal.tsx`

The email preview in the Select/Reject modal was already substituting variables locally via `renderTemplateVars`. Wired up `extra_context` so the backend also receives all candidate variable values when sending the actual email.

#### `candidateVars()` — comprehensive context builder
```typescript
function candidateVars(): Record<string, string> {
  // Returns both snake_case and uppercase keys to cover all template styles:
  candidate_name, full_name, first_name, last_name,
  email, position_applied, position,
  branch, branch_name, interview_date,
  interview_mode, interview_mode_display,
  company_name,
  FULL_NAME, FNAME, LNAME, EMAIL, POSITION, COMPANY
}
```

`interview_mode_display` maps `in_person` → `"In-Person"` etc. via `MODE_LABELS`.

#### handleConfirm passes extra_context
```typescript
RECRUITMENT_API.setStatus(candidate.id, {
  status: targetStatus, remarks,
  template_name: selectedTemplate?.name,
  extra_context: candidateVars(),   // ← added
});
```

#### Fixed hasManualVars check
Was using `.toUpperCase()` to check against `AUTO_KEYS` which contains lowercase keys — every variable incorrectly appeared "unfilled". Fixed to `.toLowerCase()`:
```typescript
// Before (broken):
.some(v => !AUTO_KEYS.has(v.toUpperCase()))
// After:
.some(v => !AUTO_KEYS.has(v.toLowerCase()))
```

---

### 3. Interview Details Save — `EditCandidateModal.tsx`

`handleSave()` now builds and passes `extra_context` when saving interview details, so the backend has all values available for the interview scheduled email:

```typescript
const extra_context: Record<string, string> = {
  candidate_name, full_name, first_name, last_name,
  email, position_applied,
  branch, branch_name,         // from branches.find(b => b.id === branch)
  interview_date,              // sliced to YYYY-MM-DD
  interview_mode,
  interview_mode_display,      // human-readable via MODE_LABELS
};
```

---

### 4. API Type Updates — `_data.ts`

`setStatus` and `update` now include `extra_context` in their payload types:

```typescript
setStatus: (id, body: {
  status: CandidateStatus; remarks?: string;
  template_name?: string;
  extra_context?: Record<string, string>;   // ← added
}) => ...

update: (id, body: Partial<Pick<Candidate, ...>> & {
  extra_context?: Record<string, string>;   // ← added
}) => ...
```

---

### 5. `lib/emailPreview.ts` — documented for reference

Two exports used by both the email templates settings page and `MarkCandidateModal`:

- `renderTemplateVars(text, vars)` — replaces `{key}` tokens with values; leaves unknown `{key}` visible
- `buildEmailPreview(body, company)` — wraps a rendered body with the company-branded HTML email wrapper (header with logo + footer with website/address), matching the backend's `_company_email_wrapper` helper

---

### Backend issue identified (fix required on backend)

The frontend sends `extra_context` correctly for all email flows. However `CandidateStatusView.patch` in `backend/apps/recruitment/views.py` line 391 calls `_send_candidate_email` without passing `extra_context` — the function already accepts and merges it, the view just never reads it from `request.data`.

**Backend fix needed** (one line change at `views.py:391`):
```python
# Current:
email_status = _send_candidate_email(candidate, template_slug, request.user)

# Fix:
raw_extra     = request.data.get('extra_context') or {}
extra_context = {k: str(v)[:2000] for k, v in raw_extra.items() if isinstance(k, str) and k.isidentifier()} if isinstance(raw_extra, dict) else {}
email_status  = _send_candidate_email(candidate, template_slug, request.user, extra_context)
```

`CandidateHRDecisionView.patch` already does this correctly — only the status-change view is missing it.

---

### 6. Referral Page — `app/dashboard/referrals/page.tsx` (NEW)

Full employee referral portal built from scratch.

#### Structure
Three tabs inside a single card:
- **My Referrals** — visible to all employees; shows referrals submitted by the logged-in user
- **All Referrals** — visible only when `recruitment.view` permission is present (HR/Admin); shows every referral across all employees
- **Referral Rules** — visible to all; fetches and displays active rules configured in Settings → Referral Rules

#### Stats row
Four cards computed from `myReferrals`:
- Total Referred · In Pipeline (excludes `rejected`/`converted`) · Selected (includes `offer_sent`) · Converted

#### Refer Someone modal
Inline form fields: Full Name, Email, Phone, Position Applied For, Branch (read-only, auto-filled from cookie), Relationship (dropdown), Notes (textarea).
- `handleSubmit` POSTs to `API.referrals.create`; on success calls `myRefetch()` and shows a 4-second success banner
- `relationship` and `notes` are merged: `"Relationship: {value}\n{notes}"` sent as the `notes` field
- Branch field is a display-only chip (not an editable select) — the employee can only refer to their own branch

#### Permission check (client-side only)
```typescript
const pair = document.cookie.split(";").find(c => c.trim().startsWith("royal_hrms_user="));
const user = JSON.parse(decodeURIComponent(raw));
setIsAdmin(user.permissions?.includes("recruitment.view") ?? false);
```
This controls the "All Referrals" tab visibility. **Backend enforces it independently** — `API.referrals.all` returns 403 for non-admin users regardless.

#### ReferralTable component
Reusable table shared by "My Referrals" and "All Referrals" tabs. Client-side search via `search` state — filters `name`, `position_applied`, `referral_by_name`. Referred-by name shown in purple with `ti-user-plus` icon.

#### Bonus breakdown table (inside Rules tab)
Static `BONUS_STAGES` constant — three stages (Referral Accepted / Candidate Selected / 90-Day Milestone) with hardcoded amounts. **Update this constant** when the actual bonus policy is confirmed.

#### Data fetching
Uses `useFetch` hook (not manual useEffect):
```typescript
useFetch(API.referrals.list)           // my referrals
useFetch(isAdmin ? API.referrals.all : null)  // null skips the call
useFetch(API.referralRules.list)       // rules for the Rules tab
useFetch(`${API.branches.list}?status=active&page_size=100`)  // for branch display name
```

---

### 7. Referral Rules Settings — `app/dashboard/settings/referral-rules/page.tsx` (NEW)

Admin CRUD page for managing referral rules shown on the Referral page.

#### RuleForm component
Inline shared form (used for both Add and Edit). Fields: icon picker (14 Tabler icon options with live preview), title, order (number), description (textarea), is_active (checkbox).

#### List behaviour
Rules sorted by `order` ascending. Each row shows the icon, order badge, title, description, Hidden badge if `is_active: false`, Edit and Delete buttons.

Delete uses a two-step confirmation — first click shows inline Confirm/Cancel buttons; second click calls `DELETE API.referralRules.detail(id)`.

Only one rule can be in edit mode at a time (`editing` state is `number | "new" | null`). All Edit/Delete/Add buttons are disabled while any form is open (`isBusy = editing !== null`).

#### API calls
```typescript
POST   API.referralRules.create            // add new
PATCH  API.referralRules.detail(id)        // update
DELETE API.referralRules.detail(id)        // delete
```

---

### Key Files Changed (06 July 2026)

| File | Change |
|------|--------|
| `app/dashboard/settings/email-templates/page.tsx` | Full rewrite — added email branding card (live preview + inline edit form with logo upload), `BrandingForm` interface, `saveBranding()`/`cancelBranding()`/`handleLogoChange()`, `TYPE_META` cast fix |
| `lib/emailPreview.ts` | Existing file — `renderTemplateVars` and `buildEmailPreview` used by both the templates page and the interview list modals |
| `app/dashboard/interview-list/MarkCandidateModal.tsx` | Added `candidateVars()` with full snake_case + uppercase keys; `handleConfirm` passes `extra_context`; fixed `hasManualVars` check to use `.toLowerCase()`; `AUTO_KEYS` updated |
| `app/dashboard/interview-list/EditCandidateModal.tsx` | `handleSave` builds and passes `extra_context` with all interview detail fields |
| `app/dashboard/interview-list/_data.ts` | `setStatus` and `update` types extended with `extra_context?: Record<string, string>` |
| `app/dashboard/referrals/page.tsx` | **NEW** — full employee referral portal; three-tab layout (My Referrals / All Referrals / Referral Rules); Refer Someone modal; `useFetch`-based data loading |
| `app/dashboard/settings/referral-rules/page.tsx` | **NEW** — admin CRUD page for referral rules; inline add/edit form; two-step delete confirmation; icon picker with live preview |
| `lib/api/endpoints.ts` | Added `referrals` and `referralRules` endpoint groups |

---

### Notes for Next Developer

- **`extra_context` is sent but not yet used by the backend status-change email** — see §5 above for the one-line backend fix. Once applied, all template variables (`{position_applied}`, `{branch_name}`, `{interview_date}`, `{interview_mode_display}`) will resolve in sent emails. The preview already substitutes them correctly client-side.
- **Email template variable format is single-brace `{key}`** — matches the backend's `EmailTemplate.render()` method. Do not use `{{ key }}` (Django template style) or `%(key)s` in template bodies.
- **`candidateVars()` maps both cases** — `position_applied` AND `position` are both sent so templates using either key work. `interview_mode_display` is the human-readable label ("In-Person") while `interview_mode` is the raw value ("in_person").
- **Branding card PATCH uses FormData** — even when only updating text fields (no logo). This is required because the logo field is an `ImageField`; JSON cannot carry file uploads. The `clientApi` interceptor automatically removes `Content-Type` for FormData so the browser sets the correct multipart boundary.
- **`buildEmailPreview` mirrors the backend wrapper** — if the backend's `_company_email_wrapper` HTML structure changes, update `lib/emailPreview.ts` to match so the preview stays accurate.

---

## Session — Safura Samreen (07 July 2026)

**Branch:** `Frontend/Referral-Mails`

---

### 1. Birthday & Wishes System

#### `components/dashboard/BirthdayWidget.tsx` (NEW)

Dashboard widget shown on HR, Admin, and Manager dashboards. Fetches `GET /hrms/birthdays/` on mount and renders two sections — **Today's Birthdays** (red highlight, 🎂 avatar, shows age turning) and **Upcoming Birthdays** (within the next 30 days).

- Each row has a "Send Wish" button that opens `SendWishModal` with `preferredKey: "birthday"`
- After sending, button label changes to "Resend" (not locked — wishes can be sent multiple times)
- `sentIds: Set<string>` tracks which employees have been wished this session

Added to three dashboard pages:
- `app/dashboard/_components/HRDashboard.tsx` — replaced static birthday/anniversary sections
- `app/dashboard/_components/AdminDashboard.tsx` — added at top of right column
- `app/dashboard/_components/ManagerDashboard.tsx` — added at top of right column

#### `components/dashboard/SendWishModal.tsx` (NEW)

Shared wish email modal — same pattern as `MarkCandidateModal`. Used from both `BirthdayWidget` and `WishesTab`.

- Fetches all templates from `GET /settings/email-templates/` grouped by category with `<optgroup>`
- Pre-selects by `preferredKey` (e.g. `"birthday"` matches any template whose `name` contains `"birthday"`)
- `employeeVars()` builds a full context map covering all common aliases: `employee_name`, `full_name`, `first_name`, `last_name`, `fname`, `lname`, `email`, `department`, `designation`, `company_name`, `company` (and uppercase variants)
- POST body: `{ template_name, extra_context: normalizeExtraContext(employeeVars()) }`
- Uses `API.recruitment.sendEmail(employeeId)` — same endpoint as candidate emails

#### `app/dashboard/employees/[id]/_components/WishesTab.tsx` (REWRITTEN)

Replaced the old flat list with occasion-based cards: **Birthday**, **Work Anniversary**, **Other**. Each card shows a TODAY / IN X DAYS badge, the date, days away, years completed, and a Send Wish / Resend button that opens `SendWishModal`.

Props: `{ employeeId, employeeName, employeeEmail, dateOfBirth, dateOfJoining }`

Cards only show the occasion button when the date is set; Other Occasion always shows it.

---

### 2. Employee Profile — Date of Birth Save Fix

`app/dashboard/employees/[id]/page.tsx` — `onSave()` previously only sent employment fields in the PUT request. All profile fields are now merged into a single `PUT /employees/{id}/`:

```typescript
const employeePayload = {
  // employment fields ...
  date_of_birth: values.dateOfBirth || null,
  gender, marital_status, father_name, blood_group,
  current_address, permanent_address,
  highest_qualification, institution, year_of_passing, specialization,
  total_experience_years, previous_employer, previous_designation, leaving_reason,
  account_holder_name, account_type, account_number, ifsc_code, bank_name, bank_branch_name,
  emergency_name, emergency_relationship, emergency_phone, emergency_email,
};
await clientApi.put(API.employees.detail(id), employeePayload);
```

There is no `/employees/{id}/profile/` endpoint — everything goes to the detail endpoint.

---

### 3. Email Variable Substitution — Universal Fix

#### `lib/emailPreview.ts` — two new features

**`normalizeExtraContext(vars)`** — expands every key to three variants before sending to the backend:
```typescript
out[key]               = value;  // original
out[key.toLowerCase()] = value;  // lowercase
out[key.toUpperCase()] = value;  // uppercase
```
So a template using `{FNAME}`, `{fname}`, or `{Fname}` all resolve correctly regardless of how the template author wrote the tag.

**`renderTemplateVars` — case-insensitive** — builds a lowercase lookup map and uses a regex replace so `{FNAME}`, `{fname}`, `{Full_Name}` all match the same key in the preview:
```typescript
const lookup: Record<string, string> = {};
for (const [key, value] of Object.entries(vars)) {
  lookup[key.toLowerCase()] = value;
}
return text.replace(/\{([^}]+)\}/g, (_match, tag) => {
  const normalized = tag.toLowerCase();
  return normalized in lookup ? lookup[normalized] : `{${tag}}`;
});
```

**Gmail anti-clipping** — added invisible `&zwnj;` padding after the footer so Gmail does not collapse it behind the "Show trimmed content" (`...`) button:
```html
<div style="display:none;max-height:0;overflow:hidden;...">
  &zwnj;&nbsp;&zwnj;&nbsp;... (20 pairs)
</div>
```

#### Applied to all three email send points

| File | Change |
|------|--------|
| `components/dashboard/SendWishModal.tsx` | `extra_context: normalizeExtraContext(employeeVars())` |
| `app/dashboard/interview-list/MarkCandidateModal.tsx` | `extra_context: normalizeExtraContext(candidateVars())` |
| `app/dashboard/interview-list/EditCandidateModal.tsx` | `normalizeExtraContext({...})` assigned to `extraContext` const then passed |

---

### 4. API Endpoint Cleanup — `lib/api/endpoints.ts`

- Removed `employees.sendWish` — was a duplicate of `recruitment.sendEmail` pointing to the same URL
- Widened `recruitment.sendEmail` type: `(id: number | string)` — needed because employee IDs are strings (e.g. `"RSS00023"`) while candidate IDs are numbers
- Added `hrms: { birthdays: "/hrms/birthdays/" }`

---

### 5. Employees Page — Search & Pagination

`app/dashboard/employees/page.tsx` — previously fetched page 1 only (20 employees) with client-side filtering.

#### Server-side search
`fetchEmployees(q = "", p = 1)` now passes `?search=q&page=p`. Debounced 350ms via `searchRef`. Search input moved from the filter bar below stats to the **page header** alongside "Add Employee" — immediately visible without scrolling.

#### Pagination
```typescript
const [page,       setPage]       = useState(1);
const [totalPages, setTotalPages] = useState(1);
const [totalCount, setTotalCount] = useState(0);
```
Populated from `data.data.total_pages`, `data.data.count`, `data.data.page`.

Pagination bar renders below the table when `totalPages > 1`: "Showing 1–20 of 27 employees" + numbered page buttons + Prev/Next.

**Total Employees stat card** now uses `totalCount` from the backend (not `employees.length` which was capped at 20). Active / Onboarding / Departments are still computed from the current page — accurate only when there is one page or when filtering reduces to a single page.

#### Branch / Dept / Status filters
Remain client-side — they filter the results returned for the current page + search combination.

---

### 6. Interview List — Search Moved to Header

`app/dashboard/interview-list/page.tsx` — search input moved from the card header (below stats + alerts + info banner) to the **page header** `page-actions` toolbar alongside the branch filter. Status filter remains in the card header. Server-side search behaviour (350ms debounce, `?search=` param) unchanged.

---

### Key Files Changed (07 July 2026)

| File | Change |
|------|--------|
| `components/dashboard/BirthdayWidget.tsx` | **NEW** — birthday/anniversary dashboard widget; fetches `/hrms/birthdays/`; Send Wish → SendWishModal |
| `components/dashboard/SendWishModal.tsx` | **NEW** — shared wish email modal; all-template picker with optgroup; `normalizeExtraContext(employeeVars())` |
| `app/dashboard/employees/[id]/_components/WishesTab.tsx` | **REWRITTEN** — occasion cards (Birthday / Work Anniversary / Other); TODAY/IN X DAYS badges; opens SendWishModal |
| `app/dashboard/employees/[id]/page.tsx` | All profile fields merged into single `PUT /employees/{id}/`; `dateOfBirth` and `dateOfJoining` passed to WishesTab |
| `app/dashboard/_components/HRDashboard.tsx` | Replaced static birthday section with `<BirthdayWidget />` |
| `app/dashboard/_components/AdminDashboard.tsx` | Added `<BirthdayWidget />` |
| `app/dashboard/_components/ManagerDashboard.tsx` | Added `<BirthdayWidget />` |
| `lib/emailPreview.ts` | Added `normalizeExtraContext()`; made `renderTemplateVars` case-insensitive; added Gmail anti-clipping `&zwnj;` padding |
| `lib/api/endpoints.ts` | Removed `employees.sendWish`; widened `recruitment.sendEmail` to `number | string`; added `hrms.birthdays` |
| `app/dashboard/interview-list/MarkCandidateModal.tsx` | Wraps `candidateVars()` in `normalizeExtraContext()` |
| `app/dashboard/interview-list/EditCandidateModal.tsx` | Wraps interview context object in `normalizeExtraContext()` |
| `app/dashboard/employees/page.tsx` | Server-side search + pagination; search in page header; `totalCount` from backend |
| `app/dashboard/interview-list/page.tsx` | Search moved from card header to page header |

---

### Notes for Next Developer

- **`normalizeExtraContext` must wrap ALL `extra_context` objects before POST** — it is the single point that ensures `{FNAME}`, `{fname}`, and `{Fname}` all resolve. If a new email send point is added anywhere, import and wrap it the same way.
- **`renderTemplateVars` is now case-insensitive** — preview and backend will match any case. Do not add uppercase duplicates to `employeeVars()` or `candidateVars()`; the normaliser handles it.
- **`BirthdayWidget` fetches on mount, no refetch** — birthday data does not change during a session. No polling needed.
- **`SendWishModal` uses `recruitment.sendEmail(employeeId)`** — the endpoint is `/recruitment/candidates/{id}/send-email/`. It works for employee IDs (strings) because `sendEmail` was widened to `number | string`. The backend must accept an employee UUID/code at that route; verify this if wish emails start failing.
- **Employee total stat is accurate; Active/Onboarding/Departments are per-page only** — to fix, ask the backend to add a `GET /employees/stats/` endpoint returning `{ total, active, onboarding, departments }`, then call it in parallel with `fetchEmployees` (same pattern as `RECRUITMENT_API.stats()` in the interview list).
- **`BONUS_STAGES` in `referrals/page.tsx` is hardcoded** — update when actual bonus policy is confirmed.
