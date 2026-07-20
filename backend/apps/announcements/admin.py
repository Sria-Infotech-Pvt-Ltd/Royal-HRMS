from django.contrib import admin

from .models import Announcement, AnnouncementReaction


class AnnouncementReactionInline(admin.TabularInline):
    model       = AnnouncementReaction
    extra       = 0
    readonly_fields = ('user', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ('title', 'category', 'visibility', 'target_department', 'target_branch', 'is_pinned', 'send_email', 'views_count', 'posted_by', 'created_at')
    list_filter   = ('category', 'visibility', 'is_pinned', 'send_email')
    search_fields = ('title', 'body')
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines       = [AnnouncementReactionInline]


@admin.register(AnnouncementReaction)
class AnnouncementReactionAdmin(admin.ModelAdmin):
    list_display  = ('announcement', 'user', 'created_at')
    search_fields = ('user__email', 'announcement__title')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
