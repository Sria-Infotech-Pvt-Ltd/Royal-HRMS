import logging
from datetime import date

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheTTL:
    LEAVE_POLICY        = 6  * 3600
    HOLIDAY             = 24 * 3600
    WEEKLY_OFF          = 24 * 3600
    ATTENDANCE_SETTINGS = 6  * 3600
    APPROVAL_WORKFLOW   = 6  * 3600
    BRANCHES            = 12 * 3600
    DEPARTMENTS         = 12 * 3600
    DESIGNATIONS        = 12 * 3600
    FINANCIAL_YEAR      = 24 * 3600


def _slug(s: str) -> str:
    return s.strip().lower().replace(' ', '_') if s else 'company'


# ── Leave Policy ──────────────────────────────────────────────────────────────

class LeavePolicyCacheService:
    @staticmethod
    def _key(leave_type: str) -> str:
        return f'leave_policy:{leave_type}'

    @classmethod
    def get(cls, leave_type: str):
        key = cls._key(leave_type)
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for %s', key)

        from apps.hrms.models import LeavePolicy
        policy = LeavePolicy.objects.filter(leave_type=leave_type, is_active=True).first()
        if policy is not None:
            try:
                cache.set(key, policy, CacheTTL.LEAVE_POLICY)
            except Exception:
                logger.warning('Cache write failed for %s', key)
        return policy

    @classmethod
    def invalidate(cls, leave_type: str) -> None:
        try:
            cache.delete(cls._key(leave_type))
        except Exception:
            logger.warning('Cache delete failed for leave_policy:%s', leave_type)


# ── Holiday ───────────────────────────────────────────────────────────────────

class HolidayCacheService:
    @staticmethod
    def _key(branch_name: str, year: int) -> str:
        return f'holiday:{_slug(branch_name)}:{year}'

    @classmethod
    def _fetch_from_db(cls, branch_name: str, year: int) -> list:
        from apps.hrms.models import Holiday
        from django.db.models import Q
        qs = Holiday.objects.filter(date__year=year, is_active=True)
        if branch_name:
            qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=branch_name))
        else:
            qs = qs.filter(branch__isnull=True)
        return list(qs.order_by('date').values('date', 'name'))

    @classmethod
    def _get_year(cls, branch_name: str, year: int) -> list:
        key = cls._key(branch_name, year)
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for %s', key)
        data = cls._fetch_from_db(branch_name, year)
        try:
            cache.set(key, data, CacheTTL.HOLIDAY)
        except Exception:
            logger.warning('Cache write failed for %s', key)
        return data

    @classmethod
    def _query_db_range(cls, start: date, end: date, branch_name: str) -> list:
        from apps.hrms.models import Holiday
        from django.db.models import Q
        qs = Holiday.objects.filter(date__gte=start, date__lte=end, is_active=True)
        if branch_name:
            qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=branch_name))
        else:
            qs = qs.filter(branch__isnull=True)
        return list(qs.order_by('date').values('date', 'name'))

    @classmethod
    def get_holiday_dates(cls, start: date, end: date, branch_name: str = '') -> set:
        if start.year != end.year:
            return set(h['date'] for h in cls._query_db_range(start, end, branch_name))
        holidays = cls._get_year(branch_name, start.year)
        return {h['date'] for h in holidays if start <= h['date'] <= end}

    @classmethod
    def get_holidays_with_names(cls, start: date, end: date, branch_name: str = '') -> list:
        if start.year != end.year:
            return cls._query_db_range(start, end, branch_name)
        holidays = cls._get_year(branch_name, start.year)
        return [h for h in holidays if start <= h['date'] <= end]

    @classmethod
    def invalidate_branch(cls, branch_name: str, year: int) -> None:
        try:
            cache.delete(cls._key(branch_name, year))
        except Exception:
            logger.warning('Cache delete failed for holiday:%s:%s', _slug(branch_name), year)

    @classmethod
    def invalidate_year(cls, year: int) -> None:
        keys = [cls._key('', year)]
        try:
            from apps.branch.models import Branch
            for name in Branch.objects.values_list('branch_name', flat=True):
                keys.append(cls._key(name, year))
        except Exception:
            logger.warning('Could not fetch branches for holiday cache invalidation (year=%s)', year)
        try:
            cache.delete_many(keys)
        except Exception:
            logger.warning('Cache delete_many failed for holiday year %s', year)


# ── Weekly Off ────────────────────────────────────────────────────────────────

