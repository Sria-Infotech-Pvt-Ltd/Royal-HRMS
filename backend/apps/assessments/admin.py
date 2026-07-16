from django.contrib import admin

from .models import (
    Assessment,
    AssessmentItem,
    AssessmentSection,
    AssessmentSettings,
    CandidateAssignment,
    CandidateResponse,
)


@admin.register(AssessmentSettings)
class AssessmentSettingsAdmin(admin.ModelAdmin):
    list_display  = ('default_pass_percentage', 'max_attempts', 'time_limit_mins', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


class AssessmentSectionInline(admin.TabularInline):
    model  = AssessmentSection
    extra  = 0
    readonly_fields = ('id', 'created_at', 'updated_at')


class AssessmentItemInline(admin.TabularInline):
    model  = AssessmentItem
    extra  = 0
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display  = ('title', 'is_active', 'is_default', 'pass_percentage', 'max_attempts', 'time_limit_mins', 'created_by', 'created_at')
    list_filter   = ('is_active', 'is_default')
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines       = [AssessmentSectionInline, AssessmentItemInline]


@admin.register(AssessmentSection)
class AssessmentSectionAdmin(admin.ModelAdmin):
    list_display  = ('title', 'assessment', 'order', 'score')
    list_filter   = ('assessment',)
    search_fields = ('title', 'assessment__title')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AssessmentItem)
class AssessmentItemAdmin(admin.ModelAdmin):
    list_display  = ('title', 'assessment', 'section', 'item_type', 'order')
    list_filter   = ('item_type', 'assessment')
    search_fields = ('title', 'question', 'assessment__title')
    readonly_fields = ('id', 'created_at', 'updated_at')


class CandidateResponseInline(admin.TabularInline):
    model       = CandidateResponse
    extra       = 0
    readonly_fields = ('id', 'item', 'is_watched', 'selected_option', 'is_correct', 'score_awarded', 'responded_at', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CandidateAssignment)
class CandidateAssignmentAdmin(admin.ModelAdmin):
    list_display  = ('__str__', 'assessment', 'status', 'score', 'max_score', 'attempt_count', 'started_at', 'completed_at', 'assigned_by')
    list_filter   = ('status', 'assessment')
    search_fields = ('candidate__name', 'candidate__email', 'employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines       = [CandidateResponseInline]


@admin.register(CandidateResponse)
class CandidateResponseAdmin(admin.ModelAdmin):
    list_display  = ('assignment', 'item', 'selected_option', 'is_correct', 'score_awarded', 'is_watched', 'responded_at')
    list_filter   = ('is_correct', 'is_watched')
    readonly_fields = ('id', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False
