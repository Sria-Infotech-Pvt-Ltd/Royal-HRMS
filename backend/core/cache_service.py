import logging
from datetime import date

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CacheTTL:
    LEAVE_POLICY        = 6  * 3600
    LEAVE_POLICY_LIST   = 300
    HOLIDAY             = 24 * 3600
    HOLIDAY_LIST        = 600
    WEEKLY_OFF          = 24 * 3600
    ATTENDANCE_SETTINGS = 6  * 3600
    APPROVAL_WORKFLOW   = 6  * 3600
    BRANCHES            = 12 * 3600
    DEPARTMENTS         = 12 * 3600
    DESIGNATIONS        = 12 * 3600
    FINANCIAL_YEAR      = 24 * 3600
    COMPANY             = 600
    ONBOARDING_FIELDS   = 6  * 3600
    TENANT_CLIENT       = 300


def _slug(s: str) -> str:
    return s.strip().lower().replace(' ', '_') if s else 'company'


# ── Tenant Client (schema resolution) ────────────────────────────────────────

class TenantClientCacheService:
    """
    Client row resolved by apps.tenants.middleware.TenantSchemaMiddleware on
    every authenticated request (public schema, before any tenant schema is
    activated) — the highest-traffic cache in this file, unlike the others
    below which are all tenant-scoped and only read on specific pages.

    Caches only {id, schema_name, is_active, enabled_modules} — deliberately
    NOT the full row. Grepped for every reader of `connection.tenant`/
    `request.tenant` project-wide: only apps.voice_commands.executor reads
    anything off it beyond the middleware itself, and only .has_module()
    (-> enabled_modules). Nothing reads company_name/contact info/gstin/
    pending_admin_password/provisioning_status/timestamps off the active
    tenant object anywhere, so those are left as field defaults on a
    cache-hit reconstruction rather than duplicated into Redis. If a future
    caller needs another Client field off connection.tenant, extend the
    cached field list here first — don't assume it's populated.

    Invalidated by apps.tenants.signals (post_save/post_delete on Client) —
    TTL below is a bounded backstop, not the correctness mechanism.

    Every method below explicitly runs inside schema_context(public). Client
    only ever lives in the public schema, and this cache's key namespace
    (CACHES['default']['KEY_FUNCTION'] = tenant_aware_key_func, see
    config/settings.py) prepends whichever schema is active ON THE
    CONNECTION at call time — not a fixed namespace. get() is only ever
    called from production code (the middleware, always right after its own
    set_schema_to_public()) so its writes were already reliably public-
    scoped, but invalidate() has no such guarantee: it fires from
    Client.save()/.delete() wherever those happen to be called from, and a
    signal handler has no control over what schema was active when its
    sender's .save() was called. Confirmed via real Postgres-backed tests
    (not by inspection) that without this, invalidate() computes a
    different, tenant-scoped key than the one get() actually wrote,
    silently leaving the stale entry in place. Wrapping every method here
    removes the need for any caller — middleware, signal, or a future one —
    to know or guarantee which schema is active.
    """

    @staticmethod
    def _key(schema_name: str) -> str:
        return f'tenant_client:{schema_name}'

    @classmethod
    def get(cls, schema_name: str):
        """Returns an unsaved Client instance for an ACTIVE schema_name, or
        None — mirrors Client.objects.get(schema_name=..., is_active=True)
        exactly (DoesNotExist -> None), just cached. Never caches a miss."""
        from django_tenants.utils import get_public_schema_name, schema_context

        key = cls._key(schema_name)
        with schema_context(get_public_schema_name()):
            try:
                cached = cache.get(key)
                if cached is not None:
                    # Defense in depth: only ever written below for a row
                    # that was active at write time, but re-checked here too
                    # so a cache hit can never grant access to a tenant the
                    # direct is_active=True query would have rejected — this
                    # must never become an authorization bypass.
                    if not cached.get('is_active'):
                        return None
                    from apps.tenants.models import Client
                    return Client(**cached)
            except Exception:
                logger.warning('Cache read failed for %s', key)

            from apps.tenants.models import Client
            client = Client.objects.filter(schema_name=schema_name, is_active=True).first()
            if client is not None:
                try:
                    cache.set(key, {
                        'id':              client.id,
                        'schema_name':     client.schema_name,
                        'is_active':       client.is_active,
                        'enabled_modules': client.enabled_modules,
                    }, CacheTTL.TENANT_CLIENT)
                except Exception:
                    logger.warning('Cache write failed for %s', key)
            return client

    @classmethod
    def invalidate(cls, schema_name: str) -> None:
        from django_tenants.utils import get_public_schema_name, schema_context

        with schema_context(get_public_schema_name()):
            try:
                cache.delete(cls._key(schema_name))
            except Exception:
                logger.warning('Cache delete failed for tenant_client:%s', schema_name)


