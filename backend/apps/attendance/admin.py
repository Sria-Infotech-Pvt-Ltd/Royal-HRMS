from django.contrib import admin

from apps.attendance.models import WorkingHoursPolicy


@admin.register(WorkingHoursPolicy)
class WorkingHoursPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'policy_code', 'start_time', 'end_time', 'is_default', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_default')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
