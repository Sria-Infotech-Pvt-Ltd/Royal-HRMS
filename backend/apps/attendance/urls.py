
from django.urls import path

from apps.attendance.views import (
    AbsenceAlertPolicyDetailView,
    AbsenceAlertPolicyListCreateView,
    AttendanceCalendarView,
    AttendanceCorrectionView,
    AttendanceGeofenceCheckView,
    AttendancePunchView,
    AttendanceSettingsAPIView,
    AttendanceStatsView,
    AttendanceSummaryView,
    MyCorrectionsListView,
    LateMarkLOPPolicyDetailView,
    LateMarkLOPPolicyListCreateView,
    OvertimePolicyDetailView,
    OvertimePolicyListCreateView,
    PunchRulesPolicyDetailView,
    PunchRulesPolicyListCreateView,
    TodayAttendanceView,
    MyShiftView,
    MyWeeklyTimesheetView,
    WeeklyDayPolicyDetailView,
    WeeklyDayPolicyListCreateView,
    WorkingHoursPolicyDetailView,
    WorkingHoursPolicyListCreateView,
    # HR Management
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
    WeeklyOffAssignmentListView,
    WeeklyOffAssignmentBulkView,
    WeeklyOffAssignmentHistoryView,
    # Audit + Invalid Punch Actions
    HRAttendanceAuditView,
    HRInvalidPunchAssignView,
    HRInvalidPunchDiscardView,
    HRInvalidPunchConvertView,
    # Face Registration
    FaceRegistrationSubmitView,
    FaceRegistrationMyStatusView,
    FaceRegistrationPendingListView,
    FaceRegistrationReviewView,
    FaceVerificationStatusView,
    FaceRegistrationEmployeePickerView,
    FaceRegistrationEmployeeStatusView,
    FaceRegistrationHRRegisterView,
)

