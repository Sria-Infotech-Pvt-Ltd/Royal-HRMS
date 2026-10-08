from django.contrib import admin

from apps.attendance.models import (
    AbsenceAlertPolicy,
    AttendanceAbsenceAlert,
    AttendanceAuditLog,
    AttendanceCorrection,
    AttendanceImportLog,
    AttendanceLateMarkRules,
    AttendanceOvertime,
    AttendanceOvertimeRules,
    AttendancePunch,
    AttendancePunchRules,
    AttendanceRecord,
    AttendanceSettings,
    AttendanceWeeklyOff,
    AttendanceWorkingHours,
    FaceCaptureTelemetry,
    FaceVerificationAttempt,
    InvalidPunch,
    LateMarkLOPPolicy,
    MissingPunchNotification,
    OvertimePolicy,
    PunchRulesPolicy,
    WeeklyDayPolicy,
    WorkingHoursPolicy,
)


# ─── Policy models (named config records) ─────────────────────────────────────

@admin.register(WorkingHoursPolicy)
class WorkingHoursPolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'start_time', 'end_time', 'is_default', 'is_active', 'created_at')
    list_filter   = ('is_active', 'is_default')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(WeeklyDayPolicy)
class WeeklyDayPolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'is_default', 'is_active')
    list_filter   = ('is_active', 'is_default')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(PunchRulesPolicy)
class PunchRulesPolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'punch_mode', 'max_punch_count', 'auto_checkout_enabled', 'is_default', 'is_active')
    list_filter   = ('is_active', 'is_default', 'punch_mode')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(OvertimePolicy)
class OvertimePolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'minimum_overtime_minutes', 'approval_type', 'is_default', 'is_active')
    list_filter   = ('is_active', 'is_default', 'approval_type')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(LateMarkLOPPolicy)
class LateMarkLOPPolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'late_marks_per_lop', 'lop_deduction_unit', 'is_default', 'is_active')
    list_filter   = ('is_active', 'is_default', 'lop_deduction_unit')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(AbsenceAlertPolicy)
class AbsenceAlertPolicyAdmin(admin.ModelAdmin):
    list_display  = ('name', 'policy_code', 'absent_days_threshold', 'notification_recipients', 'is_enabled', 'is_default', 'is_active')
    list_filter   = ('is_active', 'is_default', 'is_enabled', 'notification_recipients')
    search_fields = ('name', 'policy_code')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')


# ─── Attendance Settings (org-level config) ───────────────────────────────────

class AttendanceWorkingHoursInline(admin.StackedInline):
    model = AttendanceWorkingHours
    can_delete = False


class AttendanceWeeklyOffInline(admin.StackedInline):
    model = AttendanceWeeklyOff
    can_delete = False


class AttendancePunchRulesInline(admin.StackedInline):
    model = AttendancePunchRules
    can_delete = False


class AttendanceOvertimeRulesInline(admin.StackedInline):
    model = AttendanceOvertimeRules
    can_delete = False


class AttendanceLateMarkRulesInline(admin.StackedInline):
    model = AttendanceLateMarkRules
    can_delete = False


class AttendanceAbsenceAlertInline(admin.StackedInline):
    model = AttendanceAbsenceAlert
    can_delete = False


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    list_display  = ('id', 'is_active', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by')
    inlines       = [
        AttendanceWorkingHoursInline,
        AttendanceWeeklyOffInline,
        AttendancePunchRulesInline,
        AttendanceOvertimeRulesInline,
        AttendanceLateMarkRulesInline,
        AttendanceAbsenceAlertInline,
    ]


# ─── Attendance Transactions ──────────────────────────────────────────────────

@admin.register(AttendancePunch)
class AttendancePunchAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'punch_type', 'punched_at', 'source', 'attendance_mode', 'branch', 'is_inside_geofence', 'is_regularized')
    list_filter   = ('punch_type', 'source', 'attendance_mode', 'is_regularized', 'is_inside_geofence')
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at')

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'date', 'status', 'first_punch_in', 'last_punch_out', 'total_working_minutes', 'is_late', 'is_early_exit')
    list_filter   = ('status', 'is_late', 'is_early_exit', 'date')
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'date'


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'date', 'punch_type', 'reason', 'status', 'reviewed_by', 'created_at')
    list_filter   = ('status', 'punch_type', 'reason')
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'date'


@admin.register(AttendanceOvertime)
class AttendanceOvertimeAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'date', 'ot_type', 'ot_start', 'ot_end', 'ot_minutes', 'ot_amount', 'status')
    list_filter   = ('status', 'ot_type')
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'date'


@admin.register(AttendanceImportLog)
class AttendanceImportLogAdmin(admin.ModelAdmin):
    list_display  = ('file_name', 'imported_by', 'total_rows', 'success_rows', 'failed_rows', 'status', 'created_at')
    list_filter   = ('status',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MissingPunchNotification)
class MissingPunchNotificationAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'date', 'channel', 'created_at')
    list_filter   = ('channel',)
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'date'

    def has_add_permission(self, request):
        return False


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'date', 'event', 'old_value', 'new_value', 'performed_by', 'created_at')
    list_filter   = ('event',)
    search_fields = ('employee__email', 'employee__employee_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'date'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FaceVerificationAttempt)
class FaceVerificationAttemptAdmin(admin.ModelAdmin):
    """
    Read-only audit trail of every face-verification attempt at punch time,
    matched or not — see the model's own docstring for why every attempt is
    recorded, not just failures. This is the "HR/security review of repeated
    failed attempts" surface the model was built for; before this admin
    registration existed, that data had no reachable UI or API view at all.
    """
    list_display   = ('employee', 'source', 'is_match', 'distance', 'rejection_reason', 'liveness_passed', 'created_at')
    list_filter     = ('source', 'is_match', 'rejection_reason', 'liveness_passed')
    search_fields   = ('employee__email', 'employee__employee_id', 'capture_session_id', 'embedding_fingerprint')
    readonly_fields = (
        'id', 'employee', 'source', 'capture_session_id', 'embedding_fingerprint',
        'liveness_passed', 'liveness_score', 'is_match', 'distance', 'rejection_reason',
        'created_at', 'updated_at',
    )
    date_hierarchy  = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(InvalidPunch)
class InvalidPunchAdmin(admin.ModelAdmin):
    list_display  = ('punch', 'issue_type', 'issue', 'status', 'assigned_to', 'created_at')
    list_filter   = ('status', 'issue_type')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(FaceCaptureTelemetry)
class FaceCaptureTelemetryAdmin(admin.ModelAdmin):
    """Read-only client-side face-capture diagnostics (numbers only)."""
    list_display    = ('employee', 'purpose', 'outcome', 'duration_ms', 'liveness_attempts', 'quality_failures', 'tf_backend', 'avg_fps', 'created_at')
    list_filter     = ('purpose', 'outcome', 'tf_backend')
    search_fields   = ('employee__email', 'employee__employee_id', 'capture_session_id')
    readonly_fields = [f.name for f in FaceCaptureTelemetry._meta.fields]
    date_hierarchy  = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
