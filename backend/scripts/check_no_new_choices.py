#!/usr/bin/env python
"""
Phase 1 Task J #5 — fails CI if a new `choices=` list is added to any
model outside the allow-list below. The allow-list starts as the EXACT
Phase 1 inventory (PHASE0_INVENTORY.md / PHASE1_REPORT.md — 144 fields)
and must only ever shrink as later phases convert fields to LookupValue,
never grow.

Usage: python scripts/check_no_new_choices.py
Exit code 0 = no new choices= fields found. Exit code 1 = new ones found
(CI should fail the build).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BACKEND_DIR / 'apps'

# Exact baseline from the Phase 1 audit — "App.Model.field". Any
# choices= field found that is NOT in this set is new and fails the check.
ALLOWED_CHOICES_FIELDS = {
    # accounts
    'accounts.User.employee_type', 'accounts.User.work_mode', 'accounts.User.pay_group',
    'accounts.User.attendance_scheme', 'accounts.User.payment_method', 'accounts.User.onboarding_status',
    'accounts.User.assessment_status', 'accounts.User.employment_status',
    'accounts.HireAction.reason', 'accounts.HireAction.employment_type', 'accounts.HireAction.status',
    'accounts.PromotionRecord.reason', 'accounts.PasswordResetToken.purpose',
    'accounts.SMTPSettings.smtp_type', 'accounts.SMTPSettings.priority', 'accounts.SMTPSettings.receiver_email_type',
    'accounts.EmailLog.status',
    'accounts.Company.jurisdiction', 'accounts.Company.entity_type', 'accounts.Company.country_of_registration',
    'accounts.Company.msme_class', 'accounts.Company.bank_account_type', 'accounts.Company.industry',
    'accounts.Company.default_currency', 'accounts.Company.date_format', 'accounts.Company.timezone',
    'accounts.Company.financial_year_start_month', 'accounts.CompanyGSTRegistration.registration_type',
    'accounts.EmployeeCodeSeries.employment_type', 'accounts.Document.category',
    'accounts.EmployeeProfile.gender', 'accounts.EmployeeProfile.marital_status', 'accounts.EmployeeProfile.blood_group',
    'accounts.EmployeeProfile.account_type', 'accounts.EmployeeProfile.bank_change_status',
    'accounts.EmployeeProfile.pending_account_type', 'accounts.EmployeeProfile.disability_type',
    'accounts.EducationExperienceFieldConfig.list_type', 'accounts.EducationRecord.level',
    'accounts.WorkExperienceRecord.employment_type', 'accounts.FamilyMember.relationship', 'accounts.FamilyMember.gender',
    'accounts.EPFNominee.scheme', 'accounts.CompanyAsset.asset_type', 'accounts.CompanyAsset.condition',
    'accounts.OnboardingFieldConfig.field_type', 'accounts.OnboardingFieldConfig.step',
    'accounts.EmployeeDocument.verification_status', 'accounts.ApprovalWorkflowRule.workflow_type',
    'accounts.EmployeeApprovalOverride.workflow_type',
    # attendance
    'attendance.WeeklyDayPolicy.monday', 'attendance.WeeklyDayPolicy.tuesday', 'attendance.WeeklyDayPolicy.wednesday',
    'attendance.WeeklyDayPolicy.thursday', 'attendance.WeeklyDayPolicy.friday', 'attendance.WeeklyDayPolicy.saturday',
    'attendance.WeeklyDayPolicy.sunday', 'attendance.PunchRulesPolicy.punch_mode',
    'attendance.PunchRulesPolicy.missing_punch_action', 'attendance.OvertimePolicy.round_off_rule',
    'attendance.OvertimePolicy.approval_type', 'attendance.LateMarkLOPPolicy.lop_deduction_unit',
    'attendance.AbsenceAlertPolicy.notification_recipients', 'attendance.AttendanceLateMarkRules.lop_deduction_unit',
    'attendance.AttendanceAbsenceAlert.notify_whom', 'attendance.AttendancePunch.punch_type',
    'attendance.AttendancePunch.source', 'attendance.AttendancePunch.attendance_mode',
    'attendance.AttendanceRecord.status', 'attendance.AttendanceRecord.work_mode',
    'attendance.AttendanceCorrection.punch_type', 'attendance.AttendanceCorrection.reason',
    'attendance.AttendanceCorrection.status', 'attendance.AttendanceCorrection.l1_status',
    'attendance.AttendanceCorrection.l2_status', 'attendance.AttendanceOvertime.ot_type',
    'attendance.AttendanceOvertime.status', 'attendance.AttendanceImportLog.status',
    'attendance.AttendanceAuditLog.event', 'attendance.InvalidPunch.status',
    'attendance.FaceRegistrationRequest.status', 'attendance.FaceVerificationAttempt.source',
    'attendance.FaceVerificationAttempt.rejection_reason',
    # hrms
    'hrms.Expense.category', 'hrms.Expense.status', 'hrms.Holiday.holiday_type',
    'hrms.LeavePolicy.accrual_frequency', 'hrms.LeavePolicy.carry_forward_type', 'hrms.LeavePolicy.carry_forward_mode',
    'hrms.LeavePolicy.applicable_gender', 'hrms.LeaveBalance.leave_type', 'hrms.SeparationRequest.separation_type',
    'hrms.SeparationRequest.reason', 'hrms.SeparationRequest.status', 'hrms.SeparationApprovalStage.stage',
    'hrms.SeparationApprovalStage.status', 'hrms.SeparationClearance.clearance_type',
    'hrms.SeparationClearance.status', 'hrms.SeparationDocument.document_type', 'hrms.SeparationSettlement.status',
    'hrms.LeaveRequest.leave_type', 'hrms.LeaveRequest.duration', 'hrms.LeaveRequest.status',
    'hrms.LeaveRequest.l1_status', 'hrms.LeaveRequest.l2_status', 'hrms.WorkFromHomeRequest.status',
    'hrms.WorkFromHomeRequest.l1_status', 'hrms.WorkFromHomeRequest.l2_status', 'hrms.HRHelpRequest.topic',
    'hrms.HRHelpRequest.priority', 'hrms.HRHelpRequest.status', 'hrms.EmployeeDocumentSubmission.category',
    'hrms.EmployeeDocumentSubmission.status',
    # payroll
    'payroll.PayrollSettings.approval_levels', 'payroll.StatutoryConfig.lwf_frequency',
    'payroll.SalaryComponent.component_type', 'payroll.SalaryComponent.calculation_type',
    'payroll.BranchPayrollConfig.pf_wage_basis', 'payroll.EmployeeSalaryConfig.reason',
    'payroll.PayrollCycle.status', 'payroll.EmployeePayslip.status', 'payroll.PayslipQuery.status',
    'payroll.PayrollAdjustment.type', 'payroll.SalaryTransferBatch.status',
    'payroll.EmployeeTaxDeclaration.tax_regime', 'payroll.EmployeeTaxDeclaration.status',
    # recruitment
    'recruitment.Candidate.interview_mode', 'recruitment.Candidate.status', 'recruitment.CandidateLog.log_type',
    'recruitment.CandidateEmail.status', 'recruitment.ReferralBonus.status',
    # performance
    'performance.ReviewCycle.status', 'performance.Goal.status', 'performance.Goal.self_rating',
    'performance.PerformanceReview.self_rating', 'performance.PerformanceReview.manager_rating',
    'performance.PerformanceReview.status',
    # assessments, notifications, announcements, branch
    'assessments.AssessmentItem.item_type', 'assessments.CandidateAssignment.status',
    'notifications.Notification.notification_type', 'notifications.Notification.module',
    'announcements.Announcement.category', 'announcements.Announcement.visibility',
    'branch.Branch.status',
    # platform_core itself — both are internal state-machine vocabularies
    # with code behavior attached to every value (ChangeHistory.action is
    # read by the capture mechanism itself; NumberSeries.reset_period is
    # read by services_numbering.py's _reset_key()), not a business list an
    # admin would ever add a new value to without a matching code change
    # anyway — exactly the exception this script's own policy allows for.
    'platform_core.ChangeHistory.action', 'platform_core.NumberSeries.reset_period',
}

_CLASS_RE = re.compile(r'^class (\w+)\(')
_FIELD_START_RE = re.compile(r'^\s{4}(\w+)\s*=\s*models\.\w*Field\(')


def find_choices_fields(models_file: Path, app_label: str) -> set[str]:
    """Field definitions often span multiple lines (choices= on a later
    line than `field = models.XField(`), so this accumulates each field's
    full `(...)` call before checking for `choices=`, rather than
    requiring it on the same source line."""
    found = set()
    current_class = None
    lines = models_file.read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        class_match = _CLASS_RE.match(line)
        if class_match:
            current_class = class_match.group(1)
            i += 1
            continue

        field_match = _FIELD_START_RE.match(line)
        if field_match and current_class:
            # Accumulate lines until this field's parens balance (handles
            # the common case of choices= listed on its own indented line).
            depth = line.count('(') - line.count(')')
            buffer = line
            j = i
            while depth > 0 and j + 1 < len(lines):
                j += 1
                buffer += '\n' + lines[j]
                depth += lines[j].count('(') - lines[j].count(')')
            if 'choices' in buffer and re.search(r'\bchoices\s*=', buffer):
                found.add(f'{app_label}.{current_class}.{field_match.group(1)}')
            i = j + 1
            continue

        i += 1
    return found


def main() -> int:
    all_found: set[str] = set()
    for models_file in APPS_DIR.glob('*/models.py'):
        app_label = models_file.parent.name
        all_found |= find_choices_fields(models_file, app_label)
    for models_dir in APPS_DIR.glob('*/models'):
        if models_dir.is_dir():
            app_label = models_dir.parent.name
            for f in models_dir.glob('*.py'):
                all_found |= find_choices_fields(f, app_label)

    new_fields = all_found - ALLOWED_CHOICES_FIELDS
    if new_fields:
        print('New choices= fields found that are not on the Phase 1 allow-list:')
        for f in sorted(new_fields):
            print(f'  {f}')
        print('\nBusiness-changeable values must use a LookupType/LookupValue '
              '(apps.platform_core) instead of a hardcoded choices= list. '
              'If this field genuinely needs a plain Python enum (e.g. an '
              'internal state machine with no business-admin need to add '
              'values), add it to ALLOWED_CHOICES_FIELDS in this script '
              'with a comment explaining why.')
        return 1

    print(f'OK — {len(all_found)} choices= fields found, all on the allow-list.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
