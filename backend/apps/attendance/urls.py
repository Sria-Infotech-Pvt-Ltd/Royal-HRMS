from django.urls import path

from apps.attendance.views import (
    AbsenceAlertPolicyDetailView,
    AbsenceAlertPolicyListCreateView,
    AttendanceCalendarView,
    AttendanceCorrectionView,
    AttendancePunchView,
    AttendanceSettingsAPIView,
    AttendanceStatsView,
    AttendanceSummaryView,
    LateMarkLOPPolicyDetailView,
    LateMarkLOPPolicyListCreateView,
    OvertimePolicyDetailView,
    OvertimePolicyListCreateView,
    PunchRulesPolicyDetailView,
    PunchRulesPolicyListCreateView,
    TodayAttendanceView,
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
    HRAttendanceExportView,
    HRAttendanceReprocessView,
    HRCorrectionListView,
    HRCorrectionReviewView,
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
    path('today/',      TodayAttendanceView.as_view(),    name='attendance-today'),
    path('stats/',      AttendanceStatsView.as_view(),    name='attendance-stats'),
    path('summary/',    AttendanceSummaryView.as_view(),  name='attendance-summary'),
    path('calendar/',   AttendanceCalendarView.as_view(), name='attendance-calendar'),
    path('correction/', AttendanceCorrectionView.as_view(), name='attendance-correction'),

    # ── HR Attendance Management ───────────────────────────────────────────────
    path('dashboard/',                    HRAttendanceDashboardView.as_view(), name='hr-attendance-dashboard'),
    path('records/',                      HRAttendanceListView.as_view(),      name='hr-attendance-list'),
    path('records/<uuid:pk>/',            HRAttendanceDetailView.as_view(),    name='hr-attendance-detail'),
    path('overtime/',                     HROvertimeListView.as_view(),        name='hr-overtime-list'),
    path('overtime/create/',              HROvertimeCreateView.as_view(),      name='hr-overtime-create'),
    path('invalid-punches/',              HRInvalidPunchesView.as_view(),      name='hr-invalid-punches'),
    path('un-punches/',                   HRUnpunchesView.as_view(),           name='hr-un-punches'),
    path('import/',                       HRAttendanceImportView.as_view(),    name='hr-attendance-import'),
    path('export/',                       HRAttendanceExportView.as_view(),    name='hr-attendance-export'),
    path('reprocess/',                    HRAttendanceReprocessView.as_view(), name='hr-attendance-reprocess'),
    path('corrections/',                  HRCorrectionListView.as_view(),      name='hr-corrections-list'),
    path('corrections/<uuid:pk>/review/', HRCorrectionReviewView.as_view(),    name='hr-correction-review'),
]
