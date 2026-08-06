# Branch Merge Summary — 04 August 2026

All five branches merged into `demo` in this order. Local changes were pushed first, then each branch merged one by one.

---

## 1. `frontendtest1`

**Author:** (branch-level, multiple contributors)

### What this branch added

| Area | Change |
|------|--------|
| **Employee documents** | New document types added to `EmployeeDocument.TYPE_CHOICES`: `passport_photo`, `cancelled_cheque` |
| **Migration** | `accounts/0049` (renumbered from original `0049`) — `alter_employeedocument_document_type` |

**Migration note:** Original `0049_alter_employeedocument_document_type.py` conflicted with demo's `0049_approval_workflow_role_fk.py`. Renumbered to `0050_alter_employeedocument_document_type.py` with updated dependency.

---

## 2. `Backend/03/08/2026`

**Author:** G. Durga Prasad  
**Date:** 03 August 2026

### What this branch added

#### New Role: Branch Admin
- New `Role.can_manage_branch` boolean field — a new authorization tier between HR and system_admin
- `branch_admin` role seeded with 56 permissions
- Payroll permissions (create/edit/delete) moved from HR role to branch_admin role
- `can_manage_branch` added to login response and threaded into `UserInfo`/`lib/auth.ts`

#### Document Management
- New `_can_manage_employee_documents()` helper — respects branch scoping for branch_admin
- `EmployeeDocumentAdminView` renamed to `EmployeeProfileDocumentView`
- Real document upload/replace/preview wired in `ProfileForm.tsx` and `profile/ProfileClient.tsx`
- New route: `employees/<id>/documents/`
- `DocEntry.documentType` field added to `_data.ts`

#### Scope Filtering
- `can_manage_branch` scoping tier added to `hrms/views/leave.py`, `expenses.py`, `attendance/services_hr_corrections.py`
- Removed role-string checks from `voice_commands/executor_payroll.py` — replaced with permission-based equivalent
- Dashboard action-item `navigation_url` for missing documents now points to My Profile, not Document Center

#### Onboarding
- Multi-assessment support: `assessment_ids` (list) accepted in onboarding approval alongside `uan_number`/`name_as_per_aadhar`
- Single-assessment dropdown on `OnboardingQueueTab.tsx` → multi-select checkboxes

#### Dashboard Stats
- `EmployeeStatsView.get()` — new endpoint returning dashboard employee counts broken down by role/department

#### Bug Fix
- Role-dropdown gate (`usePermission("settings.edit")`) removed from `AddEmployeeModal.tsx` and `employees/[id]/page.tsx` — `GET /roles/` is open to any authenticated user, gate was wrong

#### Data Fixes
- `is_default` removed from "Training" assessment; 2 leftover test assessments deleted (27 stray assignments)
- Leave-policy `applicable_branches` gaps fixed + 18 balance rows backfilled

#### Frontend
- Announcement widget moved to top / added where missing in `{Employee,Admin,HR,Manager}Dashboard.tsx`
- `proxy.ts` — removed unsigned-cookie fallback in `getPermissions()`
- Assessment page — "Continue to Next Assessment" vs "Go to Dashboard" split; cookie race fix

**Migration note:** Branch had `0048_alter_doc_type`, `0049_role_can_manage_branch`, `0050_seed_branch_admin_role`, `0051_flip_payroll_admin_hr`, `0052_employeeprofile_aadhar_state_sync` — all renumbered to `0050`–`0054` to fit after demo's chain.

---

## 3. `Frontend/03-08`

**Author:** Rithwika  
**Date:** 03 August 2026

### What this branch added

#### Manager Dashboard
- `ManagerDashboard.tsx` — `QA_URL_OVERRIDE` map: every Quick Actions tile that linked to a non-existent route now redirects to the correct real page
- `leave/page.tsx` + `leave/_client.tsx` — `?tab=apply` URL param support so "Apply Leave" Quick Action opens on the Apply tab directly

