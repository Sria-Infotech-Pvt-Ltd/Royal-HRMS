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

## Session 16 — Rithwika (03 July 2026)

**Branch:** `frontend/Leavemanagement`                                                                                                                                                   
---

### 1. Leave Module — Pagination Envelope Bug (production crash fix)

`GET /leave/requests/` was switched to a paginated response (`{count, page, page_size, total_pages, results}`, the same envelope every other list endpoint uses) at some point, but three leave components were still written as if the endpoint returned a bare array. Once real data loaded, `requests`/`pending`/`l2pending`/`history`/`myRequests` held the paginated **object**, not an array, so `.map()`/`.filter()` threw `TypeError: ... is not a function` / `... is not iterable` at runtime.

Fixed by adding a `PaginatedResponse<T>` type to `app/dashboard/leave/_data.ts` (same shape already used in `types/attendance.ts` and `app/dashboard/approvals/page.tsx`) and reading `.results` everywhere:

- **`LeaveDashboard.tsx`** — `requests` (both the employee's own list and the approver's pending queue use the same endpoint) now typed `PaginatedResponse<LeaveRequest>`; introduced `requestList = requests?.results ?? []` and replaced every direct array read with it.
- **`LeaveApprovals.tsx`** — same fix for `pending`, `l2pending`, `history` (this was the component that actually crashed first, in the Approvals tab).
- **`ApplyLeaveForm.tsx`** — same latent bug in the "My Leave Requests" history table at the bottom of the Apply Leave form; fixed proactively since it hits the identical endpoint.

All three consumers of `API.leave.requests` are now consistent. No backend changes — the backend's pagination envelope is correct and matches every other list endpoint; the bug was purely stale frontend typing from before pagination was added.

---

### 2. Attendance — "View" Button on Absent Employees (UX fix)

**File:** `app/dashboard/attendance/_components/AttendanceTab.tsx`

The **View** button was `disabled` whenever a row had no `record_id` (absent employees have no `AttendanceRecord` for the day, so `record_id` is `null`). A disabled button fires no click handler, so users got zero feedback — it just looked broken/frozen.

Button is now always clickable:
```tsx
onClick={() => {
  if (r.record_id) {
    setViewingId(r.record_id);
  } else {
    showToast("No attendance record to view — employee was absent this day.", "info");
  }
}}
```

---

### 3. Attendance Import — Crash on Row Validation Errors

**Files:** `types/attendance.ts`, `app/dashboard/attendance/_components/ImportModal.tsx`

Reported error: `Objects are not valid as a React child (found: object with keys {date})`, thrown when opening the CSV import result's row-error table.

**Root cause (backend, not changed — frontend-only fix per instruction):** `services_hr_ops.py`'s `import_attendance_csv()` puts the raw DRF `ser.errors` dict (e.g. `{"date": ["Date has wrong format..."]}`) into each failed row's `errors` field instead of flattening it with the project's existing `first_error()` helper (used everywhere else in the codebase). The frontend type declared `ImportRowError.errors: string` and rendered it directly as `<td>{e.errors}</td>` — when a row failed only on its `date` column, React tried to render that object and crashed.

Fixed defensively on the frontend instead of touching the backend:
- `ImportRowError.errors` retyped to `string | Record<string, string[]>`.
- Added `formatRowError()` in `ImportModal.tsx` — passes strings through, flattens a field-errors object into `field: message` lines joined with `·`.
- `<td>{e.errors}</td>` → `<td>{formatRowError(e.errors)}</td>`.

> **Flagged, not fixed at the source:** the real fix is a one-line backend change (`'errors': first_error(ser.errors)` instead of `'errors': ser.errors`) to make the API actually match its documented contract. Worth doing whenever backend changes are back in scope — until then, any *other* frontend code that reads `ImportRowError.errors` as a plain string needs the same defensive handling.

---

### 4. Leave — Self-Approval Prevention

**Files:** `LeaveDashboard.tsx`, `LeaveApprovals.tsx`

Reported bug: an approver (manager/hr_admin) could see Approve/Reject buttons on their **own** leave request row in both the Leave Dashboard's "Pending Approvals" table and the Approvals tab's "Pending" table, and clicking them presumably no-ops or worse.

Fix: in both components' pending-approvals row rendering, compare the row against the logged-in user (`useCurrentUser()`) and swap the action buttons for a disabled "Not applicable" label when it's their own request:

```tsx
{r.employee_name === currentUser?.name ? (
  <span title="You cannot approve your own leave request.">Not applicable</span>
) : (
  /* existing Approve/Reject buttons */
)}
```

> **Known limitation — no stable ID to match on.** `LeaveRequest` only exposes `employee_name`/`employee_code` (the employee's HR code, e.g. `EMP001`), and `UserInfo` (`lib/auth.ts`) only carries `userId` (an internal UUID), `email`, and `name` — there's no field shared between the two that isn't a display value. Matched on `employee_name === currentUser.name` since both trace back to the same `full_name` field, but this breaks if two employees ever share an exact full name. A robust fix needs the leave request payload to expose a stable employee identifier (e.g. the employee's user UUID) that can be compared to `UserInfo.userId` — that's a backend serializer change, out of scope for this frontend-only pass.

---

### 5. Attendance — Audit History + Invalid Punch Actions (frontend wired ahead of backend)

Given a spec for three new backend endpoints, but **none of them exist yet** in `apps/attendance/` (checked `urls.py`, all views, all services, and all 14 migrations — confirmed absent). Per explicit instruction, implemented the frontend to the given contract anyway so it's ready the moment the backend ships; this will 404 until then.

**Endpoints wired (`lib/api/endpoints.ts`):**
```
attendance.recordAudit(id)          → GET  /attendance/records/<id>/audit/
attendance.invalidPunchAssign(id)   → POST /attendance/invalid-punches/<id>/assign/
attendance.invalidPunchDiscard(id)  → POST /attendance/invalid-punches/<id>/discard/
attendance.invalidPunchConvert(id)  → POST /attendance/invalid-punches/<id>/convert/
```

**Types added (`types/attendance.ts`):** `AttendanceAuditEntry`, `InvalidPunchAssignPayload`, `InvalidPunchDiscardPayload`, `InvalidPunchConvertPayload`.

**`AttendanceDetailDrawer.tsx`** — replaced the "not available yet" Audit Log placeholder (see Session 15 §2) with a real vertical timeline: fetches on drawer open, sorts newest-first, color-coded event badge (`CLOCK_IN`/`CORRECTION_APPROVED`/etc. mapped to badge classes, unknown events fall back to neutral), shows `performed_by` + `performed_at` + `action`, an `old_value → new_value` line only when both are non-empty, and italicized `remarks` when present.

**`InvalidPunchesTab.tsx`** — un-stubbed from the "Coming Soon" state (Session 15 §5) back to a real table; restored the previously-commented-out fetch/table code and added an **Actions** column with Assign / Convert / Discard buttons. Added an `onMutated` prop (same pattern as `AttendanceTab`) wired to `page.tsx`'s `refetchDashboard` so the "Invalid Punches" tab badge count updates after a resolution.

