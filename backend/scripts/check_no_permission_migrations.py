#!/usr/bin/env python
"""
Phase 4 Rule 5 — "No permission-granting migrations, ever again."

Fails CI if any migration file writes RolePermission or Permission rows
(create/bulk_create/get_or_create/update_or_create) UNLESS that file is
in the frozen baseline below — the exact 40 pre-Phase-4 migrations this
codebase already has (grep-verified at the time this check was written;
see PHASE4_REPORT.md). The baseline must only ever SHRINK (if one of
these files is ever deleted/squashed), never grow — any new migration
needing a permission change should go through the new RoleAssignment/
FieldPermission/SoDRule engine (Phase 4) or a seed pack, not a migration.

Usage: python scripts/check_no_permission_migrations.py
Exit code 0 = no new permission-granting migrations found.
Exit code 1 = new one(s) found (CI should fail the build).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

_WRITE_RE = re.compile(r'\b(RolePermission|Permission)\.objects\.(create|bulk_create|get_or_create|update_or_create)\b')

# Frozen baseline — exactly the pre-Phase-4 migrations already doing this.
BASELINE_FILES = {
    'apps/accounts/migrations/0002_seed_roles_permissions.py',
    'apps/accounts/migrations/0014_system_admin_recruitment_permissions.py',
    'apps/accounts/migrations/0023_onboarding_permission_and_portal_template.py',
    'apps/accounts/migrations/0029_fix_employee_attendance_permission.py',
    'apps/accounts/migrations/0041_seed_departments_designations_permissions.py',
    'apps/accounts/migrations/0042_clean_employee_role_permissions.py',
    'apps/accounts/migrations/0043_seed_payroll_view_own_permission.py',
    'apps/accounts/migrations/0044_grant_payroll_edit_to_hr.py',
    'apps/accounts/migrations/0045_remove_payroll_view_from_manager.py',
    'apps/accounts/migrations/0052_seed_branch_admin_role.py',
    'apps/accounts/migrations/0053_flip_payroll_admin_hr.py',
    'apps/accounts/migrations/0057_grant_payroll_view_own_missing_roles.py',
    'apps/accounts/migrations/0058_grant_recruitment_view_to_system_admin.py',
    'apps/accounts/migrations/0063_seed_separation_approve_permission.py',
    'apps/accounts/migrations/0070_revoke_settings_edit_from_branch_admin.py',
    'apps/accounts/migrations/0077_revoke_settings_edit_from_hr.py',
    'apps/accounts/migrations/0086_seed_org_chart_view_permission.py',
    'apps/accounts/migrations/0088_seed_wfh_permissions_and_workflow.py',
    'apps/accounts/migrations/0092_remove_manager_recruitment_and_payroll_perms.py',
    'apps/accounts/migrations/0093_branch_admin_assessments_no_branches_mgmt.py',
    'apps/accounts/migrations/0094_add_facial_recognition_approve.py',
    'apps/accounts/migrations/0101_seed_org_structure_permissions_and_jobs.py',
    'apps/accounts/migrations/0108_seed_org_structure_backdate_permission.py',
    'apps/accounts/migrations/0119_fix_facial_recognition_approve_grants.py',
    'apps/accounts/migrations/0120_fix_payroll_run_revoke_from_hr.py',
    'apps/accounts/migrations/0122_grant_all_permissions_to_system_admin.py',
    'apps/accounts/migrations/0125_seed_email_log_permissions.py',
    'apps/accounts/migrations/0126_seed_onboarding_edit_and_reset_password_permissions.py',
    'apps/accounts/migrations/0148_seed_employees_view_sensitive_permission.py',
    'apps/accounts/migrations/0153_seed_employees_confirm_permission.py',
    'apps/accounts/migrations/0172_seed_employees_edit_own_profile_permission.py',
    'apps/accounts/migrations/0173_seed_dashboard_view_company_wide_permission.py',
    'apps/accounts/migrations/0174_revoke_edit_own_profile_from_employee_role.py',
    'apps/assessments/migrations/0002_seed_permissions.py',
    'apps/attendance/migrations/0023_seed_face_registration_permission.py',
    'apps/branch/migrations/0003_branch_permissions.py',
    'apps/hrms/migrations/0002_seed_expense_permissions.py',
    'apps/hrms/migrations/0033_seed_hr_help_respond_permission.py',
    'apps/payroll/migrations/0021_seed_tax_declarations_approve_permission.py',
    'apps/performance/migrations/0002_seed_performance_manage_cycles_permission.py',
}


def main() -> int:
    new_violations = []
    for migration_file in sorted(BACKEND_DIR.glob('apps/*/migrations/*.py')):
        rel_path = migration_file.relative_to(BACKEND_DIR).as_posix()
        text = migration_file.read_text(encoding='utf-8', errors='ignore')
        if _WRITE_RE.search(text) and rel_path not in BASELINE_FILES:
            new_violations.append(rel_path)

    if new_violations:
        print('FAIL — new permission-granting migration(s) found (not allowed, Phase 4 Rule 5):')
        for f in new_violations:
            print(f'  {f}')
        print('\nUse the RoleAssignment/FieldPermission/SoDRule engine or a seed pack instead.')
        return 1

    print(f'OK — no permission-granting migrations outside the frozen baseline ({len(BASELINE_FILES)} files).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