# ── Leave Policy ──────────────────────────────────────────────────────────────

class LeavePolicyCacheService:
    _ALL_KEY = 'leave_policy:all'

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
    def get_all(cls) -> list:
        """All leave policy rows (any active state), for the settings list page."""
        try:
            cached = cache.get(cls._ALL_KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for leave_policy:all')
        from apps.hrms.models import LeavePolicy
        data = list(LeavePolicy.objects.all().order_by('leave_type'))
        try:
            cache.set(cls._ALL_KEY, data, CacheTTL.LEAVE_POLICY_LIST)
        except Exception:
            logger.warning('Cache write failed for leave_policy:all')
        return data

    @classmethod
    def invalidate(cls, leave_type: str) -> None:
        try:
            cache.delete_many([cls._key(leave_type), cls._ALL_KEY])
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

    @staticmethod
    def _list_key(year: int) -> str:
        return f'holiday:list:{year}'

    @classmethod
    def get_list_for_year(cls, year: int) -> list:
        """Full Holiday rows (any active state, every branch) for a given year —
        used by the settings/calendar list page, which filters further in Python."""
        key = cls._list_key(year)
        try:
            cached = cache.get(key)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for %s', key)
        from apps.hrms.models import Holiday
        data = list(Holiday.objects.filter(date__year=year).select_related('branch').order_by('date'))
        try:
            cache.set(key, data, CacheTTL.HOLIDAY_LIST)
        except Exception:
            logger.warning('Cache write failed for %s', key)
        return data

    @classmethod
    def invalidate_branch(cls, branch_name: str, year: int) -> None:
        try:
            cache.delete_many([cls._key(branch_name, year), cls._list_key(year)])
        except Exception:
            logger.warning('Cache delete failed for holiday:%s:%s', _slug(branch_name), year)

    @classmethod
    def invalidate_year(cls, year: int) -> None:
        keys = [cls._key('', year), cls._list_key(year)]
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

    # ── Per-employee resolution (centralized resolver) ────────────────────────
    #
    # Single unambiguous priority, used by every attendance/leave calculation:
    #   1. EmployeeWeeklyOffAssignment covering the date (employee-specific)
    #   2. WeeklyDayPolicy.is_default                     ┐ same org-wide
    #   3. AttendanceSettings.weekly_off (Settings page)  ┘ fallback chain
    #                                                        already in get()
    #   4. {'saturday', 'sunday'}                         — hardcoded floor
    #
    # get()/_fetch_from_db()/invalidate() above are untouched — steps 2-4 are
    # exactly the existing org-default resolution, unchanged. This only adds
    # step 1 in front of it. Not cached per-employee: the assignment lookup is
    # a single indexed query per employee, cheap even during batch daily
    # processing; caching it would need a per-employee key/invalidation scheme
    # for a value that changes far more often than the 24h org default does.

    @classmethod
    def get_effective_range(cls, employee, start: date, end: date) -> dict:
        """
        Resolve the effective weekly-off day-name set for `employee` for every
        date in [start, end] inclusive. Fetches the employee's assignment rows
        ONCE regardless of range length (not once per day), so this is safe to
        call for a whole calendar month or a whole leave request range.
        """
        from datetime import timedelta

        result: dict = {}
        assignments: list = []
        if employee is not None:
            from apps.attendance.models import EmployeeWeeklyOffAssignment
            from django.db.models import Q
            try:
                assignments = list(
                    EmployeeWeeklyOffAssignment.objects
                    .filter(employee=employee, effective_from__lte=end)
                    .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start))
                    .select_related('policy')
                )
            except Exception:
                logger.warning('Weekly-off assignment lookup failed for employee=%s', getattr(employee, 'pk', None))
                assignments = []

        org_default = None
        cur = start
        while cur <= end:
            match = next((a for a in assignments if a.covers(cur)), None)
            if match is not None:
                result[cur] = set(match.policy.weekly_off_days)
            else:
                if org_default is None:
                    org_default = cls.get()
                result[cur] = org_default
            cur += timedelta(days=1)
        return result

    @classmethod
    def get_effective(cls, employee, for_date: date) -> set:
        """Single-day convenience wrapper around get_effective_range()."""
        return cls.get_effective_range(employee, for_date, for_date)[for_date]


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
        rule = ApprovalWorkflowRule.objects.select_related(
            'l1_approver_role', 'l2_approver_role'
        ).filter(workflow_type=workflow_type).first()
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
            .select_related(
                'working_hours', 'weekly_off', 'punch_rules', 'overtime_rules',
                'late_mark_rules', 'absence_alert', 'face_verification', 'updated_by',
            )
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