class WeeklyOffCacheService:
    _KEY = 'weekly_off'

    @classmethod
    def _fetch_from_db(cls) -> set:
        try:
            from apps.attendance.models import WeeklyDayPolicy
            policy = WeeklyDayPolicy.objects.filter(is_active=True, is_default=True).first()
            if policy:
                return set(policy.weekly_off_days)
        except Exception:
            pass
        try:
            from apps.attendance.models import AttendanceSettings
            cfg = AttendanceSettings.objects.select_related('weekly_off').first()
            if cfg and getattr(cfg, 'weekly_off', None):
                _days = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
                return {d for d in _days if getattr(cfg.weekly_off, d, False)}
        except Exception:
            pass
        return {'saturday', 'sunday'}

    @classmethod
    def get(cls) -> set:
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for weekly_off')
        data = cls._fetch_from_db()
        try:
            cache.set(cls._KEY, data, CacheTTL.WEEKLY_OFF)
        except Exception:
            logger.warning('Cache write failed for weekly_off')
        return data

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for weekly_off')


# ── Approval Workflow ─────────────────────────────────────────────────────────

class ApprovalWorkflowCacheService:
    @staticmethod
    def _key(workflow_type: str) -> str:
        return f'approval_workflow:{workflow_type}'

    @classmethod
    def get_rule(cls, workflow_type: str):
        key = cls._key(workflow_type)
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for %s', key)
        from apps.accounts.models import ApprovalWorkflowRule
        rule = ApprovalWorkflowRule.objects.filter(workflow_type=workflow_type).first()
        if rule is not None:
            try:
                cache.set(key, rule, CacheTTL.APPROVAL_WORKFLOW)
            except Exception:
                logger.warning('Cache write failed for %s', key)
        return rule

    @classmethod
    def invalidate(cls, workflow_type: str) -> None:
        try:
            cache.delete(cls._key(workflow_type))
        except Exception:
            logger.warning('Cache delete failed for approval_workflow:%s', workflow_type)


# ── Attendance Settings ───────────────────────────────────────────────────────

class AttendanceSettingsCacheService:
    _KEY = 'attendance_settings'

    @classmethod
    def get(cls):
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for attendance_settings')
        from apps.attendance.models import AttendanceSettings
        settings = (
            AttendanceSettings.objects
            .select_related('working_hours', 'weekly_off', 'punch_rules', 'overtime_rules')
            .filter(is_active=True)
            .order_by('-created_at')
            .first()
        )
        if settings is not None:
            try:
                cache.set(cls._KEY, settings, CacheTTL.ATTENDANCE_SETTINGS)
            except Exception:
                logger.warning('Cache write failed for attendance_settings')
        return settings

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for attendance_settings')


# ── Branch ────────────────────────────────────────────────────────────────────

class BranchCacheService:
    _KEY = 'branches:all'

    @classmethod
    def get_all(cls) -> list:
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for branches:all')
        from apps.branch.models import Branch
        data = list(Branch.objects.filter(status='active').order_by('branch_name'))
        try:
            cache.set(cls._KEY, data, CacheTTL.BRANCHES)
        except Exception:
            logger.warning('Cache write failed for branches:all')
        return data

    @classmethod
    def invalidate_all(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for branches:all')


# ── Department ────────────────────────────────────────────────────────────────

class DepartmentCacheService:
    _KEY = 'departments:all'

    @classmethod
    def get_all(cls) -> list:
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for departments:all')
        from apps.accounts.models import Department
        data = list(Department.objects.filter(is_active=True).order_by('name'))
        try:
            cache.set(cls._KEY, data, CacheTTL.DEPARTMENTS)
        except Exception:
            logger.warning('Cache write failed for departments:all')
        return data

    @classmethod
    def invalidate_all(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for departments:all')


# ── Designation ───────────────────────────────────────────────────────────────

class DesignationCacheService:
    _KEY = 'designations:all'

    @classmethod
    def get_all(cls) -> list:
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for designations:all')
        from apps.accounts.models import Designation
        data = list(Designation.objects.filter(is_active=True).order_by('name'))
        try:
            cache.set(cls._KEY, data, CacheTTL.DESIGNATIONS)
        except Exception:
            logger.warning('Cache write failed for designations:all')
        return data

    @classmethod
    def invalidate_all(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for designations:all')


# ── Financial Year ─────────────────────────────────────────────────────────────

class FinancialYearCacheService:
    _KEY = 'financial_year_config'

    @classmethod
    def get(cls) -> dict | None:
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for financial_year_config')
        return None

    @classmethod
    def set(cls, data: dict) -> None:
        try:
            cache.set(cls._KEY, data, CacheTTL.FINANCIAL_YEAR)
        except Exception:
            logger.warning('Cache write failed for financial_year_config')

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for financial_year_config')
