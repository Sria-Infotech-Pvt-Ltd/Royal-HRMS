from django.contrib import admin

from apps.branch.models import Branch, City, EmployeeBranchAccess, State


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display  = ('name', 'code', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display  = ('name', 'state', 'is_active')
    list_filter   = ('is_active', 'state')
    search_fields = ('name',)
    autocomplete_fields = ('state',)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    # employees_count is NOT the model's own `employees_count` column — that
    # field is never written to anywhere (grepped: no assignment, no save()
    # override, no signal) and is always 0. The real count is computed live,
    # matching BranchSerializer.get_employees_count (apps/branch/serializers.py)
    # exactly, so admin and API never disagree.
    list_display  = ('branch_code', 'branch_name', 'city', 'state', 'status', 'is_headquarter', 'geofencing_enabled', 'employees_count')
    list_filter   = ('status', 'is_headquarter', 'geofencing_enabled', 'state')
    search_fields = ('branch_code', 'branch_name')
    autocomplete_fields = ('state', 'city')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Employees')
    def employees_count(self, obj):
        from apps.accounts.models import User
        return User.objects.filter(branch=obj.branch_name, is_active=True).count()


@admin.register(EmployeeBranchAccess)
class EmployeeBranchAccessAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'branch', 'is_primary', 'created_at')
    list_filter   = ('is_primary', 'branch')
    search_fields = ('employee__email', 'employee__employee_id', 'branch__branch_name')
    readonly_fields = ('id', 'created_at', 'updated_at')