# ── Company ───────────────────────────────────────────────────────────────────

class CompanyCacheService:
    """Company is an enforced singleton (Company.objects.first()) — a single key is enough."""
    _KEY = 'company:info'

    @classmethod
    def get(cls):
        try:
            cached = cache.get(cls._KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for company:info')
        from apps.accounts.models import Company
        company = Company.objects.first()
        if company is not None:
            try:
                cache.set(cls._KEY, company, CacheTTL.COMPANY)
            except Exception:
                logger.warning('Cache write failed for company:info')
        return company

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._KEY)
        except Exception:
            logger.warning('Cache delete failed for company:info')


# ── Onboarding Field Config ──────────────────────────────────────────────────

class OnboardingFieldConfigCacheService:
    """
    All OnboardingFieldConfig rows, grouped by step — read on every onboarding
    GET/save and every settings-page load, so worth caching same as the other
    per-company config lists above. tenant_aware_key_func (config/settings.py)
    already scopes this cache key per company automatically.
    """
    _ALL_KEY = 'onboarding_field_config:all'

    @classmethod
    def get_all(cls) -> list:
        try:
            cached = cache.get(cls._ALL_KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for onboarding_field_config:all')
        from apps.accounts.models import OnboardingFieldConfig
        data = list(OnboardingFieldConfig.objects.all())
        try:
            cache.set(cls._ALL_KEY, data, CacheTTL.ONBOARDING_FIELDS)
        except Exception:
            logger.warning('Cache write failed for onboarding_field_config:all')
        return data

    @classmethod
    def get_for_step(cls, step: int) -> list:
        return [c for c in cls.get_all() if c.step == step]

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._ALL_KEY)
        except Exception:
            logger.warning('Cache delete failed for onboarding_field_config:all')


class DocumentTypeConfigCacheService:
    """
    All DocumentTypeConfig rows — sibling of OnboardingFieldConfigCacheService
    for onboarding Step 5 (Documents). Read on every document upload/list
    (to resolve a type_key's label/required/allow_multiple) and every
    settings-page load.
    """
    _ALL_KEY = 'document_type_config:all'

    @classmethod
    def get_all(cls) -> list:
        try:
            cached = cache.get(cls._ALL_KEY)
            if cached is not None:
                return cached
        except Exception:
            logger.warning('Cache read failed for document_type_config:all')
        from apps.accounts.models import DocumentTypeConfig
        data = list(DocumentTypeConfig.objects.all())
        try:
            cache.set(cls._ALL_KEY, data, CacheTTL.ONBOARDING_FIELDS)
        except Exception:
            logger.warning('Cache write failed for document_type_config:all')
        return data

    @classmethod
    def label_for(cls, type_key: str) -> str:
        """Human label for a type_key, falling back to the raw key if the
        config row is missing (e.g. a since-deleted custom type — the
        underlying EmployeeDocument row itself is never deleted alongside
        it, same as a deleted custom OnboardingFieldConfig field leaving its
        historical value behind)."""
        for c in cls.get_all():
            if c.type_key == type_key:
                return c.label
        return type_key

    @classmethod
    def invalidate(cls) -> None:
        try:
            cache.delete(cls._ALL_KEY)
        except Exception:
            logger.warning('Cache delete failed for document_type_config:all')
