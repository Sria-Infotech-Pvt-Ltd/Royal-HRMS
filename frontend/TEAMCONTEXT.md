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

- No backend changes in this entire branch
- All API paths from `lib/api/endpoints.ts` — no inline strings
- All data fetching via `useFetch` hook
- `clientApi` used with `withCredentials: true`
- No `localStorage` for tokens
- No `any` types — all shapes explicitly typed