**New modal components** (`app/dashboard/attendance/_components/`):
- `AssignPunchModal.tsx` — HR-user dropdown sourced from the existing `API.employees.hrList` (`/employees/hrs/`, returns `{id, employee_id, full_name, ...}` per user — used `id` as `assigned_to` since that's the actual UUID, not the `employee_id` code).
- `DiscardPunchModal.tsx` — optional remarks textarea, 500-char limit.
- `ConvertPunchModal.tsx` — punch type select (IN/OUT) + `<input type="time">` for target time.

All three: show the response `message` via the existing `useToast` on error; on success, refetch the invalid-punches list, call `onMutated?.()`, and close.

> **Do not trust the exact response/error shapes until the backend actually ships** — they were inferred from the spec, not verified against a running endpoint.

---

### Key Files Changed / Created (03 July 2026)

| File | Change |
|------|--------|
| `app/dashboard/leave/_data.ts` | Added `PaginatedResponse<T>` |
| `app/dashboard/leave/_components/LeaveDashboard.tsx` | Fixed paginated-envelope bug; added self-approval guard |
| `app/dashboard/leave/_components/LeaveApprovals.tsx` | Fixed paginated-envelope bug; added self-approval guard |
| `app/dashboard/leave/_components/ApplyLeaveForm.tsx` | Fixed paginated-envelope bug (proactive, same endpoint) |
| `app/dashboard/attendance/_components/AttendanceTab.tsx` | "View" button on absent-employee rows now shows an info toast instead of being disabled |
| `types/attendance.ts` | `ImportRowError.errors` retyped to `string \| Record<string, string[]>`; added `AttendanceAuditEntry`, `InvalidPunchAssignPayload`, `InvalidPunchDiscardPayload`, `InvalidPunchConvertPayload` |
| `app/dashboard/attendance/_components/ImportModal.tsx` | Added `formatRowError()` to safely render string-or-dict row errors |
| `lib/api/endpoints.ts` | Added `attendance.recordAudit`, `invalidPunchAssign`, `invalidPunchDiscard`, `invalidPunchConvert` |
| `app/dashboard/attendance/_components/AttendanceDetailDrawer.tsx` | Audit Log placeholder replaced with a real fetched timeline |
| `app/dashboard/attendance/_components/InvalidPunchesTab.tsx` | Un-stubbed; real table + Actions column (Assign/Convert/Discard); added `onMutated` prop |
| `app/dashboard/attendance/_components/AssignPunchModal.tsx` | **NEW** |
| `app/dashboard/attendance/_components/DiscardPunchModal.tsx` | **NEW** |
| `app/dashboard/attendance/_components/ConvertPunchModal.tsx` | **NEW** |
| `app/dashboard/attendance/page.tsx` | Passes `refetchDashboard` into `InvalidPunchesTab` as `onMutated` |

---

### Notes for Next Developer

- **Three attendance endpoints are frontend-ready but backend-absent**: `GET /attendance/records/<id>/audit/`, `POST /attendance/invalid-punches/<id>/{assign,discard,convert}/`. Build these next — the frontend contract (request/response shapes) is already committed in `types/attendance.ts`, verify it matches whatever the backend actually implements before calling this "done."
- **Invalid Punches is live again** (Session 15 §5's "Coming Soon" state is gone) — but every action button will 404 until the three endpoints above exist.
- **The real fix for the Import row-error crash is still pending on the backend** — `services_hr_ops.py:145` should use `first_error(ser.errors)` instead of raw `ser.errors`, matching every other `error()` call in the codebase. The frontend defensive fix (§3 above) means it won't crash either way, but the backend contract is still technically wrong.
- **Self-approval guard matches on employee full name, not a stable ID** (§4) — revisit if the backend ever adds a comparable employee/user identifier to the leave request payload.
- **Leave module's pagination bug (§1) suggests checking other older leave/approvals pages** for the same "written before pagination was added" pattern if similar crashes turn up elsewhere.

---

## Session 17 — Rithwika (06 July 2026)

**Branch:** `frontend/Leavemanagement`

---

### 1. HR/Manager Approval Queue — `scope=team`, No Hardcoded Status

`LeaveDashboard.tsx` (Dashboard tab, approver view), `LeaveApprovals.tsx` (Approvals tab), and `TeamApprovalsSection` in `app/dashboard/approvals/page.tsx` all now call:

```
GET /leave/requests/?scope=team
```

**One URL, two results** — the backend returns `pending` requests for managers and `l2_pending` for HR automatically, based on the caller's role. `status=pending`/`status=l2_pending` must never be hardcoded on this call again; per an explicit backend contract, the server already enforces it. `LeaveApprovals.tsx`'s history sub-tab is the one exception — `?scope=team&status=approved,rejected,cancelled` stays explicit there since that's a user-selected filter, not an auto-enforced queue state.

### 2. Employee's Own "My Leave Requests" — Bare Endpoint, Every Role

After several rounds of back-and-forth on this, the final, correct contract is:

```
GET /leave/requests/          ← own requests, NO scope param, NO status/year filter
```

used identically for **every role** — employee, manager, and HR — in `ApplyLeaveForm.tsx`. This matters because managers and HR also apply for their own leave through this same screen; routing them through `scope=own` or any role-based branching would be redundant at best and wrong the moment the backend's default-scope logic changes.

> **Manager applying for their own leave** routes through the same `EmployeeApprovalOverride`/`ApprovalWorkflowRule` resolution as anyone else — L1 goes to *their own* `reporting_manager` (not their direct reports), L2 to their assigned `hr`. A senior manager with no `reporting_manager` set has no valid L1 approver except the `system_admin` catch-all — worth an override if that gap matters.

**`LeaveDashboard.tsx`'s Dashboard tab is intentionally different for approvers** — it shows the "Pending Approvals" queue (other people's requests needing action), never the approver's own submitted leave. Confirmed with the user this stays as-is; their own requests only show on the "Apply Leave" tab.

### 3. Full Request Detail — Click Any Row, Not Just the Status

Built `LeaveRequestDetailModal.tsx` (new): on open, fetches the individual request fresh via `GET /leave/requests/<id>/` (`useFetch`), rendering the row's already-known data immediately and swapping in the fresh response once it resolves (no blank flash, and reflects any change since the list loaded). Shows:

- Employee name/code/dept/branch
- Dates, days, reason, status badge
- **Approval Flow** — a `DecisionRow` per level (Manager, HR) with approver name, decision (colour-coded dot), remarks in quotes, and timestamp. This is what surfaces *why* a request was rejected — `approved_by`/`approved_at` (see §4) can't carry that, only a name and a timestamp.
- Handover/contact info, and a document link when present

**Every leave table restructured** (`ApplyLeaveForm.tsx`, both branches of `LeaveDashboard.tsx`, `LeaveApprovals.tsx`, both sections of `approvals/page.tsx`) so the **entire `<tr>`** opens this modal — not just the status cell. Approve/Reject/Cancel moved out of per-row buttons into the modal's footer, gated by `can_approve`/`can_cancel`:

```
(r.can_approve ?? true) && onApprove   /* approval-queue context only — onApprove is never passed to an own-requests view */
(r.can_cancel ?? statusIsPendingOrL2Pending) && onCancelRequest
```

The `?? true` / status-based fallback exists because this repo's backend doesn't return `can_approve`/`can_cancel` yet — once it does, the real field takes over automatically with zero frontend changes needed. `TeamApprovalsSection`'s Approve/Reject still opens the existing `ApprovalModal` (template-selection support) rather than duplicating a simpler reject flow.

`StatusCell.tsx` is back to a plain, non-interactive badge — the row owns the click now.

### 4. `approved_by` / `approved_at` Fields

Added to `LeaveRequest`. The "Approver" column in list tables and a compact line in the detail modal read these two fields directly — **no frontend logic picks between `l1_approver_name`/`l2_approver_name` based on status anymore**, per an explicit backend contract change. The granular per-level "Approval Flow" breakdown (§3) was deliberately kept, since it's a different, richer feature (remarks/audit trail) that these two fields can't replace.

### 5. Status Labels

`STATUS_LABEL` in `_data.ts`:

```
pending:    "Pending Manager Approval"
l2_pending: "Pending HR Approval"
```

Applied everywhere via this single map — including the "My Leave Requests" filter chips, which used to have their own separate, unaligned text ("Pending", "Pending L2"). Chips are now generated directly from `STATUS_LABEL` so they can't drift out of sync with the table badges again.

### 6. `clientApi.ts` — Root-Cause Fix for Swallowed Error Messages

Found a **systemic bug**, not limited to leave: `normaliseError()` in `lib/clientApi.ts` ran on every non-401 error and returned a flat `{ message, status, data }` object with **no `.response` property**. Every `catch` block across the whole app was written expecting the raw axios shape (`err.response.data.message`), so that read always silently returned `undefined` and fell back to a generic message — regardless of what the backend actually said.

Fixed at the one shared location instead of touching every consumer:

```typescript
// lib/clientApi.ts — normaliseError()
return { message, status, data, response: { data: { message, data } } };
```

This means every existing `err.response?.data?.message` read across the entire app (leave, expenses, attendance, onboarding, etc.) started working correctly with this one change — no other files needed touching for this part.

### 7. Duplicate-Leave-Request Error — Toast, Not Inline

With §6 fixed, the backend's `"You already have a leave request for the selected date(s)..."` message now actually reaches the frontend. Converted all three leave-creation forms to show it as a **toast** instead of an inline banner:

- `ApplyLeaveForm.tsx` — removed the `submitErr` state/banner entirely, replaced with `showToast(msg, "error")`
- `my-requests/page.tsx`'s `NewLeaveModal` — added `useToast`; API errors → toast, client-side "required fields" validation stays inline
- `approvals/page.tsx`'s `NewLeaveModal` — same split

### 8. System Admin — Branch Filter + Pagination

`LeaveDashboard.tsx`'s approver query now supports real server-side filtering and paging:

```
GET /leave/requests/?scope=team&branch=<name>&page=<n>
```

- Replaced the old `BranchDropdown.tsx` (hardcoded 6-branch list, multi-select, client-side `.filter()` after fetching everything) with the **already-existing shared** `components/BranchFilterSelect.tsx` (same component already used by Attendance/OT/Corrections) — fetches real branches from `GET /api/branches/`. `BranchDropdown.tsx` was deleted as dead code once nothing referenced it.
- Single-select; empty string = "All Branches" = no `branch` param.
- Selecting a branch resets to page 1.
- Prev/Next + "Page X of Y" footer, shown when `total_pages > 1` — same pattern as `AttendanceTab.tsx`.
- Branch filter only renders for `system_admin` — HR/manager are already branch-scoped server-side and don't need it.

> **Known discrepancy, not resolved**: the backend spec's example URL for this feature included `&status=pending,l2_pending`, which directly conflicts with §1's "never hardcode status" rule. Kept the standing no-hardcode behavior and treated the status in that example as incidental. Flag to the backend/spec owner if system_admin is actually supposed to get an explicit status param.

---

### Key Files Changed / Created (06 July 2026)

| File | Change |
|------|--------|
| `app/dashboard/leave/_data.ts` | `STATUS_LABEL` updated; added `approved_by`/`approved_at`, `can_approve`/`can_cancel` to `LeaveRequest` |
| `app/dashboard/leave/_components/LeaveRequestDetailModal.tsx` | **NEW** — full request detail, fetched live, houses Approve/Reject/Cancel |
| `app/dashboard/leave/_components/StatusCell.tsx` | Reverted to a plain badge (no click/modal logic — the row owns that now) |
| `app/dashboard/leave/_components/ApplyLeaveForm.tsx` | Bare endpoint for own requests (all roles); row-click detail modal; Cancel moved into modal; toast on submit error; filter chips derived from `STATUS_LABEL` |
| `app/dashboard/leave/_components/LeaveDashboard.tsx` | `scope=team` (no status) for approvers; row-click detail modal; Approve/Reject moved into modal; branch (`branch` prop, was `selectedBranches`) + pagination |
| `app/dashboard/leave/_components/LeaveApprovals.tsx` | Collapsed two status-filtered fetches into one `?scope=team` call; row-click detail modal; Approve/Reject moved into modal |
| `app/dashboard/leave/_client.tsx` | Branch state single-select (`branch: string`); fetches real branches; uses shared `BranchFilterSelect` |
| `app/dashboard/leave/_components/BranchDropdown.tsx` | **DELETED** — dead code, superseded by shared `BranchFilterSelect` |
| `app/dashboard/approvals/page.tsx` | Replaced local mismatched `LeaveRequest` type with the shared one from `leave/_data.ts` (fixed several already-broken columns — see Notes); row-click detail modal on both leave tables; `NewLeaveModal` fixed to send `duration`/`start_date`/`end_date` instead of the wrong field names; toast on submit error |
| `lib/clientApi.ts` | `normaliseError()` now preserves a `response.data.message`-compatible shape — root-cause fix for app-wide swallowed error messages |
| `app/dashboard/my-requests/page.tsx` | Added `useToast`; API submit errors → toast |
| `components/BranchFilterSelect.tsx` | No change — reused as-is from the attendance module |

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

- **`LeaveApprovals.tsx` has no branch filter or pagination** — only `LeaveDashboard.tsx`'s Dashboard-tab queue got that treatment this session. If system_admin uses the Approvals tab as their main queue, it still loads everything on one page.
- **`LeaveAnalytics.tsx`** still calls `/leave/stats/` without an explicit `scope=team` for approvers (relies on backend default same-as-team behavior). Never explicitly requested, left as-is.
- **`my-requests/page.tsx`'s `NewLeaveModal` still sends `from_date`/`to_date`** instead of `start_date`/`end_date`/`duration` — the identical bug was fixed in `approvals/page.tsx`'s equivalent modal this session, but this one was only flagged, not fixed. Its submissions are very likely failing serializer validation server-side.
- **`LeaveTypes.tsx`** is still dead mock code (fabricated `SEED` data, wrong shape vs. the real `LeavePolicy` type), not linked into any tab, not wired to the real `/leave/policy/` CRUD endpoints that already exist on the backend.
- **Duplicated reject-modal logic** — `LeaveDashboard.tsx` and `LeaveApprovals.tsx` each maintain their own separate reject-reason modal state/UI instead of sharing one.
- **File length**: `ApplyLeaveForm.tsx` and `LeaveDashboard.tsx` both exceed this repo's own 200-line component guideline; `backend/apps/hrms/views/leave.py` exceeds the 300-line file guideline. Flagged repeatedly, never split.
- **Backend items observed but out of frontend scope** (status depends on whichever backend branch is authoritative — this repo's local copy may be stale): a `Q()`/`F()` bug in `_deduct_balance_safe` that would raise `TypeError` on every balance deduction; `leave.approve` is one overloaded permission gating approve + balance-adjust + policy-edit; custom leave types created via the policy API still can't be selected when applying (`LeaveRequestCreateSerializer` only accepts the fixed six); no server-side enforcement that a required document was actually attached for sick/maternity/paternity leave.
- **`can_approve`/`can_cancel` fallbacks** (§3) are silently doing real work right now — if the backend ships these fields with different semantics than assumed (e.g. `can_approve: false` meaning something other than "not your own request"), every approval queue's buttons need re-checking.

---

## Session 18 — Rithwika (08 July 2026)

**Branch:** `frontend/Leavemanagement`

---

### 1. Dashboard "My Leave Requests" — Corrected Location After a False Start

First attempt put a new "Pending Approvals / My Leave Requests" tabbed card on the **main app Dashboard** (`ManagerDashboard.tsx`/`HRDashboard.tsx`, the `/dashboard` homepage) — wrong location. The user's "Dashboard" meant the **Dashboard tab inside Leave Management** (`/dashboard/leave`, the tab `LeaveDashboard.tsx` already renders for approvers). Reverted the homepage change completely and deleted the misplaced `LeaveRequestsCard.tsx`.

Correct fix, in `LeaveDashboard.tsx`'s approver layout only:

- The single "Pending Approvals" card header is now two tab buttons: **Pending Approvals** (existing `scope=team` table, unchanged) and **My Leave Requests** (the approver's *own* submitted leave — fetched with no `scope` param, since `scope=team` explicitly excludes the approver's own rows server-side).
- Detail modal's `onApprove`/`onReject` only show on the Pending tab; `onCancelRequest` only shows on the My Leave Requests tab — a manager can't approve/reject their own request (backend already blocks it; this just keeps the button from appearing at all).
- This is also why the **history table was removed from `ApplyLeaveForm.tsx`** ("My Leave Requests" section at the bottom) — that data now lives on this Dashboard tab instead, per explicit instruction not to show it in both places.

### 2. Notification Bell — Built, Debugged, One Feature Reverted

Built from a full frontend spec (endpoints, types, hook, component) that assumed a live `/api/notifications/` backend. **It didn't exist in this repo** — confirmed via `config/urls.py`, no `Notification` model anywhere. Root cause of the confusion: this frontend's real backend runs at `NEXT_PUBLIC_API_URL` (`http://192.168.0.174:8000` per `.env`/`.env.local`), a separate deployed server — the local `backend/` folder here is not guaranteed to match what's actually running there. Built the frontend to the given contract anyway (same "ready ahead of backend" pattern as Session 16 §5), then the real backend turned out to already exist on that live server once tested.

**Files (all new unless noted):**
- `lib/api/endpoints.ts` — `notifications.{list, unreadCount, markRead(id), markAllRead}`
- `types/notifications.ts` — `Notification`, `NotificationListResponse`, `UnreadCountResponse`
- `hooks/useNotifications.ts` — polls unread count every 60s; `fetchNotifications`/`markRead`/`markAllRead`, all fail silently on error so a missing/404 backend never breaks the UI
- `components/NotificationBell.tsx` — bell + red badge (hidden at 0, capped "99+"), dropdown panel, click-outside-to-close, row click → mark read → `router.push` via a `MODULE_ROUTES` map
- `components/dashboard/DashboardShell.tsx` — swapped the old hardcoded, non-functional bell (static red dot, no handler) for `<NotificationBell />`

**Bug found and fixed once real data existed:** the badge count was read from a separate `unread_count` field in the list response, while each row's dot color came from that row's own `is_read` — these could disagree. Fixed by deriving the badge count directly from the loaded rows (`results.filter(n => !n.is_read).length`) so it can never drift from what the panel actually shows.

**`markAllRead` now surfaces the backend's own message** via the existing `useToast` (both success and error paths) instead of just updating state silently — e.g. shows *"All notifications marked as read."* verbatim.

> **Reverted**: a "remove/erase notification" feature (DELETE endpoint guess, `deleteNotification` in the hook, an × button per row) was built, then fully reverted per instruction — not part of the current spec. All three files are back to their pre-delete state; confirmed via `tsc`/`eslint` clean.

**Known gap, not a frontend bug**: an employee submitting a leave request does not appear to notify the manager — only the employee gets a self-confirmation. The notification *mechanism* (badge/list rendering) is generic and works for any row the backend sends; there's just no evidence the backend creates that specific row today. Needs verification directly against the live server (DevTools Network tab), not something fixable from the frontend.

### 3. Settings → Leave Management — New "Leave Policy" Tab

`app/dashboard/settings/leave-policy/page.tsx` now has **three** tabs, in this exact order: **Leave Types** (renamed from "Leave Policy" — same component, `PolicyTab.tsx`, untouched otherwise, renamed only to disambiguate from the new tab), **Leave Policy** (new), **Credit Rules** (untouched).

New files:
- `app/dashboard/settings/leave-policy/_components/LeavePoliciesTab.tsx` — leave-type dropdown (from the same `GET /leave/policy/` list `PolicyTab.tsx` already uses — no second fetch), sections for Application Rules, Holiday & Week-off Rules, Documentation Rules, Leave Restrictions, Additional Rules; dependent fields only render when their parent toggle is on; Save/Discard footer.
- `app/dashboard/settings/leave-policy/_components/EligibilitySection.tsx` — split out since it needs its own data (branches/departments/designations fetched for real; employment types are a static list — no such concept exists anywhere in `accounts.models`, confirmed by search).
- `components/ToggleSwitch.tsx` — **new shared component**, promoted from the one-off inline `ToggleSwitch` in `BranchManagement.tsx`, per that file's own note from Session 15 ("if a second toggle is needed anywhere else, promote it to `components/ToggleSwitch.tsx`"). `BranchManagement.tsx` itself left untouched — its local copy still duplicates this, out of scope to refactor here.

**First draft used invented field names and an invented endpoint** (`/leave/policy-rules/<type>/`) before the real API contract was given. Once given, it turned out the real backend just added dozens of fields directly onto the *existing* `LeavePolicy` resource — same `GET /leave/policy/` and `PUT /leave/policy/<type>/` that Leave Types already uses. Rewrote to match exactly:

- Field names corrected wholesale (`minimum_leave_duration`, `maximum_future_days`, `convert_to_lop`, `allow_leave_cancellation`, `allow_probation_leave`, `allow_leave_combination`, etc. — every guessed name was wrong).
- Removed two invented sandwich-leave sub-toggles ("Apply on Holidays"/"on Week-offs") — the real API has one flag, `sandwich_leave_enabled`.
- Gender dropdown fixed to exactly `all`/`male`/`female` (no `other` — different from the general user-profile gender field, which does have one).
- Selecting a leave type no longer triggers a second network call — the full rule set is already in the list response, so it's just a lookup by `leave_type`.
- PUT payload sends **only** the rule fields — never `annual_days`/`can_carry_forward`/`policy_note`/`is_active`, which stay exclusively owned by the Leave Types tab.
- An `eslint-disable` used in the first draft was removed in favor of actually fixing the effect's dependencies (depend on `policies` directly, not a derived `list` array) — zero suppressions, zero warnings.

> **Not implemented, flagged instead of guessed**: an "Approval Workflow" section was mentioned in the original prose spec but had zero fields listed for it anywhere in the text. Confirmed a separate, already-existing settings page (`/dashboard/settings/approval-rules`, wired to `GET/PATCH /settings/approval-rules/`) already owns this concern — left alone rather than duplicating it.
>
> **"Delete Custom Leave Type"** — the backend endpoint (`DELETE /leave/policy/<type>/`) was documented in the API spec, but no UI exists anywhere for it (`PolicyTab.tsx` only has Create + Edit). Not built this session since it means modifying the Leave Types tab, which was explicitly off-limits for this task.

### 4. Sandwich Leave — Day-Counter Fix

`app/dashboard/leave/_data.ts`:
- `LeavePolicy` gained `sandwich_leave_enabled: boolean` (API already returned it; just wasn't typed).
- `calcWorkingDays(from, to, dur, sandwichEnabled = false)` — new 4th param. When `true`, counts **every** calendar day in the range (no weekend skip at all), matching the backend's own sandwich-leave day count regardless of which days are configured as week-offs. Default `false` preserves all existing call sites/behavior — confirmed via search this function has exactly one caller.

`ApplyLeaveForm.tsx` — `sandwichEnabled` is read off the already-fetched `policy` for the selected leave type (no new fetch) and threaded into the `workDays` `useMemo`'s deps.

### 5. LOP (Loss of Pay) Summary UI

Backend now returns `lop_days` on every leave request and validates against `convert_to_lop` on submission. Frontend changes:

`app/dashboard/leave/_data.ts` — added `convert_to_lop: boolean` to `LeavePolicy`, `lop_days: number` to `LeaveRequest`.

`ApplyLeaveForm.tsx` — the old binary `overLimit` became three states:
```
exceedsBalance = workDays > available
overLimit      = exceedsBalance && !convertToLop   // still blocks submission
lopDays        = exceedsBalance && convertToLop ? workDays - available : 0   // no longer blocks
```
When `lopDays > 0`, the summary bar turns amber ("Xd will be LOP") and a breakdown card appears (Available / Requested / Used / LOP Days) plus the exact info banner text specified ("...will be treated as Leave Without Pay (LOP) if this request is approved.").

`LeaveRequestDetailModal.tsx` — shared by both the employee's own history and the approver's queue, so one change covered both required views: when `lop_days > 0`, shows the split (`{Leave Type}: X days` / `LOP: Y days` / `Total: Z days`) instead of a flat total.

---

### Key Files Changed / Created (08 July 2026)

| File | Change |
|------|--------|
| `app/dashboard/leave/_components/LeaveDashboard.tsx` | Approver layout: card header replaced with Pending Approvals / My Leave Requests tabs; own-requests table added; detail modal props gated per tab |
| `app/dashboard/leave/_components/ApplyLeaveForm.tsx` | Removed "My Leave Requests" history table (moved to Dashboard tab, see §1); sandwich-aware `workDays`; three-state balance/LOP summary + breakdown card |
| `app/dashboard/leave/_components/LeaveRequestDetailModal.tsx` | Shows Leave Type/LOP/Total split when `lop_days > 0` |
| `app/dashboard/leave/_data.ts` | Added `sandwich_leave_enabled`, `convert_to_lop` to `LeavePolicy`; `lop_days` to `LeaveRequest`; `calcWorkingDays` gained `sandwichEnabled` param |
| `lib/api/endpoints.ts` | Added `notifications.{list, unreadCount, markRead, markAllRead}` |
| `types/notifications.ts` | **NEW** |
| `hooks/useNotifications.ts` | **NEW** |
| `components/NotificationBell.tsx` | **NEW** |
| `components/dashboard/DashboardShell.tsx` | Hardcoded bell replaced with `<NotificationBell />` |
| `components/ToggleSwitch.tsx` | **NEW** — promoted shared component (see §3) |
| `app/dashboard/settings/leave-policy/page.tsx` | Third tab added ("Leave Policy"); first tab relabeled "Leave Types" (same component) |
| `app/dashboard/settings/leave-policy/_components/LeavePoliciesTab.tsx` | **NEW** |
| `app/dashboard/settings/leave-policy/_components/EligibilitySection.tsx` | **NEW** |
| `app/dashboard/_components/ManagerDashboard.tsx`, `HRDashboard.tsx` | Reverted to original — see §1's false start |

---

### Notes for Next Developer

- **Manager doesn't get notified when an employee submits leave** (§2) — needs verification against the live backend, not a frontend fix.
- **"Delete Custom Leave Type" has a documented backend endpoint and zero UI** (§3) — needs a trash icon in `PolicyTab.tsx`, deliberately not added this session (out of scope).
- **No Holiday calendar model exists anywhere in the backend** — undercuts two Leave Policy toggles now live in the UI: "Count Holidays as Leave" and "Sandwich Leave Enabled" (sandwich logic needs to know which days are holidays) have no real data source to compute against yet.
- **Custom leave types still can't be applied for** — `LeaveRequestCreateSerializer` only accepts the six built-in types (Session 17 note, re-confirmed this session — unchanged).
- **Re-confirmed, still unfixed**: the `Q()`/`F()` bug in `_deduct_balance_safe` (`backend/apps/hrms/views/leave.py`) — `Q('used_days') + float(...)` should be `F('used_days') + float(...)`. This runs on every final leave approval for a non-LWP type. Same caveat as before: verify against the actually-deployed server, not just this local file.
- **Re-confirmed, still unfixed**: `my-requests/page.tsx`'s "New Leave Request" modal still sends `from_date`/`to_date` instead of `start_date`/`end_date`/`duration` — every submission through this specific page fails validation.
- **Re-confirmed, still dead code**: `LeaveTypes.tsx` — fabricated `SEED` data, confirmed not imported anywhere in `app/`.
- **`CreditTab.tsx`'s "Accrual Rules" table is still pure local mock state** ("Automation coming soon") — only the "Credit All Employees" button above it is real.
- **`LeavePoliciesTab.tsx` is ~270 lines**, over this repo's own 200-line component guideline — same standing exception as `ApplyLeaveForm.tsx`/`LeaveDashboard.tsx`, flagged rather than silently ignored.

---

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

---

## Session — Safura Samreen (08 July 2026)

**Branch:** `Fix/Login_Send`

---

### 1. Birthday Widget — "Send All" Button

#### `components/dashboard/BirthdayWidget.tsx`

Added a **Send All** button to the Today's Birthdays card header. The button only renders when `todayList.length > 0` and sits alongside the existing `X today` badge.

- `showSendAll: boolean` state gates the modal
- On click → opens `SendAllBirthdayModal` with the full `todayList` as `entries`
- On completion → all successfully sent employee IDs are merged into `sentIds` so their individual row buttons flip to "Resend"
- `BirthdayEntry` interface promoted from `interface` to `export interface` so `SendAllBirthdayModal` can import it

#### `components/dashboard/SendAllBirthdayModal.tsx` (NEW)

Shared "send to everyone" variant of `SendWishModal`. Kept in a separate file to stay within the 200-line component guideline.

**Flow:**
1. Fetches all active email templates (`GET /settings/email-templates/`) and company info (`GET /settings/company/`) on mount — same two calls as `SendWishModal`
2. Pre-selects the first template whose `name` contains `"birthday"`; falls back to the first active template
3. Shows a recipients summary (`alert-info`) listing all employee names
4. Template picker dropdown — disabled once sending starts
5. **Send to All** button triggers `handleSendAll()`:
   - Iterates `entries` sequentially with `for...of`
   - Each iteration calls `POST /recruitment/candidates/{employee_id}/send-email/` with `{ template_name, extra_context: normalizeExtraContext(buildVars(entry)) }`
   - Progress bar updates after each send: `done / total`
   - Failed names are collected in `errors[]`
6. On finish — calls `onAllSent(sentIds)` then closes automatically if all succeeded; if any failed, stays open and shows an error summary

**`buildVars(entry)`** — mirrors `employeeVars()` from `SendWishModal` but takes a `BirthdayEntry` object instead of component props. Sends the same full alias set: `employee_name`, `full_name`, `first_name`, `last_name`, `fname`, `lname`, `department`, `designation`, `company_name`, `company`, plus uppercase variants. Wrapped with `normalizeExtraContext()` before POST.

**UX details:**
- Overlay click is blocked while sending is in progress (`!sending` guard on the backdrop click handler)
- Close button hidden during sending
- Footer shows Cancel + "Send to All N" before start; switches to a single "Close" once done

---

### 2. Referral Stats — Use Backend `data.stats`

**File:** `app/dashboard/referrals/page.tsx`

The stat cards (Total Referred / In Pipeline / Selected / Converted) were previously computed from the local `myReferrals` array — which is page-scoped and does not reflect all-time totals for admins.

#### What changed

Added `ReferralListResponse` and `ReferralStats` interfaces:
```typescript
interface ReferralStats {
  total_referred: number;
  in_pipeline:    number;
  selected:       number;
  converted:      number;
}

interface ReferralListResponse {
  results:     Candidate[];
  count:       number;
  stats:       ReferralStats;
}
```

Both `useFetch` calls updated to use `ReferralListResponse`:
```typescript
useFetch<ReferralListResponse>(API.referrals.list)
useFetch<ReferralListResponse>(isAdmin ? API.referrals.all : null)
```

`backendStats` reads `allData?.stats ?? myData?.stats`:
- For admins: `allData.stats` provides org-wide totals from `GET /recruitment/referrals/all/`
- For non-admins: falls back to `myData.stats` if the list endpoint provides it
- If neither has stats: falls back to computing from `myReferrals` (original behaviour)

```typescript
const backendStats = allData?.stats ?? myData?.stats;
const statCards = [
  { label: "Total Referred", value: backendStats?.total_referred ?? myReferrals.length, ... },
  { label: "In Pipeline",    value: backendStats?.in_pipeline    ?? myReferrals.filter(...).length, ... },
  { label: "Selected",       value: backendStats?.selected       ?? myReferrals.filter(...).length, ... },
  { label: "Converted",      value: backendStats?.converted      ?? myReferrals.filter(...).length, ... },
];
```

---

### 3. Login Error — Dismiss on Input Focus

**File:** `app/login/page.tsx`

The error banner was permanent — it stayed until the user entered correct credentials or refreshed the page.

#### What changed

Removed the auto-dismiss timer entirely. Added `onFocus={() => setError("")}` to both inputs:
- **Email input** — focusing the email field clears the error
- **Password input** — focusing the password field clears the error

This means the error disappears the moment the user clicks or tabs into either field to try again — natural UX, no arbitrary timeout.

`useRef` import removed (was only needed for the timer). No other changes to the login flow.

---

### Key Files Changed (08 July 2026)

| File | Change |
|------|--------|
| `components/dashboard/BirthdayWidget.tsx` | `BirthdayEntry` exported; `showSendAll` state; "Send All" button in Today's card header; `SendAllBirthdayModal` rendered with `onAllSent` callback |
| `components/dashboard/SendAllBirthdayModal.tsx` | **NEW** — batch wish sender; sequential send loop; live progress bar; error summary; `buildVars()` mirrors `SendWishModal.employeeVars()` |
| `app/dashboard/referrals/page.tsx` | `ReferralStats` + `ReferralListResponse` interfaces; both `useFetch` calls typed; `backendStats = allData?.stats ?? myData?.stats`; stat cards use backend values with computed fallbacks |
| `app/login/page.tsx` | `onFocus={() => setError("")}` on email and password inputs; removed timer ref and `setTimeout`; `useRef` import removed |`n`n---`n`n## Session 19 — Rithwika (08 July 2026)

**Branch:** `frontend/08-07`

---

### 1. Settings → Holiday Calendar — Wired to Real Backend

`app/dashboard/settings/holiday-calendar/page.tsx` was pure mock (hardcoded `SEED` array, all CRUD just mutated local state). Given a real API contract (`GET/POST /leave/holidays/`, `GET/PATCH/DELETE /leave/holidays/<id>/`), rebuilt fully against it.

- **`lib/api/endpoints.ts`** — added `leave.holidays` / `leave.holidayDetail(id)`.
- **`types/holidays.ts`** (new) — `Holiday`, `HolidayListData`, `HolidayFormPayload` typed to the real response/request shapes (`holiday_type_display`, `mandatory_optional`, `branch`/`branch_name`, etc.).
- Split into 5 files to stay under this repo's 200/300-line guidelines (a single-file version would have been ~480 lines):
  - `page.tsx` (278 lines) — state, fetching, filters
  - `_components/HolidayFormModal.tsx` — Add/Edit
  - `_components/HolidayViewModal.tsx` — View
  - `_components/DeleteHolidayModal.tsx` — Delete confirm
  - `_components/HolidayListView.tsx` / `HolidayCalendarView.tsx` — List table / calendar grid
- Add/Edit/Delete/status-toggle all call the real endpoints via `clientApi`, surfacing the backend's own `message` through `useToast` (same pattern as every other CRUD page this branch touched).
- Branch dropdown (top filter + Add/Edit form) sourced from real `GET /branch/branches/`, not a hardcoded list.

---

### 2. Holiday Calendar — List/Calendar Filtering Fix

Two bugs found after the initial build, both in `page.tsx`:

**a) List view filters were client-side-only, not hitting the server.** Given contract: `?year=&month=&type=&optional=true`. Fixed by splitting into two fetches — `yearData` (fetched once per year, feeds Calendar view + tab-count stats, so navigating months never re-calls the API) and `listData` (built from a `useMemo`'d query string including `month`/`type`/`optional`, refetched whenever those filters change). Branch/search stay client-side on top of the server-filtered list since they aren't part of the given query contract.

**b) Month dropdown and Calendar view were disconnected.** Picking "August" in the "All Months" dropdown updated the List view correctly but the Calendar view stayed on January — `fMonth` (dropdown) and `calMonth` (calendar's displayed month) were two independent states with nothing syncing them. Fixed with `changeFMonth`/`changeCalMonth` wrapper handlers that keep both in sync in either direction (dropdown → calendar, and calendar's own prev/next arrows → dropdown).

---

### 3. My Attendance — Calendar Couldn't Navigate Past the Current Month

Reported symptom: the "My Attendance" calendar was stuck at July 2026 — employees need to browse forward to see upcoming holidays before deciding when to apply for leave.

Root cause in `app/dashboard/my-attendance/page.tsx`: `next()` had `if (isCurrentMonth) return;`, and `CalendarAndHistory.tsx` separately disabled the Next button on the same flag. Both removed — forward navigation is now unbounded, matching `prev()` (which already had no limit). The now-dead `isCurrentMonth` prop was removed from `CalendarAndHistory.tsx` entirely.

---

### 4. `my-requests/page.tsx` — Field Contract Fix, Then Full Rebuild Against Shared Leave Types

**First pass:** `NewLeaveModal` was still sending `from_date`/`to_date` (no `duration` field at all) instead of the real `start_date`/`end_date`/`duration` contract — every submission through this page failed validation. Fixed to match `approvals/page.tsx`'s already-correct equivalent modal exactly, including adding the missing Duration dropdown. Also fixed `"lop"` → `"lwp"` for the Loss-of-Pay leave type value (confirmed via `backend/apps/hrms/models.py`: `LEAVE_LWP = 'lwp'`) — this typo existed in both `my-requests` and `approvals` pages and would have failed validation the moment the date-field fix let requests actually reach the backend.

**Inline CSS removal:** per instruction, converted every inline `style={{...}}` in this file to global CSS classes or Tailwind utilities. Reused several exact pre-existing global classes the page wasn't using (`.badge`/`.badge-warn`/etc., `.table-wrap`, `.tabs`/`.tab`/`.tab.active`), added one new reusable global class (`.field-select` in `app/globals.css`, replacing the duplicated inline chevron-background-image object on every themed `<select>`), and used Tailwind arbitrary values (`text-[var(--error)]`, etc.) for one-offs with no existing class. Also fixed `.btn-primary` → `.btn-filled` on every button in this file — `.btn-primary` doesn't exist anywhere in `globals.css`, so those buttons were rendering with no background color at all.

**Read-side field mismatch + pagination bug:** the table's local `LeaveRequest` interface used stale field names (`from_date`/`to_date`/`days`/`applied_on`/`remarks`) that don't exist on the real API response, and `useFetch<LeaveRequest[]>(...)` treated the paginated envelope (`{count, results, ...}`) as a bare array — the same "written before pagination was added" bug already fixed in three other leave components back in Session 16, just never caught here. Fixed by dropping the local type entirely in favor of the shared `LeaveRequest`/`PaginatedResponse`/`fmtDate` from `../leave/_data`, and switching the Status column to the shared `StatusCell` component.

---

### 5. Cancel Leave Request — Added in All Three "My Leave Requests" Locations

Turned out there are three separate places in the app where an employee can see and click into their own leave request, and none of them had a way to cancel:

1. `app/dashboard/my-requests/page.tsx`
2. `app/dashboard/approvals/page.tsx` → `MyRequestsSection` ("My Requests" tab)
3. `app/dashboard/leave/_components/LeaveDashboard.tsx` → employee branch ("Leave Management" sidebar page)

**Shared button, one place:** `LeaveRequestDetailModal.tsx` already had a Cancel button gated on `onCancelRequest && (r.can_cancel ?? (r.status === "pending" || r.status === "l2_pending"))` — reads the backend's `can_cancel` field first, falls back to a status check only if it's absent. Added a `window.confirm("Are you sure you want to cancel this leave request?")` guard before firing `onCancelRequest`, so every page using this modal gets the confirmation dialog for free.

**Per-page wiring** (each page owns its own `cancelRequest`/`cancelMine` function calling `clientApi.patch(API.leave.requestDetail(id))` — no body — then shows the backend's response `message` via `useToast` and refetches):
- `my-requests/page.tsx` — new `cancelRequest(id)` in `LeaveTab`, passed as `onCancelRequest`.
- `approvals/page.tsx` — new `cancelRequest(id)` in `MyRequestsSection`, passed the same way.
- `LeaveDashboard.tsx` — `cancelMine(id)` **already existed** and was already correctly wired for the approver's own "My Leave Requests" tab (`tab === "mine"`), but the plain-employee branch's modal call never passed `onCancelRequest` at all — the exact bug behind the reported screenshot. Wired it in, and fixed `cancelMine` itself: it previously swallowed all errors silently and only refetched a list the employee branch doesn't even read from (`refetchMine`, not `refetchRequests`). Now shows toast feedback on both success/error and refetches both lists.

---

### Key Files Changed / Created (08 July 2026 — Session 19)

| File | Change |
|------|--------|
| `lib/api/endpoints.ts` | Added `leave.holidays`, `leave.holidayDetail(id)` |
| `types/holidays.ts` | **NEW** |
| `app/dashboard/settings/holiday-calendar/page.tsx` | Full rewrite — real API, split into 5 files; server-side List filtering; month dropdown/Calendar view sync fix |
| `app/dashboard/settings/holiday-calendar/_components/HolidayFormModal.tsx` | **NEW** |
| `app/dashboard/settings/holiday-calendar/_components/HolidayViewModal.tsx` | **NEW** |
| `app/dashboard/settings/holiday-calendar/_components/DeleteHolidayModal.tsx` | **NEW** |
| `app/dashboard/settings/holiday-calendar/_components/HolidayListView.tsx` | **NEW** |
| `app/dashboard/settings/holiday-calendar/_components/HolidayCalendarView.tsx` | **NEW** |
| `app/dashboard/my-attendance/page.tsx` | Removed the `isCurrentMonth` block on forward calendar navigation |
| `app/dashboard/my-attendance/_components/CalendarAndHistory.tsx` | Removed dead `isCurrentMonth` prop; Next button no longer disabled at the current month |
| `app/globals.css` | Added `.field-select` (reusable select-chevron background, replaces per-file inline style objects) |
| `app/dashboard/my-requests/page.tsx` | `NewLeaveModal` sends `start_date`/`end_date`/`duration` (was `from_date`/`to_date`); `"lop"` → `"lwp"`; all inline styles converted to global/Tailwind classes; `.btn-primary` → `.btn-filled`; switched to shared `LeaveRequest`/`PaginatedResponse`/`fmtDate`/`StatusCell`/`LeaveRequestDetailModal` (fixes a Session-16-pattern pagination bug); added row-click detail modal + Cancel Request wiring |
| `app/dashboard/approvals/page.tsx` | `MyRequestsSection` — added `cancelRequest(id)`, wired `onCancelRequest` into its `LeaveRequestDetailModal` call |
| `app/dashboard/leave/_components/LeaveDashboard.tsx` | Employee branch's detail modal now passes `onCancelRequest={() => cancelMine(...)}`; `cancelMine` gained toast feedback and now refetches both `requestsUrl` and the mine-list |
| `app/dashboard/leave/_components/LeaveRequestDetailModal.tsx` | Cancel Request button now shows a `window.confirm` prompt before firing |

---

### Notes for Next Developer

- **`SendAllBirthdayModal` sends sequentially, not in parallel** — each POST awaits before the next starts. If the backend adds a bulk-send endpoint, replace the `for...of` loop with a single request.
- **`backendStats` prefers `allData.stats`** — `allData` is only fetched when `isAdmin === true`, which is set asynchronously from the cookie. On first render the stat cards will briefly show computed values until `allData` resolves; this is a flash of ~1 network round-trip, not a permanent state.
- **`referrals/page.tsx` fallback computing remains** — the `?? myReferrals.filter(...)` chains are intentional. Remove them only once you've confirmed both list and all endpoints always return a `stats` object.
- **Login error clears on focus, not on change** — clearing on the first keystroke (`onChange`) would also work but feels abrupt; focus was chosen because it matches the intent ("user is about to try again").`n`n---`n`n- **`.btn-primary` still doesn't exist anywhere in `globals.css`** — only fixed the instances in `my-requests/page.tsx` this session. Grep for `btn-primary` across the rest of the app (`approvals/page.tsx` still uses it in several places, confirmed while reading this session — not fixed, out of scope for the task given) — every one of those buttons is currently rendering with no background color.
- **`my-requests/page.tsx`'s `className="settings-card"` wrapper div also references an undefined class** — only `.settings-card-tile`/`.settings-card-icon`/etc. exist in `globals.css`, not a bare `.settings-card`. Flagged, not fixed (unrelated to the inline-style task given).
- **Custom leave types still can't be applied for, and now we know exactly why**: `LeaveRequestCreateSerializer.validate_leave_type` (`backend/apps/hrms/views/leave.py`) has logic to accept custom types via a `LeavePolicy` lookup, but it's dead code — `LeaveRequest.leave_type` is a model `CharField(choices=LEAVE_TYPE_CHOICES)`, so DRF's auto-generated `ChoiceField` rejects anything outside the fixed six before that validator ever runs. Backend fix needed: widen or drop the model-level `choices=`.
- **The `Q()`/`F()` bug in `_deduct_balance_safe` flagged in Session 18 is confirmed fixed** — `leave.py:212` already uses `F('used_days') + days` correctly. No longer an open item.
- **Holiday Calendar's branch field type mismatch**: the given API spec described `branch` as a UUID, but this app's real `GET /branch/branches/` returns numeric `id`s (confirmed via `BranchManagement.tsx`). Implemented using whatever `id` the branches endpoint actually returns (`number | null`) rather than forcing a UUID type that doesn't match reality — flag to the backend/spec owner if this becomes a real mismatch once tested against the live server.
- **Three "My Leave Requests" views now all support Cancel, but each still has its own separate `cancelRequest`/`cancelMine` function** — not shared, since each page's data-fetching/refetch shape differs slightly. If a fourth such view is ever added, consider extracting a `useCancelLeaveRequest()` hook instead of copy-pasting a fourth time.

---

## Session — Safura Samreen (09 July 2026)

**Branch:** `Frontend/Assessment_Issue`

---

### 1. Assessment Portal — "All Done" Button Showing With Zero Assignments

**File:** `app/onboarding/assessments/page.tsx`

**Symptom:** An employee with `assessment_status: "pending"` (visible in the login API response) was landing on `/onboarding/assessments`, seeing "0 tests assigned / No Assessments Yet", but the green "All Done — Go to Dashboard" button was still visible and clickable. Clicking it let them bypass the assessment gate entirely.

**Root cause:** The backend returns `all_complete: true` when `assignments` is an empty array — vacuously true (zero out of zero complete). The page was checking only `data?.all_complete` to show the button and to call `setAssessmentStatus("complete")`, which writes to the `royal_hrms_user` cookie and tells the proxy to stop redirecting.

**Fix:**
```typescript
// Before — triggers on vacuous all_complete
useEffect(() => { if (data?.all_complete) setAssessmentStatus("complete"); }, [data?.all_complete]);

// After — requires at least one assignment to exist
const assignments = data?.assignments ?? [];
const allComplete = data?.all_complete === true && assignments.length > 0;
useEffect(() => { if (allComplete) setAssessmentStatus("complete"); }, [allComplete]);
```

All three places that previously read `data?.all_complete` now read `allComplete`:
- `useEffect` that calls `setAssessmentStatus("complete")` — no longer fires on empty list
- Header "Go to Dashboard" button — no longer renders
- Main content "All Done — Go to Dashboard" button — no longer renders

When `assignments.length === 0` the page correctly shows only "No Assessments Yet — Your HR team will assign assessments before you can proceed to the dashboard." with no escape route.

---

### 2. Assessment Assign Modal — ID Mismatch Investigation

**File:** `app/dashboard/assessments/page.tsx`

Three rounds of debugging to find the correct ID to send to `POST /api/assessments/assign/`.

#### Round 1 — Status quo (employee UUID sent as `candidate_id`)
The assign modal was already sending `e.id` from `GET /employees/?page_size=500` — the employee's UUID — as `candidate_id`. The assignment stored successfully (no error from the backend), but when the assigned employee logged in and called `GET /assessments/my/`, it returned empty for some employees despite the assignment existing in the admin view.

#### Round 2 — Switched to candidate integer ID
Changed source to `GET /recruitment/candidates/?page_size=500` to send the proper `Candidate.id` (integer). Result: `{"status": "error", "message": "Employee not found.", "data": {}}`. The backend's assign endpoint is not a candidate FK lookup — it looks up an **Employee** by the UUID sent, and an integer candidate ID is not a valid Employee UUID.

#### Round 3 — Reverted to employee UUID
Reverted back to `GET /employees/?page_size=500` sending employee UUID. This correctly resolves the "Employee not found" error. The empty `my/` issue for some employees is a separate backend bug (see §3).

**Current state of the file:** source is `GET /employees/?page_size=500`, `candidate_id` field sends `e.id` (employee UUID). No net change from the starting state — the back-and-forth confirmed the original approach was correct for the assign step.

---

### 3. Root Cause Analysis — `GET /assessments/my/` Returns Empty for Some Employees

**Read-only investigation** — no code was changed. All findings are in backend files.

#### Models (`backend/apps/assessments/models.py`)

`CandidateAssignment` has **two separate FK fields**, only one of which is populated per row:

```python
candidate = ForeignKey('recruitment.Candidate', null=True, blank=True, …)
employee  = ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, …)
```

`candidate` → links to the recruitment `Candidate` model (for new-joiners going through the hiring pipeline).
`employee` → links directly to the `User` model (for existing employees assigned via UUID/department).

#### Assign endpoint (`backend/apps/assessments/views/admin.py` lines 225–332)

The view routes to one FK or the other based on what is sent:

```python
if candidate_id and not _UUID_RE.match(str(candidate_id)):
    employee_id  = candidate_id   # non-UUID string → re-route to employee path
    candidate_id = None

# UUID path → writes CandidateAssignment(candidate=<Candidate record>)
# employee_id / UUID path → writes CandidateAssignment(employee=<User>)
```

When the frontend sends a **UUID** as `candidate_id`, the backend runs `Candidate.objects.get(pk=candidate_id)`. If no `Candidate` row has that UUID (because the UUID is an Employee's UUID, not a Candidate's), it raises "Employee not found" or stores an orphaned assignment.

#### `my/` endpoint (`backend/apps/assessments/views/portal.py` lines 108–122)

```python
def get(self, request):
    candidate = _get_candidate(request.user)
    if candidate:
        assignments = base_qs.filter(candidate=candidate)   # path A
    else:
        assignments = base_qs.filter(employee=request.user) # path B
```

`_get_candidate(user)` does:
```python
return Candidate.objects.filter(portal_user=user).first()
```

This is an **exclusive OR** — it never queries both FKs at once. The path taken depends entirely on whether a `Candidate` row exists with `portal_user` pointing to the logged-in user.

#### The mismatch

| Employee type | Has `Candidate` row with `portal_user` set | Assignment stored on | `my/` queries | Result |
|---|---|---|---|---|
| Directly added (never went through recruitment) | No | `employee = user` | `employee = user` (path B) | ✅ Visible |
| Came through recruitment pipeline (onboarded) | Yes | `employee = user` (UUID sent from employees list) | `candidate = candidate` (path A) | ❌ Empty |
| Came through recruitment, assigned via Candidate UUID | Yes | `candidate = candidate` | `candidate = candidate` (path A) | ✅ Visible |

Employees who went through recruitment have their `Candidate.portal_user` set to their user account. So `_get_candidate` always finds them and forces path A. But the assignment was written to `employee=user` (path B) because the frontend sends the employee UUID. The two paths never overlap — the assignment is invisible.

This is why the bug is **intermittent**: it only affects employees who have both a `Candidate` record with `portal_user` set AND were assigned via the employees list (UUID path).

#### Where the backend fix must go

`backend/apps/assessments/views/portal.py` lines 119–122. The exclusive OR must become a union:

```python
# Current (broken for recruited employees assigned via UUID):
if candidate:
    assignments = base_qs.filter(candidate=candidate)
else:
    assignments = base_qs.filter(employee=request.user)

# Fix — query both FKs and union the results:
candidate = _get_candidate(request.user)
q = base_qs.filter(employee=request.user)
if candidate:
    q = q | base_qs.filter(candidate=candidate)
assignments = q.distinct()
```

This is a **backend-only fix** — one file, ~4 lines. No frontend change can resolve this because the mismatch is entirely inside the backend's read query.

---

### Key Files Changed (09 July 2026)

| File | Change |
|------|--------|
| `app/onboarding/assessments/page.tsx` | `allComplete` derived variable guards `setAssessmentStatus` and both "Go to Dashboard" buttons against vacuous `all_complete: true` when `assignments.length === 0` |
| `app/dashboard/assessments/page.tsx` | Reverted to employee UUID source after round-trip debugging confirmed original approach was correct for assign endpoint; no net change from session start |

---

### Notes for Next Developer

- **Backend fix is pending and blocking** — `backend/apps/assessments/views/portal.py` lines 119–122 must union both FK paths. Until this is deployed, employees who came through the recruitment pipeline will always see "No assessments assigned" when assigned via the employee UUID path. This is not a frontend bug — do not attempt to work around it in the frontend.
- **Existing broken assignments need to be deleted and re-assigned** — any assignment that was stored with the wrong FK (either a dangling Candidate UUID or the wrong path) will not surface even after the backend fix, because those rows are orphaned. HR must delete them from the admin view and re-assign.
- **`allComplete` replaces all three `data?.all_complete` references** — do not use `data?.all_complete` directly anywhere in `app/onboarding/assessments/page.tsx`. Always read from `allComplete` so the `assignments.length > 0` guard is enforced.
- **The assign endpoint's UUID routing logic** (`admin.py` lines 225–227) means a non-UUID string (e.g. `"RSS00016"`) sent as `candidate_id` is silently re-routed to the `employee_id` path. This re-routing is silent — there is no error if the re-route happens unexpectedly. Always send a UUID from `GET /employees/` as `candidate_id`, never an `employee_id` code string.
