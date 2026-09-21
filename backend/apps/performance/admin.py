from django.contrib import admin

from .models import Goal, PerformanceReview, ReviewCycle


@admin.register(ReviewCycle)
class ReviewCycleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'status', 'period_start', 'period_end', 'self_review_due', 'manager_review_due')
    list_filter   = ('status',)
    search_fields = ('name',)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display  = ('title', 'employee', 'cycle', 'status', 'due_date')
    list_filter   = ('status', 'cycle')
    search_fields = ('title', 'employee__full_name')


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'cycle', 'status', 'manager', 'self_submitted_at', 'manager_submitted_at')
    list_filter   = ('status', 'cycle')
    search_fields = ('employee__full_name', 'manager__full_name')
