from django.urls import path

from apps.payroll.views.settings import PayrollSettingsView
from apps.payroll.views.structures import (
    SalaryStructureListView,
    SalaryStructureDetailView,
    SalaryComponentListView,
    SalaryComponentDetailView,
)
from apps.payroll.views.statutory import (
    StatutoryConfigListView,
    StatutoryConfigDetailView,
    StatutoryConfigByStateView,
)
from apps.payroll.views.branch_config import (
    BranchPayrollConfigListView,
    BranchPayrollConfigDetailView,
    BranchPayrollConfigByBranchView,
)
from apps.payroll.views.employee_salary import (
    EmployeeSalaryConfigListView,
    EmployeeSalaryConfigDetailView,
    EmployeeSalaryHistoryView,
)
from apps.payroll.views.cycles import (
    PayrollCycleListView,
    PayrollCycleDetailView,
    AttendanceApprovalView,
    ManagerAttendanceApprovalListView,
    ProcessPayrollView,
    MarkCyclePaidView,
    CancelPayrollCycleView,
)
from apps.payroll.views.attendance_approval import (
    AttendancePendingCyclesView,
    CycleAttendanceSummaryView,
    CycleEmployeeDailyView,
)
from apps.payroll.views.payslips import (
    CyclePayslipListView,
    PayslipDetailView,
    UpdatePayslipReimbBonusView,
    DispatchPayslipsView,
    MyPayslipsView,
    AcknowledgePayslipView,
    PayslipQueryListView,
    PayslipQueryResolveView,
    ExpenseSummaryForCycleView,
    ReferralBonusSummaryForCycleView,
)
from apps.payroll.views.adjustments import (
    PayrollAdjustmentListCreateView,
    PayrollAdjustmentDeleteView,
    PayrollAdjustmentBulkImportView,
)

urlpatterns = [
    # ── Payroll global settings ──────────────────────────────────────────────
    path('settings/', PayrollSettingsView.as_view(), name='payroll-settings'),

    # ── Salary structures ────────────────────────────────────────────────────
    path('structures/', SalaryStructureListView.as_view(), name='salary-structure-list'),
    path('structures/<uuid:pk>/', SalaryStructureDetailView.as_view(), name='salary-structure-detail'),
    path('structures/<uuid:structure_pk>/components/', SalaryComponentListView.as_view(), name='salary-component-list'),
    path('structures/<uuid:structure_pk>/components/<uuid:pk>/', SalaryComponentDetailView.as_view(), name='salary-component-detail'),

    # ── Statutory configs (per state) ────────────────────────────────────────
    path('statutory/', StatutoryConfigListView.as_view(), name='statutory-list'),
    path('statutory/<uuid:pk>/', StatutoryConfigDetailView.as_view(), name='statutory-detail'),
    path('statutory/by-state/<uuid:state_pk>/', StatutoryConfigByStateView.as_view(), name='statutory-by-state'),

    # ── Branch payroll config ────────────────────────────────────────────────
    path('branch-config/', BranchPayrollConfigListView.as_view(), name='branch-config-list'),
    path('branch-config/<uuid:pk>/', BranchPayrollConfigDetailView.as_view(), name='branch-config-detail'),
    path('branch-config/by-branch/<uuid:branch_pk>/', BranchPayrollConfigByBranchView.as_view(), name='branch-config-by-branch'),

    # ── Employee salary config (CTC assignment) ──────────────────────────────
    path('employee-salary/', EmployeeSalaryConfigListView.as_view(), name='employee-salary-list'),
    path('employee-salary/<uuid:pk>/', EmployeeSalaryConfigDetailView.as_view(), name='employee-salary-detail'),
    path('employee-salary/history/<str:employee_pk>/', EmployeeSalaryHistoryView.as_view(), name='employee-salary-history'),

    # ── Attendance approval (manager + HR) ──────────────────────────────────
    path('cycles/pending-approval/', AttendancePendingCyclesView.as_view(), name='payroll-pending-approval'),
    path('cycles/<uuid:pk>/attendance-summary/', CycleAttendanceSummaryView.as_view(), name='payroll-attendance-summary'),
    path('cycles/<uuid:pk>/attendance-daily/<str:employee_pk>/', CycleEmployeeDailyView.as_view(), name='payroll-employee-daily'),

    # ── Payroll cycles ───────────────────────────────────────────────────────
    path('cycles/', PayrollCycleListView.as_view(), name='payroll-cycle-list'),
    path('cycles/<uuid:pk>/', PayrollCycleDetailView.as_view(), name='payroll-cycle-detail'),
    path('cycles/<uuid:pk>/approve-attendance/', AttendanceApprovalView.as_view(), name='payroll-approve-attendance'),
    path('cycles/<uuid:pk>/manager-approvals/', ManagerAttendanceApprovalListView.as_view(), name='payroll-manager-approvals'),
    path('cycles/<uuid:pk>/process/', ProcessPayrollView.as_view(), name='payroll-process'),
    path('cycles/<uuid:pk>/mark-paid/', MarkCyclePaidView.as_view(), name='payroll-mark-paid'),
    path('cycles/<uuid:pk>/cancel/', CancelPayrollCycleView.as_view(), name='payroll-cancel-cycle'),

    # ── Payslips (HR) ────────────────────────────────────────────────────────
    path('cycles/<uuid:cycle_pk>/payslips/', CyclePayslipListView.as_view(), name='cycle-payslip-list'),
    path('cycles/<uuid:cycle_pk>/payslips/dispatch/', DispatchPayslipsView.as_view(), name='payslip-dispatch'),
    path('cycles/<uuid:cycle_pk>/expense-summary/', ExpenseSummaryForCycleView.as_view(), name='cycle-expense-summary'),
    path('cycles/<uuid:cycle_pk>/referral-bonus-summary/', ReferralBonusSummaryForCycleView.as_view(), name='cycle-referral-bonus-summary'),
    path('payslips/<uuid:pk>/', PayslipDetailView.as_view(), name='payslip-detail'),
    path('payslips/<uuid:pk>/reimb-bonus/', UpdatePayslipReimbBonusView.as_view(), name='payslip-reimb-bonus'),

    # ── Employee self-service ────────────────────────────────────────────────
    path('my-payslips/', MyPayslipsView.as_view(), name='my-payslips'),
    path('my-payslips/<uuid:pk>/acknowledge/', AcknowledgePayslipView.as_view(), name='payslip-acknowledge'),

    # ── Payslip queries ──────────────────────────────────────────────────────
    path('queries/', PayslipQueryListView.as_view(), name='payslip-query-list'),
    path('queries/<uuid:pk>/resolve/', PayslipQueryResolveView.as_view(), name='payslip-query-resolve'),

    # ── Payroll adjustments ──────────────────────────────────────────────────
    path('adjustments/', PayrollAdjustmentListCreateView.as_view(), name='payroll-adjustment-list'),
    path('adjustments/bulk-import/', PayrollAdjustmentBulkImportView.as_view(), name='payroll-adjustment-bulk-import'),
    path('adjustments/<uuid:pk>/', PayrollAdjustmentDeleteView.as_view(), name='payroll-adjustment-delete'),
]
