from django.contrib import admin
from .models import Expense

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ('title', 'employee', 'category', 'amount', 'expense_date', 'status')
    list_filter   = ('status', 'category')
    search_fields = ('title', 'employee__full_name')
