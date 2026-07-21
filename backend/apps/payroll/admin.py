from django.contrib import admin
from .models import (
    PayrollSettings,
    StatutoryConfig,
    SalaryStructure,
    SalaryComponent,
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    PayrollCycle,
    EmployeePayslip,
    PayslipQuery,
)


@admin.register(PayrollSettings)
class PayrollSettingsAdmin(admin.ModelAdmin):
    list_display = ['cycle_start_day', 'cycle_end_day', 'pay_day', 'approval_levels', 'enable_reimbursements', 'enable_bonuses']


@admin.register(StatutoryConfig)
class StatutoryConfigAdmin(admin.ModelAdmin):
    list_display = ['state', 'pt_applicable', 'esi_applicable', 'lwf_applicable']
    list_select_related = ['state']


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'is_active', 'created_at']


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ['name', 'structure', 'component_type', 'calculation_type', 'value', 'is_active']
    list_select_related = ['structure']


@admin.register(BranchPayrollConfig)
class BranchPayrollConfigAdmin(admin.ModelAdmin):
    list_display = ['branch', 'salary_structure', 'pf_applicable', 'pf_wage_ceiling']
    list_select_related = ['branch', 'salary_structure']


@admin.register(EmployeeSalaryConfig)
class EmployeeSalaryConfigAdmin(admin.ModelAdmin):
    list_display = ['employee', 'annual_ctc', 'effective_from', 'is_active']
    list_select_related = ['employee', 'salary_structure']


@admin.register(PayrollCycle)
class PayrollCycleAdmin(admin.ModelAdmin):
    list_display = ['cycle_start', 'cycle_end', 'pay_date', 'status', 'created_by']
    list_select_related = ['created_by']


@admin.register(EmployeePayslip)
class EmployeePayslipAdmin(admin.ModelAdmin):
    list_display = ['employee', 'cycle', 'net_pay', 'status']
    list_select_related = ['employee', 'cycle']


@admin.register(PayslipQuery)
class PayslipQueryAdmin(admin.ModelAdmin):
    list_display = ['payslip', 'raised_by', 'status', 'created_at']
    list_select_related = ['payslip', 'raised_by']
