from django.contrib import admin

from apps.assets.models import Asset, AssetAssignment


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
