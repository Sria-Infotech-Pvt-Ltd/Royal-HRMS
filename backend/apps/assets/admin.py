from django.contrib import admin

from apps.assets.models import Asset, AssetAssignment, AssetCategory, AssetMaintenanceRecord, AssetType


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display  = ('name', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('name',)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'is_active')
    list_filter   = ('is_active', 'category')
    search_fields = ('name',)
    autocomplete_fields = ('category',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ('asset_tag', 'asset_name', 'category', 'asset_type', 'branch', 'status', 'condition')
    list_filter   = ('status', 'condition', 'category', 'branch')
    search_fields = ('asset_tag', 'asset_name', 'serial_number')


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display  = ('asset', 'employee', 'status', 'assigned_date', 'return_date')
    list_filter   = ('status',)
    search_fields = ('asset__asset_tag', 'employee__full_name')
    autocomplete_fields = ('asset', 'employee', 'assigned_by', 'returned_by')


@admin.register(AssetMaintenanceRecord)
class AssetMaintenanceRecordAdmin(admin.ModelAdmin):
    list_display  = ('asset', 'status', 'maintenance_start_date', 'outcome', 'completed_date')
    list_filter   = ('status', 'outcome')
    search_fields = ('asset__asset_tag', 'issue')
    autocomplete_fields = ('asset', 'sent_to_maintenance_by', 'completed_by')
