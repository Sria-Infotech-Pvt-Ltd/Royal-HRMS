from django.urls import path

from apps.dashboard import views
from apps.dashboard.views.module_overviews import (
    AttendanceOverviewView,
    LeaveOverviewView,
    PayrollOverviewView,
    PerformanceOverviewView,
    ReportsOverviewView,
    SettingsOverviewView,
)

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
    path('birthdays/mine/',                    views.MyBirthdayWidgetsView.as_view()),

    # ── HR Dashboard ──────────────────────────────────────────────────────────
    path('hr/kpis/',                           views.HRKPIView.as_view()),
    path('hr/action-queue/',                   views.HRActionQueueView.as_view()),
    path('hr/recruitment-funnel/',             views.HRRecruitmentFunnelView.as_view()),
    path('hr/department-headcount/',           views.HRDepartmentHeadcountView.as_view()),
    path('hr/employee-lifecycle/',             views.HREmployeeLifecycleView.as_view()),
    path('hr/birthdays/today/',                views.HRBirthdayTodayView.as_view()),
    path('hr/birthdays/upcoming/',             views.HRBirthdayUpcomingView.as_view()),
    path('hr/attendance-summary/',             views.HRAttendanceSummaryView.as_view()),
    path('hr/overview/',                       views.HRDashboardOverviewView.as_view()),
    path('hr/lifecycle-register/',             views.HRLifecycleActionRegisterView.as_view()),

    # ── Module overview landings ─────────────────────────────────────────────
    path('module/attendance-overview/',        AttendanceOverviewView.as_view()),
    path('module/leave-overview/',             LeaveOverviewView.as_view()),
    path('module/payroll-overview/',           PayrollOverviewView.as_view()),
    path('module/performance-overview/',       PerformanceOverviewView.as_view()),
    path('module/reports-overview/',           ReportsOverviewView.as_view()),
    path('module/settings-overview/',          SettingsOverviewView.as_view()),

    # ── Manager / Team Lead Dashboard ────────────────────────────────────────
    path('manager/', views.ManagerDashboardView.as_view(), name='manager-dashboard'),

    # ── Employee Dashboard ────────────────────────────────────────────────────
    path('employee/kpis/',               views.EmployeeKPIView.as_view()),
    path('employee/leave-balances/',     views.EmployeeLeaveBalanceView.as_view()),
    path('employee/action-items/',       views.EmployeeActionItemsView.as_view()),
    path('employee/recent-requests/',    views.EmployeeRecentRequestsView.as_view()),
    path('employee/attendance-summary/', views.EmployeeAttendanceSummaryView.as_view()),
    path('employee/attendance-status/',  views.EmployeeAttendanceStatusView.as_view()),
    path('employee/birthdays/today/',    views.EmployeeBirthdayTodayView.as_view()),

]
