from django.contrib import admin

from .models import (
    Expense,
    ExpenseReceipt,
    LeaveBalance,
    LeavePolicy,
    LeaveRequest,
)


# ─── Expenses ─────────────────────────────────────────────────────────────────

class ExpenseReceiptInline(admin.TabularInline):
    model       = ExpenseReceipt
    extra       = 0
    readonly_fields = ('id', 'created_at')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ('expense_number', 'title', 'employee', 'category', 'amount', 'expense_date', 'status', 'branch')
    list_filter   = ('status', 'category', 'branch')
    search_fields = ('title', 'employee__full_name', 'employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'expense_date'
    inlines       = [ExpenseReceiptInline]


@admin.register(ExpenseReceipt)
class ExpenseReceiptAdmin(admin.ModelAdmin):
    list_display  = ('expense', 'file', 'created_at')
    readonly_fields = ('id', 'created_at')


# ─── Leave Policy ─────────────────────────────────────────────────────────────

@admin.register(LeavePolicy)
class LeavePolicyAdmin(admin.ModelAdmin):
    list_display  = ('leave_type', 'leave_type_label', 'annual_days', 'can_carry_forward', 'is_active')
    list_filter   = ('is_active', 'leave_type', 'can_carry_forward', 'applicable_gender')
    search_fields = ('leave_type', 'leave_type_label')
    readonly_fields = ('created_at', 'updated_at')


# ─── Leave Balance ────────────────────────────────────────────────────────────

@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'leave_type', 'year', 'total_days', 'used_days', 'carried_forward')
    list_filter   = ('leave_type', 'year')
    search_fields = ('employee__email', 'employee__full_name', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')


# ─── Leave Request ────────────────────────────────────────────────────────────

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'leave_type', 'start_date', 'end_date', 'total_days', 'duration', 'status', 'l1_status', 'l2_status')
    list_filter   = ('status', 'leave_type', 'duration', 'is_lwp')
    search_fields = ('employee__email', 'employee__full_name', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'start_date'
