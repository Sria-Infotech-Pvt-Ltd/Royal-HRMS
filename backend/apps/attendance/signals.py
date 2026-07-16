import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='attendance.WeeklyDayPolicy')
@receiver(post_delete, sender='attendance.WeeklyDayPolicy')
def on_weekly_day_policy_change(sender, instance, **kwargs):
    from core.cache_service import WeeklyOffCacheService
    WeeklyOffCacheService.invalidate()


@receiver(post_save, sender='attendance.AttendanceWeeklyOff')
@receiver(post_delete, sender='attendance.AttendanceWeeklyOff')
def on_attendance_weekly_off_change(sender, instance, **kwargs):
    from core.cache_service import WeeklyOffCacheService, AttendanceSettingsCacheService
    WeeklyOffCacheService.invalidate()
    AttendanceSettingsCacheService.invalidate()


@receiver(post_save, sender='attendance.AttendanceSettings')
@receiver(post_delete, sender='attendance.AttendanceSettings')
def on_attendance_settings_change(sender, instance, **kwargs):
    from core.cache_service import AttendanceSettingsCacheService
    AttendanceSettingsCacheService.invalidate()


@receiver(post_save, sender='attendance.AttendanceWorkingHours')
@receiver(post_delete, sender='attendance.AttendanceWorkingHours')
def on_attendance_working_hours_change(sender, instance, **kwargs):
    from core.cache_service import AttendanceSettingsCacheService
    AttendanceSettingsCacheService.invalidate()


@receiver(post_save, sender='attendance.AttendancePunchRules')
@receiver(post_delete, sender='attendance.AttendancePunchRules')
def on_attendance_punch_rules_change(sender, instance, **kwargs):
    from core.cache_service import AttendanceSettingsCacheService
    AttendanceSettingsCacheService.invalidate()


@receiver(post_save, sender='attendance.AttendanceOvertimeRules')
@receiver(post_delete, sender='attendance.AttendanceOvertimeRules')
def on_attendance_overtime_rules_change(sender, instance, **kwargs):
    from core.cache_service import AttendanceSettingsCacheService
    AttendanceSettingsCacheService.invalidate()
