from apps.attendance.views.working_hours import (
    WorkingHoursPolicyDetailView,
    WorkingHoursPolicyListCreateView,
)
from apps.attendance.views.weekly_days import (
    WeeklyDayPolicyDetailView,
    WeeklyDayPolicyListCreateView,
)
from apps.attendance.views.punch_rules import (
    PunchRulesPolicyDetailView,
    PunchRulesPolicyListCreateView,
)
from apps.attendance.views.overtime_rules import (
    OvertimePolicyDetailView,
    OvertimePolicyListCreateView,
)
from apps.attendance.views.late_mark_lop import (
    LateMarkLOPPolicyDetailView,
    LateMarkLOPPolicyListCreateView,
)
from apps.attendance.views.absence_alert import (
    AbsenceAlertPolicyDetailView,
    AbsenceAlertPolicyListCreateView,
)
from apps.attendance.views.settings_view import AttendanceSettingsAPIView
from apps.attendance.views.my_attendance import (
    AttendancePunchView,
    TodayAttendanceView,
    AttendanceStatsView,
    AttendanceSummaryView,
    AttendanceCalendarView,
    AttendanceCorrectionView,
)
from apps.attendance.views.hr_attendance import (
    HRAttendanceDashboardView,
    HRAttendanceListView,
    HRAttendanceDetailView,
    HROvertimeListView,
    HROvertimeCreateView,
    HRInvalidPunchesView,
    HRUnpunchesView,
    HRAttendanceImportView,
    HRAttendanceImportSampleView,
    HRAttendanceImportStatusView,
    HRAttendanceExportView,
    HRAttendanceReprocessView,
    HRCorrectionListView,
    HRCorrectionReviewView,
    HREmployeeMonthView,
    HRAttendanceCreateView,
)
from apps.attendance.views.hr_audit_actions import (
    HRAttendanceAuditView,
    HRInvalidPunchAssignView,
    HRInvalidPunchDiscardView,
    HRInvalidPunchConvertView,
)

__all__ = [
    'WorkingHoursPolicyListCreateView',
    'WorkingHoursPolicyDetailView',
    'WeeklyDayPolicyListCreateView',
    'WeeklyDayPolicyDetailView',
    'PunchRulesPolicyListCreateView',
    'PunchRulesPolicyDetailView',
    'OvertimePolicyListCreateView',
    'OvertimePolicyDetailView',
    'LateMarkLOPPolicyListCreateView',
    'LateMarkLOPPolicyDetailView',
    'AbsenceAlertPolicyListCreateView',
    'AbsenceAlertPolicyDetailView',
    'AttendanceSettingsAPIView',
    'AttendancePunchView',
    'TodayAttendanceView',
    'AttendanceStatsView',
    'AttendanceSummaryView',
    'AttendanceCalendarView',
    'AttendanceCorrectionView',
    # HR Management
    'HRAttendanceDashboardView',
    'HRAttendanceListView',
    'HRAttendanceDetailView',
    'HROvertimeListView',
    'HROvertimeCreateView',
    'HRInvalidPunchesView',
    'HRUnpunchesView',
    'HRAttendanceImportView',
    'HRAttendanceImportSampleView',
    'HRAttendanceImportStatusView',
    'HRAttendanceExportView',
    'HRAttendanceReprocessView',
    'HRCorrectionListView',
    'HRCorrectionReviewView',
    'HREmployeeMonthView',
    'HRAttendanceCreateView',
    # Audit + Invalid Punch Actions
    'HRAttendanceAuditView',
    'HRInvalidPunchAssignView',
    'HRInvalidPunchDiscardView',
    'HRInvalidPunchConvertView',
]
