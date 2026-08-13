from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import (
    AuditLog,
    ApprovalWorkflowRule,
    Company,
    Department,
    Designation,
    Document,
    EmailTemplate,
    EmailTemplateAttachment,
    EmailTemplateCategory,
    EmployeeApprovalOverride,
    EmployeeCodeSettings,
    EmployeeDocument,
    EmployeeProfile,
    OTPVerification,
    PasswordResetToken,
    Permission,
    PromotionRecord,
    Role,
    RolePermission,
    SMTPSettings,
    User,
)


# ─── Role & Permissions ───────────────────────────────────────────────────────

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'display_name', 'is_active')
    search_fields = ('name', 'display_name')
    list_filter   = ('is_active',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display  = ('codename', 'module', 'action')
    list_filter   = ('module',)
    search_fields = ('codename',)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission', 'granted_at')
    list_filter  = ('role',)


# ─── User ─────────────────────────────────────────────────────────────────────

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ('email', 'full_name', 'role', 'employee_id', 'department', 'branch', 'is_active', 'must_change_password', 'date_joined')
    list_filter    = ('role', 'is_active', 'must_change_password', 'is_staff')
    search_fields  = ('email', 'full_name', 'employee_id', 'department', 'branch')
    ordering       = ('email',)
    readonly_fields = ('id', 'date_joined', 'updated_at', 'last_login_ip')

    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'role', 'employee_id', 'department', 'designation', 'branch', 'phone', 'date_of_joining')}),
        ('Reporting', {'fields': ('reporting_manager', 'hr')}),
        ('Onboarding', {'fields': ('onboarding_status', 'assessment_status')}),
        ('Security', {'fields': ('must_change_password', 'failed_login_attempts', 'locked_until', 'last_login_ip')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps', {'fields': ('date_joined', 'updated_at', 'last_login')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'password1', 'password2'),
        }),
    )


# ─── Org Structure ────────────────────────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'manager', 'is_active')
    search_fields = ('name',)
    list_filter   = ('is_active',)
    autocomplete_fields = ('manager',)


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display  = ('name', 'department', 'is_active')
    list_filter   = ('is_active', 'department')
    search_fields = ('name',)


@admin.register(PromotionRecord)
class PromotionRecordAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'previous_designation', 'new_designation', 'previous_role', 'new_role', 'effective_date', 'promoted_by')
    list_filter   = ('effective_date',)
    search_fields = ('employee__full_name', 'employee__employee_id')
    autocomplete_fields = ('employee', 'promoted_by')


# ─── Auth helpers ─────────────────────────────────────────────────────────────

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display  = ('user', 'attempts', 'is_used', 'expires_at', 'created_at')
    list_filter   = ('is_used',)
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display  = ('user', 'is_used', 'expires_at', 'created_at')
    list_filter   = ('is_used',)
    readonly_fields = ('id', 'created_at')

    def has_add_permission(self, request):
        return False


# ─── Audit ────────────────────────────────────────────────────────────────────

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'action', 'module', 'ip_address', 'created_at')
    list_filter   = ('action', 'module')
    search_fields = ('user__email', 'action')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ─── SMTP ─────────────────────────────────────────────────────────────────────

@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    list_display  = ('name', 'smtp_type', 'host', 'port', 'from_email', 'is_active', 'priority', 'updated_at')
    list_filter   = ('is_active', 'smtp_type', 'priority')
    search_fields = ('name', 'host', 'from_email')
    readonly_fields = ('updated_at', 'updated_by')


# ─── Email Templates ──────────────────────────────────────────────────────────

@admin.register(EmailTemplateCategory)
class EmailTemplateCategoryAdmin(admin.ModelAdmin):
    list_display  = ('display_name', 'name', 'is_builtin', 'order')
    list_filter   = ('is_builtin',)
    search_fields = ('name', 'display_name')


class EmailTemplateAttachmentInline(admin.TabularInline):
    model  = EmailTemplateAttachment
    extra  = 0
    readonly_fields = ('uploaded_at', 'uploaded_by')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display  = ('display_name', 'name', 'template_type', 'is_active', 'is_builtin', 'updated_at')
    list_filter   = ('is_active', 'is_builtin', 'template_type')
    search_fields = ('name', 'display_name', 'subject')
    readonly_fields = ('updated_at', 'updated_by')
    inlines       = [EmailTemplateAttachmentInline]


# ─── Company & Settings ───────────────────────────────────────────────────────

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display  = ('company_name', 'gstin', 'pan', 'city', 'state', 'updated_at')
    readonly_fields = ('updated_at', 'updated_by')


@admin.register(EmployeeCodeSettings)
class EmployeeCodeSettingsAdmin(admin.ModelAdmin):
    list_display  = ('prefix', 'padding', 'next_sequence', 'updated_at')
    readonly_fields = ('updated_at', 'updated_by')


# ─── Documents ────────────────────────────────────────────────────────────────

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ('title', 'category', 'file_type', 'branch', 'uploaded_by', 'is_active', 'uploaded_at')
    list_filter   = ('category', 'file_type', 'is_active', 'branch')
    search_fields = ('title',)
    readonly_fields = ('uploaded_at', 'updated_at', 'uploaded_by')


# ─── Employee Profile & Documents ─────────────────────────────────────────────

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'date_of_birth', 'gender', 'blood_group', 'bank_name', 'birthday_wish_sent_year')
    search_fields = ('user__email', 'user__full_name', 'user__employee_id')
    list_filter   = ('gender', 'marital_status', 'blood_group')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display  = ('user', 'document_type', 'file_name', 'uploaded_at')
    list_filter   = ('document_type',)
    search_fields = ('user__email', 'user__employee_id')
    readonly_fields = ('uploaded_at', 'updated_at')


# ─── Approval Workflow ────────────────────────────────────────────────────────

@admin.register(ApprovalWorkflowRule)
class ApprovalWorkflowRuleAdmin(admin.ModelAdmin):
    list_display  = ('workflow_type', 'l1_approver_role', 'l2_approver_role', 'updated_at')
    readonly_fields = ('updated_at', 'updated_by')


@admin.register(EmployeeApprovalOverride)
class EmployeeApprovalOverrideAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'workflow_type', 'l1_override', 'l2_override', 'updated_at')
    list_filter   = ('workflow_type',)
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('updated_at', 'updated_by')