#### Add Employee Form
- Reporting Manager + HR fields added (branch-scoped dropdowns, follow-up `PUT` after creation)
- Reporting Manager fetch requires both `department` AND `branch` to be set first (disables until both selected)
- Field order rewritten: Role → Branch → Department → Designation → Employee Type → Date of Joining → Reporting Manager → HR
- Stale manager/HR cleared on branch change to prevent silent wrong-branch submission

#### Employees List Page
- Duplicate + non-functional "Role" filter removed (was never wired to the actual fetch query)

#### Assessments Page
- All four permission checks: `recruitment.*` → `assessments.*` (root cause: entire admin view was hidden for users with only Assessments permissions)
- "Assign" button moved from `canCreate` to `canEdit` (backend requires `assessments.edit`)

#### Alert Popups → In-App Banners (9 `alert()` calls across 5 files)
| File | Fix |
|------|-----|
| `settings/permissions/page.tsx` + `AddRoleModal.tsx` + `EditRoleModal.tsx` | Inline modal banner; 409-conflict case → dismissible page banner |
| `announcements/page.tsx` | Delete error → inline modal banner |
| `assessments/page.tsx` + `ItemsModal.tsx` | Delete errors → page/modal banner |
| `payroll/_components/PayrollAdjustments.tsx` | Delete/import/add errors → page or modal banner |

#### Proxy + Auth
- `proxy.ts` — `getCanManageTeam()` helper added; managers excluded from forced assessment redirect (`needsAssessments`)
- `login/page.tsx` — same manager exclusion in post-login `dest` computation

---

## 4. `employee4/26`

**Author:** (branch contributor)

### What this branch added

#### Backend
- `EmployeeStatsView.post()` — `hr_id` and `reporting_manager_id` now accepted as optional fields when creating an employee; validated before `_auto_assign_managers()` so an explicit pick always wins
- `ManagerListView.get()` — `department` filter added alongside existing `branch` filter
- `HRListView.get()` — `branch` now required; `system_admin` role excluded; cross-branch requester-insertion fallback removed
- `DepartmentListCreateView.get()` — `branch` filter added (derived from which departments have active employees in that branch)
- Branch canonicalization: `branch` and `department` values on employee creation now validated against `Branch`/`Department` tables with a 400 on unrecognized values

#### TEAM_CONTEXT.md
- Session log entry for 2026-08-04 (Swetha) added

---

## 5. `week-off`

**Author:** Teerdaveni  
**Date:** 03 August 2026

### What this branch added

#### Feature: Weekly Off Assignment (full feature)

- New model `EmployeeWeeklyOffAssignment` — per-employee, per-policy, with `effective_from`/`effective_to`; history preserved by closing out the prior row on reassignment
- Migration: `attendance/0020_employeeweeklyoffassignment.py`
- Centralized resolver in `core/cache_service.py::WeeklyOffCacheService` — priority: per-employee assignment → `WeeklyDayPolicy.is_default` → `AttendanceSettings.weekly_off` → Sat/Sun fallback
- Wired into: `AttendanceProcessorService._is_weekly_off()`, `AttendanceDashboardService`, `services_absence.py`, `hrms/views/leave.py`
- New service functions in `attendance/services_hr.py`: `build_weekly_off_assignment_queryset()`, `bulk_assign_weekly_off()`, `assign_weekly_off()`, `get_weekly_off_assignment_history()`
- New endpoints: `GET/POST /api/attendance/weekly-off-assignments/`, `POST .../bulk/`, `GET .../<employee_id>/history/`
- `assigned_employee_count` annotation added to `WeeklyDayPolicy` list/detail serializers
- Delete-safety check on `WeeklyDayPolicy` (blocks deleting in-use or default pattern)
- Frontend: `WeeklyOffAssignmentTab.tsx` (new 5th tab in Attendance & Time), `WeeklyOffPatternsCard.tsx` replacing old 7-day-toggle card

#### Production Hardening — Async / Celery

