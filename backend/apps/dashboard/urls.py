from django.urls import path

from apps.dashboard import views

urlpatterns = [
    # ── System Admin Dashboard ────────────────────────────────────────────────
    path('system-admin/kpis/',                views.SystemAdminKPIView.as_view()),
    path('system-admin/announcement/',         views.SystemAdminAnnouncementView.as_view()),
    path('system-admin/pending-approvals/',    views.SystemAdminPendingApprovalsView.as_view()),
    path('system-admin/department-headcount/', views.SystemAdminDepartmentHeadcountView.as_view()),
    path('system-admin/employee-lifecycle/',   views.SystemAdminEmployeeLifecycleView.as_view()),
    path('system-admin/birthdays/today/',      views.SystemAdminBirthdayTodayView.as_view()),
    path('system-admin/birthdays/upcoming/',   views.SystemAdminBirthdayUpcomingView.as_view()),
    path('system-admin/audit-logs/',           views.SystemAdminAuditLogsView.as_view()),

    # ── Shared ────────────────────────────────────────────────────────────────
    path('department-headcount/',              views.HRDepartmentHeadcountView.as_view()),
    path('announcement/',                      views.SharedAnnouncementView.as_view()),

    # ── HR Dashboard ──────────────────────────────────────────────────────────
    path('hr/kpis/',                           views.HRKPIView.as_view()),
    path('hr/action-queue/',                   views.HRActionQueueView.as_view()),
    path('hr/recruitment-funnel/',             views.HRRecruitmentFunnelView.as_view()),
    path('hr/department-headcount/',           views.HRDepartmentHeadcountView.as_view()),
    path('hr/employee-lifecycle/',             views.HREmployeeLifecycleView.as_view()),
    path('hr/birthdays/today/',                views.HRBirthdayTodayView.as_view()),
    path('hr/birthdays/upcoming/',             views.HRBirthdayUpcomingView.as_view()),
    path('hr/attendance-summary/',             views.HRAttendanceSummaryView.as_view()),

    # ── Manager / Team Lead Dashboard ────────────────────────────────────────
    path('manager/', views.ManagerDashboardView.as_view(), name='manager-dashboard'),

    # ── Employee Dashboard ────────────────────────────────────────────────────
    path('employee/kpis/',               views.EmployeeKPIView.as_view()),
    path('employee/leave-balances/',     views.EmployeeLeaveBalanceView.as_view()),
    path('employee/action-items/',       views.EmployeeActionItemsView.as_view()),
    path('employee/recent-requests/',    views.EmployeeRecentRequestsView.as_view()),
    path('employee/attendance-summary/', views.EmployeeAttendanceSummaryView.as_view()),
    path('employee/attendance-status/',  views.EmployeeAttendanceStatusView.as_view()),
]