urlpatterns = [
    # Working Hours Policies
    path('working-hours/',           WorkingHoursPolicyListCreateView.as_view(), name='working-hours-list'),
    path('working-hours/<uuid:pk>/', WorkingHoursPolicyDetailView.as_view(),     name='working-hours-detail'),

    # Weekly Day Policies
    path('weekly-days/',           WeeklyDayPolicyListCreateView.as_view(), name='weekly-days-list'),
    path('weekly-days/<uuid:pk>/', WeeklyDayPolicyDetailView.as_view(),     name='weekly-days-detail'),

    # Punch Rules Policies
    path('punch-rules/',           PunchRulesPolicyListCreateView.as_view(), name='punch-rules-list'),
    path('punch-rules/<uuid:pk>/', PunchRulesPolicyDetailView.as_view(),     name='punch-rules-detail'),

    # Overtime Policies
    path('overtime-rules/',           OvertimePolicyListCreateView.as_view(), name='overtime-rules-list'),
    path('overtime-rules/<uuid:pk>/', OvertimePolicyDetailView.as_view(),     name='overtime-rules-detail'),

    # Late Mark & LOP Policies
    path('late-mark-lop/',           LateMarkLOPPolicyListCreateView.as_view(), name='late-mark-lop-list'),
    path('late-mark-lop/<uuid:pk>/', LateMarkLOPPolicyDetailView.as_view(),     name='late-mark-lop-detail'),

    # Absence Alert Policies
    path('absence-alert/',           AbsenceAlertPolicyListCreateView.as_view(), name='absence-alert-list'),
    path('absence-alert/<uuid:pk>/', AbsenceAlertPolicyDetailView.as_view(),     name='absence-alert-detail'),

    # Unified Attendance Settings (single-page save)
    path('settings/', AttendanceSettingsAPIView.as_view(), name='attendance-settings'),

    # ── My Attendance ─────────────────────────────────────────────────────────
    path('punch/',      AttendancePunchView.as_view(),    name='attendance-punch'),
    path('geofence-check/', AttendanceGeofenceCheckView.as_view(), name='attendance-geofence-check'),
    path('today/',      TodayAttendanceView.as_view(),    name='attendance-today'),
    path('my-shift/',   MyShiftView.as_view(),            name='attendance-my-shift'),
    path('my-weekly-timesheet/', MyWeeklyTimesheetView.as_view(), name='attendance-my-weekly-timesheet'),
    path('stats/',      AttendanceStatsView.as_view(),    name='attendance-stats'),
    path('summary/',    AttendanceSummaryView.as_view(),  name='attendance-summary'),
    path('calendar/',   AttendanceCalendarView.as_view(), name='attendance-calendar'),
    path('correction/', AttendanceCorrectionView.as_view(), name='attendance-correction'),
    path('corrections/my/', MyCorrectionsListView.as_view(), name='attendance-corrections-my'),

    # ── HR Attendance Management ───────────────────────────────────────────────
    path('dashboard/',                    HRAttendanceDashboardView.as_view(), name='hr-attendance-dashboard'),
    path('records/',                      HRAttendanceListView.as_view(),      name='hr-attendance-list'),
    path('records/create/',               HRAttendanceCreateView.as_view(),    name='hr-attendance-create'),
    path('records/<uuid:pk>/',            HRAttendanceDetailView.as_view(),    name='hr-attendance-detail'),
    path('overtime/',                     HROvertimeListView.as_view(),        name='hr-overtime-list'),
    path('overtime/create/',              HROvertimeCreateView.as_view(),      name='hr-overtime-create'),
    path('invalid-punches/',              HRInvalidPunchesView.as_view(),      name='hr-invalid-punches'),
    path('un-punches/',                   HRUnpunchesView.as_view(),           name='hr-un-punches'),
    path('import/',                         HRAttendanceImportView.as_view(),         name='hr-attendance-import'),
    path('import/sample/',                  HRAttendanceImportSampleView.as_view(),   name='hr-attendance-import-sample'),
    path('import/<uuid:import_id>/status/', HRAttendanceImportStatusView.as_view(),   name='hr-attendance-import-status'),
    path('export/',                       HRAttendanceExportView.as_view(),    name='hr-attendance-export'),
    path('reprocess/',                    HRAttendanceReprocessView.as_view(), name='hr-attendance-reprocess'),
    path('corrections/',                  HRCorrectionListView.as_view(),      name='hr-corrections-list'),
    path('corrections/<uuid:pk>/review/', HRCorrectionReviewView.as_view(),    name='hr-correction-review'),
    path('employee-calendar/',            HREmployeeMonthView.as_view(),       name='hr-employee-month-calendar'),
    path('weekly-off-assignments/',                      WeeklyOffAssignmentListView.as_view(),    name='weekly-off-assignments-list'),
    path('weekly-off-assignments/bulk/',                  WeeklyOffAssignmentBulkView.as_view(),    name='weekly-off-assignments-bulk'),
    path('weekly-off-assignments/<str:employee_id>/history/', WeeklyOffAssignmentHistoryView.as_view(), name='weekly-off-assignments-history'),

    # ── Audit History ─────────────────────────────────────────────────────────
    path('records/<uuid:pk>/audit/',                    HRAttendanceAuditView.as_view(),         name='hr-attendance-audit'),

    # ── Invalid Punch Actions ─────────────────────────────────────────────────
    path('invalid-punches/<uuid:pk>/assign/',  HRInvalidPunchAssignView.as_view(),  name='hr-invalid-punch-assign'),
    path('invalid-punches/<uuid:pk>/discard/', HRInvalidPunchDiscardView.as_view(), name='hr-invalid-punch-discard'),
    path('invalid-punches/<uuid:pk>/convert/', HRInvalidPunchConvertView.as_view(), name='hr-invalid-punch-convert'),

    # ── Face Registration ─────────────────────────────────────────────────────
    path('face-registration/',                  FaceRegistrationSubmitView.as_view(),      name='face-registration-submit'),
    path('face-registration/me/',               FaceRegistrationMyStatusView.as_view(),    name='face-registration-me'),
    path('face-registration/pending/',           FaceRegistrationPendingListView.as_view(), name='face-registration-pending'),
    path('face-registration/<uuid:pk>/review/', FaceRegistrationReviewView.as_view(),      name='face-registration-review'),

    # ── Face Verification — org-wide toggle status (Attendance Settings) ────────
    path('face-verification/status/', FaceVerificationStatusView.as_view(), name='face-verification-status'),

    # ── Face Registration — HR-initiated (register/update on someone's behalf) ─
    path('face-registration/register/',                              FaceRegistrationHRRegisterView.as_view(),    name='face-registration-hr-register'),
    path('face-registration/employees/',                             FaceRegistrationEmployeePickerView.as_view(), name='face-registration-employee-picker'),
    path('face-registration/employees/<uuid:employee_uuid>/status/', FaceRegistrationEmployeeStatusView.as_view(), name='face-registration-employee-status'),
]