| Phase | What moved to Celery |
|-------|---------------------|
| 1(a) | Announcement bulk email — new `announcements/tasks.py`; BCC-batched (≤90/message) via `transaction.on_commit` |
| 1(b) | Recruitment assessment bulk-assign — new `assessments/tasks.py`; N+1 fixed (52+ queries → 12 for 26 employees) |
| 1(c) | 4 remaining `threading.Thread` → Celery: leave-lifecycle email, interview-scheduled + referral-submission emails, onboarding HR notification (new `notifications/tasks.py`, `recruitment/tasks.py`, `accounts/tasks.py`) |
| 3 | Attendance reprocessing — `HRAttendanceReprocessView` now queues `reprocess_attendance_task`, returns immediately; audit-log writes batched to `bulk_create` |

#### Production Hardening — Payroll Processing (Phase 2)

- `ProcessPayrollView` refactored into `process_payroll_cycle()` helper + `PayrollAlreadyProcessing` exception
- Bulk-fetch + per-distinct-structure caching + `bulk_create`/`bulk_update` instead of per-employee `update_or_create`
- Query count: 138 → 14 (90% reduction, N=23 employees)
- Idempotency: atomic `UPDATE ... WHERE status='attendance_approved'` compare-and-swap prevents double-processing
- Rollback safety: failed mid-write reverts cycle to `attendance_approved`

#### Production Hardening — Phase 4 Database Indexes

11 new indexes across 7 apps (one migration per app):

| App | Migration | Indexes added |
|-----|-----------|---------------|
| `accounts` | `0055_phase4_index_review` | `User(branch,is_active)`, `User(onboarding_status,is_active)`, `AuditLog(module,created_at)` |
| `attendance` | `0021_phase4_index_review` | `AttendanceCorrection(status)`, `LeaveRequest(employee,status,start_date,end_date)` |
| `payroll` | `0010_phase4_index_review` | `PayrollCycle(status)`, `PayrollCycle(cycle_start,cycle_end)` |
| `notifications` | `0002_phase4_index_review` | `Notification(user,is_read)`, `Notification(user,created_at)` |
| `announcements` | `0002_phase4_index_review` | `Announcement(is_pinned,created_at)` |
| `assessments` | `0011_phase4_index_review` | `CandidateAssignment(employee,status)`, `CandidateAssignment(candidate,status)` |
| `hrms` | `0018_phase4_index_review` | `LeaveRequest(employee,status,start_date,end_date)` |

**Migration notes:**
- `accounts/0048_phase4_index_review` conflicted with demo's `0048_add_uan_aadhar` — renumbered to `0055_phase4_index_review` (dep: `0054_employeeprofile_aadhar_uan_state_sync`)
- `payroll/0008_phase4_index_review` conflicted with demo's `0008_add_epf_statutory_rates` — renumbered to `0010_phase4_index_review` (dep: `0009_seed_payroll_email_templates`)

---

## Final Migration Chain — `accounts` app

```
0047_role_add_can_manage_team
  └─ 0048_add_uan_aadhar_to_employee_profile   (local/demo)
       └─ 0049_approval_workflow_role_fk        (local/demo)
            └─ 0050_alter_employeedocument_document_type  (frontendtest1)
                 └─ 0051_role_can_manage_branch           (Backend/03/08)
                      └─ 0052_seed_branch_admin_role      (Backend/03/08)
                           └─ 0053_flip_payroll_admin_hr  (Backend/03/08)
                                └─ 0054_employeeprofile_aadhar_uan_state_sync  (Backend/03/08)
                                     └─ 0055_phase4_index_review               (week-off)
```

## Final Migration Chain — `payroll` app

```
0007_payrollcycle_branch
  └─ 0008_add_epf_statutory_rates_to_payroll_settings  (local/demo)
       └─ 0009_seed_payroll_email_templates             (local/demo)
            └─ 0010_phase4_index_review                 (week-off)
```
