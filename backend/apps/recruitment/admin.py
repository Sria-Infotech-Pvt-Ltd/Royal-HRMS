from django.contrib import admin

from .models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule


class CandidateLogInline(admin.TabularInline):
    model       = CandidateLog
    extra       = 0
    readonly_fields = ('log_type', 'title', 'description', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


class CandidateEmailInline(admin.TabularInline):
    model       = CandidateEmail
    extra       = 0
    readonly_fields = ('template_used', 'subject', 'to_email', 'status', 'sent_by', 'sent_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display  = ('name', 'email', 'phone', 'position_applied', 'branch', 'status', 'referral_by', 'interview_date', 'added_by', 'created_at')
    list_filter   = ('status', 'branch', 'interview_mode', 'hr_approved', 'details_filled', 'portal_credentials_sent')
    search_fields = ('name', 'email', 'phone', 'position_applied')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines       = [CandidateLogInline, CandidateEmailInline]


@admin.register(CandidateLog)
class CandidateLogAdmin(admin.ModelAdmin):
    list_display  = ('candidate', 'log_type', 'title', 'created_at')
    list_filter   = ('log_type',)
    search_fields = ('candidate__name', 'candidate__email', 'title')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CandidateEmail)
class CandidateEmailAdmin(admin.ModelAdmin):
    list_display  = ('candidate', 'subject', 'to_email', 'template_used', 'status', 'sent_by', 'sent_at')
    list_filter   = ('status',)
    search_fields = ('candidate__name', 'to_email', 'subject')
    readonly_fields = ('sent_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReferralRule)
class ReferralRuleAdmin(admin.ModelAdmin):
    list_display  = ('title', 'order', 'is_active')
    list_filter   = ('is_active',)
    search_fields = ('title',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display  = ('referrer', 'candidate', 'bonus_amount', 'status', 'approved_by', 'approved_at', 'paid_by', 'paid_at', 'created_at')
    list_filter   = ('status',)
    search_fields = ('referrer__email', 'referrer__employee_id', 'candidate__name')
    readonly_fields = ('created_at', 'updated_at')
