from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from rest_framework import serializers

from apps.attendance.models import (
    DAYS_OF_WEEK,
    DAY_TYPE_CHOICES,
    DAY_TYPE_WORKING,
    AbsenceAlertPolicy,
    LateMarkLOPPolicy,
    OvertimePolicy,
    PunchRulesPolicy,
    WeeklyDayPolicy,
    WorkingHoursPolicy,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _compute_net_hours(start_time, end_time, break_duration: int) -> Decimal:
    """Return net working hours as a Decimal, handling overnight shifts."""
    today = date.today()
    start_dt = datetime.combine(today, start_time)
    end_dt = datetime.combine(today, end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    total_seconds = (end_dt - start_dt).total_seconds()
    net_seconds = total_seconds - (break_duration * 60)
    return Decimal(str(round(max(net_seconds, 0) / 3600, 2)))


# ─── List ──────────────────────────────────────────────────────────────────────

class WorkingHoursPolicyListSerializer(serializers.ModelSerializer):
    """Minimal read-only representation used in paginated list responses."""

    standard_working_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = WorkingHoursPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'start_time',
            'end_time',
            'break_duration',
            'grace_period',
            'standard_working_hours',
            'minimum_working_hours',
            'maximum_working_hours',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class WorkingHoursPolicyRetrieveSerializer(serializers.ModelSerializer):
    """Full read-only representation used in single-object responses."""

    standard_working_hours = serializers.FloatField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkingHoursPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            'start_time',
            'end_time',
            'break_duration',
            'grace_period',
            'standard_working_hours',
            'minimum_working_hours',
            'maximum_working_hours',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: WorkingHoursPolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: WorkingHoursPolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _WorkingHoursPolicyValidationMixin:
    """
    Reusable cross-field validations shared by Create and Update serializers.
    Kept in one place so the rules cannot drift apart between the two.
    """

    # Maximum allowed values — kept as class-level constants for easy change.
    MAX_BREAK_MINUTES = 480   # 8 h
    MAX_GRACE_MINUTES = 120   # 2 h
    MAX_HOURS = Decimal('24')

    def _validate_break_duration(self, value: int) -> int:
        if value > self.MAX_BREAK_MINUTES:
            raise serializers.ValidationError(
                f'Break duration cannot exceed {self.MAX_BREAK_MINUTES} minutes (8 hours).'
            )
        return value

    def _validate_grace_period(self, value: int) -> int:
        if value > self.MAX_GRACE_MINUTES:
            raise serializers.ValidationError(
                f'Grace period cannot exceed {self.MAX_GRACE_MINUTES} minutes (2 hours).'
            )
        return value

    def _validate_working_hours_field(self, value: Decimal, field_label: str) -> Decimal:
        if value < 0:
            raise serializers.ValidationError(
                f'{field_label} cannot be negative.'
            )
        if value > self.MAX_HOURS:
            raise serializers.ValidationError(
                f'{field_label} cannot exceed 24 hours.'
            )
        return value

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        """
        Run all cross-field checks.  When updating, fall back to the instance
        value for fields not present in attrs (PATCH support).
        """
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        start_time = _get('start_time')
        end_time = _get('end_time')
        break_duration = _get('break_duration', 0) or 0
        minimum_wh = _get('minimum_working_hours', Decimal('0')) or Decimal('0')
        maximum_wh = _get('maximum_working_hours', Decimal('0')) or Decimal('0')
        name = _get('name')

        # ── start == end is meaningless ──────────────────────────────────────
        if start_time and end_time and start_time == end_time:
            raise serializers.ValidationError({
                'end_time': 'Start time and end time cannot be the same.',
            })

        # ── Net hours must be positive after break deduction ────────────────
        if start_time and end_time:
            net_hours = _compute_net_hours(start_time, end_time, break_duration)
            if net_hours <= 0:
                raise serializers.ValidationError(
                    'Net working hours (shift duration minus break) must be greater than '
                    'zero. Reduce break duration or widen the shift window.'
                )

            # ── minimum_working_hours ≤ net shift hours ──────────────────────
            if minimum_wh and minimum_wh > net_hours:
                raise serializers.ValidationError({
                    'minimum_working_hours': (
                        f'Minimum working hours ({minimum_wh} h) cannot exceed the net '
                        f'shift duration ({net_hours} h). '
                        'Adjust the shift window, break duration, or minimum hours.'
                    ),
                })

        # ── minimum ≤ maximum ────────────────────────────────────────────────
        if minimum_wh and maximum_wh and minimum_wh > maximum_wh:
            raise serializers.ValidationError({
                'minimum_working_hours': (
                    f'Minimum working hours ({minimum_wh} h) cannot exceed '
                    f'maximum working hours ({maximum_wh} h).'
                ),
            })

        # ── Duplicate name check ─────────────────────────────────────────────
        if name:
            qs = WorkingHoursPolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'A working hours policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class WorkingHoursPolicyCreateSerializer(
    _WorkingHoursPolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = WorkingHoursPolicy
        fields = (
            'name',
            'policy_code',
            'description',
            'start_time',
            'end_time',
            'break_duration',
            'grace_period',
            'minimum_working_hours',
            'maximum_working_hours',
            'is_default',
            'is_active',
        )

    # ── Field-level validators ────────────────────────────────────────────────

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                'Policy name must be at least 3 characters long.'
            )
        if len(value) > 100:
            raise serializers.ValidationError(
                'Policy name must not exceed 100 characters.'
            )
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError(
                'Policy code must be at least 2 characters long.'
            )
        if WorkingHoursPolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'A working hours policy with code "{value}" already exists.'
            )
        return value

    def validate_break_duration(self, value: int) -> int:
        return self._validate_break_duration(value)

    def validate_grace_period(self, value: int) -> int:
        return self._validate_grace_period(value)

    def validate_minimum_working_hours(self, value: Decimal) -> Decimal:
        return self._validate_working_hours_field(value, 'Minimum working hours')

    def validate_maximum_working_hours(self, value: Decimal) -> Decimal:
        return self._validate_working_hours_field(value, 'Maximum working hours')

    # ── Cross-field validation ────────────────────────────────────────────────

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    # ── Save ─────────────────────────────────────────────────────────────────

    def create(self, validated_data: dict) -> WorkingHoursPolicy:
        # Enforce single-default invariant
        if validated_data.get('is_default'):
            WorkingHoursPolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class WorkingHoursPolicyUpdateSerializer(
    _WorkingHoursPolicyValidationMixin,
    serializers.ModelSerializer,
):
    """
    Used for both PUT (full update) and PATCH (partial update).
    policy_code is intentionally excluded — it is immutable after creation.
    """

    class Meta:
        model = WorkingHoursPolicy
        fields = (
            'name',
            'description',
            'start_time',
            'end_time',
            'break_duration',
            'grace_period',
            'minimum_working_hours',
            'maximum_working_hours',
            'is_default',
            'is_active',
        )

    # ── Field-level validators ────────────────────────────────────────────────

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                'Policy name must be at least 3 characters long.'
            )
        if len(value) > 100:
            raise serializers.ValidationError(
                'Policy name must not exceed 100 characters.'
            )
        return value

    def validate_break_duration(self, value: int) -> int:
        return self._validate_break_duration(value)

    def validate_grace_period(self, value: int) -> int:
        return self._validate_grace_period(value)

    def validate_minimum_working_hours(self, value: Decimal) -> Decimal:
        return self._validate_working_hours_field(value, 'Minimum working hours')

    def validate_maximum_working_hours(self, value: Decimal) -> Decimal:
        return self._validate_working_hours_field(value, 'Maximum working hours')

    # ── Cross-field validation ────────────────────────────────────────────────

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    # ── Save ─────────────────────────────────────────────────────────────────

    def update(self, instance: WorkingHoursPolicy, validated_data: dict) -> WorkingHoursPolicy:
        # Enforce single-default invariant: only clear others when *setting* this one as default
        if validated_data.get('is_default') and not instance.is_default:
            WorkingHoursPolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)


# ══════════════════════════════════════════════════════════════════════════════
#  Weekly Day Policy serializers
# ══════════════════════════════════════════════════════════════════════════════

_DAY_FIELDS = (
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
)

_VALID_DAY_TYPES = {choice[0] for choice in DAY_TYPE_CHOICES}


# ─── List ─────────────────────────────────────────────────────────────────────

class WeeklyDayPolicyListSerializer(serializers.ModelSerializer):
    """Minimal read-only representation used in paginated list responses."""

    working_days_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = WeeklyDayPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            *_DAY_FIELDS,
            'working_days_count',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class WeeklyDayPolicyRetrieveSerializer(serializers.ModelSerializer):
    """Full read-only representation including computed day-group lists."""

    working_days      = serializers.ListField(child=serializers.CharField(), read_only=True)
    weekly_off_days   = serializers.ListField(child=serializers.CharField(), read_only=True)
    half_day_off_days = serializers.ListField(child=serializers.CharField(), read_only=True)
    working_days_count = serializers.IntegerField(read_only=True)
    created_by_name   = serializers.SerializerMethodField()
    updated_by_name   = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyDayPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            *_DAY_FIELDS,
            'working_days',
            'weekly_off_days',
            'half_day_off_days',
            'working_days_count',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: WeeklyDayPolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: WeeklyDayPolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _WeeklyDayPolicyValidationMixin:

    def _validate_day_type(self, value: str, day_name: str) -> str:
        if value not in _VALID_DAY_TYPES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid day type for {day_name}. '
                f'Allowed values: {", ".join(sorted(_VALID_DAY_TYPES))}.'
            )
        return value

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        # ── At least one working day ─────────────────────────────────────────
        working_count = sum(
            1 for day in DAYS_OF_WEEK
            if _get(day, DAY_TYPE_WORKING) == DAY_TYPE_WORKING
        )
        if working_count == 0:
            raise serializers.ValidationError(
                'At least one day must be marked as a working day. '
                'A week with zero working days is not a valid work schedule.'
            )

        # ── Duplicate name check ─────────────────────────────────────────────
        name = _get('name')
        if name:
            qs = WeeklyDayPolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'A weekly day policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class WeeklyDayPolicyCreateSerializer(
    _WeeklyDayPolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = WeeklyDayPolicy
        fields = (
            'name',
            'policy_code',
            'description',
            *_DAY_FIELDS,
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError('Policy code must be at least 2 characters long.')
        if WeeklyDayPolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'A weekly day policy with code "{value}" already exists.'
            )
        return value

    def validate_monday(self, value: str)    -> str: return self._validate_day_type(value, 'Monday')
    def validate_tuesday(self, value: str)   -> str: return self._validate_day_type(value, 'Tuesday')
    def validate_wednesday(self, value: str) -> str: return self._validate_day_type(value, 'Wednesday')
    def validate_thursday(self, value: str)  -> str: return self._validate_day_type(value, 'Thursday')
    def validate_friday(self, value: str)    -> str: return self._validate_day_type(value, 'Friday')
    def validate_saturday(self, value: str)  -> str: return self._validate_day_type(value, 'Saturday')
    def validate_sunday(self, value: str)    -> str: return self._validate_day_type(value, 'Sunday')

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    def create(self, validated_data: dict) -> WeeklyDayPolicy:
        if validated_data.get('is_default'):
            WeeklyDayPolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class WeeklyDayPolicyUpdateSerializer(
    _WeeklyDayPolicyValidationMixin,
    serializers.ModelSerializer,
):
    """PUT / PATCH — policy_code is immutable after creation."""

    class Meta:
        model = WeeklyDayPolicy
        fields = (
            'name',
            'description',
            *_DAY_FIELDS,
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_monday(self, value: str)    -> str: return self._validate_day_type(value, 'Monday')
    def validate_tuesday(self, value: str)   -> str: return self._validate_day_type(value, 'Tuesday')
    def validate_wednesday(self, value: str) -> str: return self._validate_day_type(value, 'Wednesday')
    def validate_thursday(self, value: str)  -> str: return self._validate_day_type(value, 'Thursday')
    def validate_friday(self, value: str)    -> str: return self._validate_day_type(value, 'Friday')
    def validate_saturday(self, value: str)  -> str: return self._validate_day_type(value, 'Saturday')
    def validate_sunday(self, value: str)    -> str: return self._validate_day_type(value, 'Sunday')

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    def update(self, instance: WeeklyDayPolicy, validated_data: dict) -> WeeklyDayPolicy:
        if validated_data.get('is_default') and not instance.is_default:
            WeeklyDayPolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)


# ══════════════════════════════════════════════════════════════════════════════
#  Punch Rules Policy serializers
# ══════════════════════════════════════════════════════════════════════════════

_VALID_PUNCH_MODES        = {c[0] for c in PunchRulesPolicy.PUNCH_MODE_CHOICES}
_VALID_MISSING_PUNCH_ACTS = {c[0] for c in PunchRulesPolicy.MISSING_PUNCH_CHOICES}
_MAX_EARLY_CHECKOUT_GRACE = 120    # 2 h
_MAX_PUNCH_COUNT          = 20


# ─── List ─────────────────────────────────────────────────────────────────────

class PunchRulesPolicyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PunchRulesPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'punch_mode',
            'max_punch_count',
            'auto_checkout_enabled',
            'auto_checkout_time',
            'early_checkout_grace',
            'missing_punch_action',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class PunchRulesPolicyRetrieveSerializer(serializers.ModelSerializer):
    punch_mode_display        = serializers.CharField(source='get_punch_mode_display',        read_only=True)
    missing_punch_action_display = serializers.CharField(source='get_missing_punch_action_display', read_only=True)
    created_by_name           = serializers.SerializerMethodField()
    updated_by_name           = serializers.SerializerMethodField()

    class Meta:
        model = PunchRulesPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            'punch_mode',
            'punch_mode_display',
            'max_punch_count',
            'auto_checkout_enabled',
            'auto_checkout_time',
            'early_checkout_grace',
            'missing_punch_action',
            'missing_punch_action_display',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: PunchRulesPolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: PunchRulesPolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _PunchRulesPolicyValidationMixin:

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        punch_mode            = _get('punch_mode',            PunchRulesPolicy.PUNCH_MODE_MULTIPLE)
        max_punch_count       = _get('max_punch_count',       2)
        auto_checkout_enabled = _get('auto_checkout_enabled', False)
        auto_checkout_time    = _get('auto_checkout_time',    None)
        name                  = _get('name')

        # ── Single punch → max count is exactly 1 ───────────────────────────
        if punch_mode == PunchRulesPolicy.PUNCH_MODE_SINGLE:
            if 'max_punch_count' in attrs and attrs['max_punch_count'] != 1:
                raise serializers.ValidationError({
                    'max_punch_count': (
                        'Max punch count must be 1 when punch mode is "single". '
                        'In single-punch mode the system records one punch-in; '
                        'auto-checkout handles the punch-out.'
                    ),
                })
            attrs['max_punch_count'] = 1

        # ── Multiple punch → at least 2 ─────────────────────────────────────
        elif punch_mode == PunchRulesPolicy.PUNCH_MODE_MULTIPLE:
            if max_punch_count is not None and max_punch_count < 2:
                raise serializers.ValidationError({
                    'max_punch_count': (
                        'Max punch count must be at least 2 for multiple-punch mode '
                        '(minimum one IN punch and one OUT punch per day).'
                    ),
                })

        # ── Auto checkout requires a time ────────────────────────────────────
        if auto_checkout_enabled and not auto_checkout_time:
            raise serializers.ValidationError({
                'auto_checkout_time': (
                    'Auto checkout time is required when auto checkout is enabled.'
                ),
            })

        # ── Auto checkout time without the flag is a likely mistake ─────────
        if auto_checkout_time and not auto_checkout_enabled:
            raise serializers.ValidationError({
                'auto_checkout_time': (
                    'Auto checkout time is set but auto checkout is disabled. '
                    'Enable auto checkout or clear the time field.'
                ),
            })

        # ── Duplicate name ───────────────────────────────────────────────────
        if name:
            qs = PunchRulesPolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'A punch rules policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class PunchRulesPolicyCreateSerializer(
    _PunchRulesPolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = PunchRulesPolicy
        fields = (
            'name',
            'policy_code',
            'description',
            'punch_mode',
            'max_punch_count',
            'auto_checkout_enabled',
            'auto_checkout_time',
            'early_checkout_grace',
            'missing_punch_action',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError('Policy code must be at least 2 characters long.')
        if PunchRulesPolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'A punch rules policy with code "{value}" already exists.'
            )
        return value

    def validate_max_punch_count(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError('Max punch count must be at least 1.')
        if value > _MAX_PUNCH_COUNT:
            raise serializers.ValidationError(
                f'Max punch count cannot exceed {_MAX_PUNCH_COUNT}.'
            )
        return value

    def validate_early_checkout_grace(self, value: int) -> int:
        if value > _MAX_EARLY_CHECKOUT_GRACE:
            raise serializers.ValidationError(
                f'Early checkout grace cannot exceed {_MAX_EARLY_CHECKOUT_GRACE} minutes (2 hours).'
            )
        return value

    def validate_punch_mode(self, value: str) -> str:
        if value not in _VALID_PUNCH_MODES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid punch mode. '
                f'Allowed values: {", ".join(sorted(_VALID_PUNCH_MODES))}.'
            )
        return value

    def validate_missing_punch_action(self, value: str) -> str:
        if value not in _VALID_MISSING_PUNCH_ACTS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid missing punch action. '
                f'Allowed values: {", ".join(sorted(_VALID_MISSING_PUNCH_ACTS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    def create(self, validated_data: dict) -> PunchRulesPolicy:
        if validated_data.get('is_default'):
            PunchRulesPolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class PunchRulesPolicyUpdateSerializer(
    _PunchRulesPolicyValidationMixin,
    serializers.ModelSerializer,
):
    """PUT / PATCH — policy_code is immutable after creation."""

    class Meta:
        model = PunchRulesPolicy
        fields = (
            'name',
            'description',
            'punch_mode',
            'max_punch_count',
            'auto_checkout_enabled',
            'auto_checkout_time',
            'early_checkout_grace',
            'missing_punch_action',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_max_punch_count(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError('Max punch count must be at least 1.')
        if value > _MAX_PUNCH_COUNT:
            raise serializers.ValidationError(f'Max punch count cannot exceed {_MAX_PUNCH_COUNT}.')
        return value

    def validate_early_checkout_grace(self, value: int) -> int:
        if value > _MAX_EARLY_CHECKOUT_GRACE:
            raise serializers.ValidationError(
                f'Early checkout grace cannot exceed {_MAX_EARLY_CHECKOUT_GRACE} minutes (2 hours).'
            )
        return value

    def validate_punch_mode(self, value: str) -> str:
        if value not in _VALID_PUNCH_MODES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid punch mode. '
                f'Allowed values: {", ".join(sorted(_VALID_PUNCH_MODES))}.'
            )
        return value

    def validate_missing_punch_action(self, value: str) -> str:
        if value not in _VALID_MISSING_PUNCH_ACTS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid missing punch action. '
                f'Allowed values: {", ".join(sorted(_VALID_MISSING_PUNCH_ACTS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    def update(self, instance: PunchRulesPolicy, validated_data: dict) -> PunchRulesPolicy:
        if validated_data.get('is_default') and not instance.is_default:
            PunchRulesPolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)


# ══════════════════════════════════════════════════════════════════════════════
#  Overtime Policy serializers
# ══════════════════════════════════════════════════════════════════════════════

_VALID_ROUND_OFF_RULES  = {c[0] for c in OvertimePolicy.ROUND_OFF_CHOICES}
_VALID_APPROVAL_TYPES   = {c[0] for c in OvertimePolicy.APPROVAL_CHOICES}
_MAX_OT_MULTIPLIER      = Decimal('5.0')
_MIN_OT_MULTIPLIER      = Decimal('1.0')
_MAX_OT_MINUTES_PER_DAY = 720   # 12 h


# ─── List ─────────────────────────────────────────────────────────────────────

class OvertimePolicyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = OvertimePolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'minimum_overtime_minutes',
            'maximum_overtime_minutes_per_day',
            'maximum_overtime_minutes_per_month',
            'round_off_rule',
            'approval_type',
            'count_holiday_overtime',
            'count_weekly_off_overtime',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class OvertimePolicyRetrieveSerializer(serializers.ModelSerializer):
    round_off_rule_display  = serializers.CharField(source='get_round_off_rule_display',  read_only=True)
    approval_type_display   = serializers.CharField(source='get_approval_type_display',   read_only=True)
    created_by_name         = serializers.SerializerMethodField()
    updated_by_name         = serializers.SerializerMethodField()

    class Meta:
        model = OvertimePolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            'minimum_overtime_minutes',
            'maximum_overtime_minutes_per_day',
            'maximum_overtime_minutes_per_month',
            'round_off_rule',
            'round_off_rule_display',
            'approval_type',
            'approval_type_display',
            'count_holiday_overtime',
            'holiday_overtime_multiplier',
            'count_weekly_off_overtime',
            'weekly_off_overtime_multiplier',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: OvertimePolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: OvertimePolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _OvertimePolicyValidationMixin:

    def _validate_multiplier(self, value: Decimal, label: str) -> Decimal:
        if value < _MIN_OT_MULTIPLIER:
            raise serializers.ValidationError(
                f'{label} must be at least {_MIN_OT_MULTIPLIER} '
                '(employees cannot be paid less than regular rate for overtime).'
            )
        if value > _MAX_OT_MULTIPLIER:
            raise serializers.ValidationError(
                f'{label} cannot exceed {_MAX_OT_MULTIPLIER}.'
            )
        return value

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        min_ot        = _get('minimum_overtime_minutes',           30)
        max_ot_day    = _get('maximum_overtime_minutes_per_day',   0)
        max_ot_month  = _get('maximum_overtime_minutes_per_month', 0)
        name          = _get('name')

        # ── min OT must fit within the daily cap (when cap is set) ───────────
        if max_ot_day and max_ot_day > 0 and min_ot > max_ot_day:
            raise serializers.ValidationError({
                'minimum_overtime_minutes': (
                    f'Minimum overtime threshold ({min_ot} min) cannot exceed the '
                    f'daily overtime cap ({max_ot_day} min). '
                    'Lower the minimum threshold or raise the daily cap.'
                ),
            })

        # ── daily cap must fit within the monthly cap (when both are set) ───
        if max_ot_day and max_ot_month:
            # 26 working days is the typical maximum working month
            if max_ot_day * 26 < max_ot_month:
                raise serializers.ValidationError({
                    'maximum_overtime_minutes_per_month': (
                        f'Monthly overtime cap ({max_ot_month} min) cannot be reached given the '
                        f'daily cap ({max_ot_day} min × 26 days = {max_ot_day * 26} min). '
                        'Raise the daily cap or lower the monthly cap.'
                    ),
                })

        # ── duplicate name ────────────────────────────────────────────────────
        if name:
            qs = OvertimePolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'An overtime policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class OvertimePolicyCreateSerializer(
    _OvertimePolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = OvertimePolicy
        fields = (
            'name',
            'policy_code',
            'description',
            'minimum_overtime_minutes',
            'maximum_overtime_minutes_per_day',
            'maximum_overtime_minutes_per_month',
            'round_off_rule',
            'approval_type',
            'count_holiday_overtime',
            'holiday_overtime_multiplier',
            'count_weekly_off_overtime',
            'weekly_off_overtime_multiplier',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError('Policy code must be at least 2 characters long.')
        if OvertimePolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'An overtime policy with code "{value}" already exists.'
            )
        return value

    def validate_minimum_overtime_minutes(self, value: int) -> int:
        if value > _MAX_OT_MINUTES_PER_DAY:
            raise serializers.ValidationError(
                f'Minimum overtime minutes cannot exceed {_MAX_OT_MINUTES_PER_DAY} minutes (12 hours).'
            )
        return value

    def validate_maximum_overtime_minutes_per_day(self, value: int) -> int:
        if value > _MAX_OT_MINUTES_PER_DAY:
            raise serializers.ValidationError(
                f'Daily overtime cap cannot exceed {_MAX_OT_MINUTES_PER_DAY} minutes (12 hours).'
            )
        return value

    def validate_round_off_rule(self, value: str) -> str:
        if value not in _VALID_ROUND_OFF_RULES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid round-off rule. '
                f'Allowed values: {", ".join(sorted(_VALID_ROUND_OFF_RULES))}.'
            )
        return value

    def validate_approval_type(self, value: str) -> str:
        if value not in _VALID_APPROVAL_TYPES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid approval type. '
                f'Allowed values: {", ".join(sorted(_VALID_APPROVAL_TYPES))}.'
            )
        return value

    def validate_holiday_overtime_multiplier(self, value: Decimal) -> Decimal:
        return self._validate_multiplier(value, 'Holiday overtime multiplier')

    def validate_weekly_off_overtime_multiplier(self, value: Decimal) -> Decimal:
        return self._validate_multiplier(value, 'Weekly-off overtime multiplier')

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    def create(self, validated_data: dict) -> OvertimePolicy:
        if validated_data.get('is_default'):
            OvertimePolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class OvertimePolicyUpdateSerializer(
    _OvertimePolicyValidationMixin,
    serializers.ModelSerializer,
):
    """PUT / PATCH — policy_code is immutable after creation."""

    class Meta:
        model = OvertimePolicy
        fields = (
            'name',
            'description',
            'minimum_overtime_minutes',
            'maximum_overtime_minutes_per_day',
            'maximum_overtime_minutes_per_month',
            'round_off_rule',
            'approval_type',
            'count_holiday_overtime',
            'holiday_overtime_multiplier',
            'count_weekly_off_overtime',
            'weekly_off_overtime_multiplier',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_minimum_overtime_minutes(self, value: int) -> int:
        if value > _MAX_OT_MINUTES_PER_DAY:
            raise serializers.ValidationError(
                f'Minimum overtime minutes cannot exceed {_MAX_OT_MINUTES_PER_DAY} minutes (12 hours).'
            )
        return value

    def validate_maximum_overtime_minutes_per_day(self, value: int) -> int:
        if value > _MAX_OT_MINUTES_PER_DAY:
            raise serializers.ValidationError(
                f'Daily overtime cap cannot exceed {_MAX_OT_MINUTES_PER_DAY} minutes (12 hours).'
            )
        return value

    def validate_round_off_rule(self, value: str) -> str:
        if value not in _VALID_ROUND_OFF_RULES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid round-off rule. '
                f'Allowed values: {", ".join(sorted(_VALID_ROUND_OFF_RULES))}.'
            )
        return value

    def validate_approval_type(self, value: str) -> str:
        if value not in _VALID_APPROVAL_TYPES:
            raise serializers.ValidationError(
                f'"{value}" is not a valid approval type. '
                f'Allowed values: {", ".join(sorted(_VALID_APPROVAL_TYPES))}.'
            )
        return value

    def validate_holiday_overtime_multiplier(self, value: Decimal) -> Decimal:
        return self._validate_multiplier(value, 'Holiday overtime multiplier')

    def validate_weekly_off_overtime_multiplier(self, value: Decimal) -> Decimal:
        return self._validate_multiplier(value, 'Weekly-off overtime multiplier')

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    def update(self, instance: OvertimePolicy, validated_data: dict) -> OvertimePolicy:
        if validated_data.get('is_default') and not instance.is_default:
            OvertimePolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)


# ══════════════════════════════════════════════════════════════════════════════
#  Late Mark & LOP Policy serializers
# ══════════════════════════════════════════════════════════════════════════════

_VALID_LOP_UNITS    = {c[0] for c in LateMarkLOPPolicy.LOP_UNIT_CHOICES}
_MAX_LATE_MARKS_PER_LOP = 31   # one per working day; beyond that makes no business sense


# ─── List ─────────────────────────────────────────────────────────────────────

class LateMarkLOPPolicyListSerializer(serializers.ModelSerializer):
    is_lop_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = LateMarkLOPPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'late_marks_per_lop',
            'lop_deduction_unit',
            'is_lop_enabled',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class LateMarkLOPPolicyRetrieveSerializer(serializers.ModelSerializer):
    is_lop_enabled         = serializers.BooleanField(read_only=True)
    lop_deduction_unit_display = serializers.CharField(
        source='get_lop_deduction_unit_display', read_only=True,
    )
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LateMarkLOPPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            'late_marks_per_lop',
            'lop_deduction_unit',
            'lop_deduction_unit_display',
            'is_lop_enabled',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: LateMarkLOPPolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: LateMarkLOPPolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _LateMarkLOPPolicyValidationMixin:

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        late_marks_per_lop = _get('late_marks_per_lop', 3)
        name               = _get('name')

        # ── late_marks_per_lop=1 means every single late arrival triggers LOP ──
        # That is valid but worth noting; no rule prevents it. No cross-field
        # dependency here beyond the range check done at field level.

        # ── lop_deduction_unit is meaningless when lop is disabled ───────────
        lop_unit = _get('lop_deduction_unit', LateMarkLOPPolicy.LOP_UNIT_FULL_DAY)
        if late_marks_per_lop == 0 and 'lop_deduction_unit' in attrs:
            # Accept the value but warn; we do not reject because storing the
            # preferred unit makes re-enabling later smoother.
            pass

        # ── Duplicate name check ──────────────────────────────────────────────
        if name:
            qs = LateMarkLOPPolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'A late mark/LOP policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class LateMarkLOPPolicyCreateSerializer(
    _LateMarkLOPPolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = LateMarkLOPPolicy
        fields = (
            'name',
            'policy_code',
            'description',
            'late_marks_per_lop',
            'lop_deduction_unit',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError('Policy code must be at least 2 characters long.')
        if LateMarkLOPPolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'A late mark/LOP policy with code "{value}" already exists.'
            )
        return value

    def validate_late_marks_per_lop(self, value: int) -> int:
        if value > _MAX_LATE_MARKS_PER_LOP:
            raise serializers.ValidationError(
                f'Late marks per LOP cannot exceed {_MAX_LATE_MARKS_PER_LOP}.'
            )
        return value

    def validate_lop_deduction_unit(self, value: str) -> str:
        if value not in _VALID_LOP_UNITS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid LOP deduction unit. '
                f'Allowed values: {", ".join(sorted(_VALID_LOP_UNITS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    def create(self, validated_data: dict) -> LateMarkLOPPolicy:
        if validated_data.get('is_default'):
            LateMarkLOPPolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class LateMarkLOPPolicyUpdateSerializer(
    _LateMarkLOPPolicyValidationMixin,
    serializers.ModelSerializer,
):
    """PUT / PATCH — policy_code is immutable after creation."""

    class Meta:
        model = LateMarkLOPPolicy
        fields = (
            'name',
            'description',
            'late_marks_per_lop',
            'lop_deduction_unit',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_late_marks_per_lop(self, value: int) -> int:
        if value > _MAX_LATE_MARKS_PER_LOP:
            raise serializers.ValidationError(
                f'Late marks per LOP cannot exceed {_MAX_LATE_MARKS_PER_LOP}.'
            )
        return value

    def validate_lop_deduction_unit(self, value: str) -> str:
        if value not in _VALID_LOP_UNITS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid LOP deduction unit. '
                f'Allowed values: {", ".join(sorted(_VALID_LOP_UNITS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    def update(self, instance: LateMarkLOPPolicy, validated_data: dict) -> LateMarkLOPPolicy:
        if validated_data.get('is_default') and not instance.is_default:
            LateMarkLOPPolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)


# ══════════════════════════════════════════════════════════════════════════════
#  Absence Alert Policy serializers
# ══════════════════════════════════════════════════════════════════════════════

_VALID_NOTIFY_RECIPIENTS    = {c[0] for c in AbsenceAlertPolicy.NOTIFY_CHOICES}
_MAX_ABSENT_DAYS_THRESHOLD  = 30   # one full calendar month


# ─── List ─────────────────────────────────────────────────────────────────────

class AbsenceAlertPolicyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbsenceAlertPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'is_enabled',
            'absent_days_threshold',
            'notification_recipients',
            'is_default',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


# ─── Retrieve ─────────────────────────────────────────────────────────────────

class AbsenceAlertPolicyRetrieveSerializer(serializers.ModelSerializer):
    notification_recipients_display = serializers.CharField(
        source='get_notification_recipients_display', read_only=True,
    )
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AbsenceAlertPolicy
        fields = (
            'id',
            'name',
            'policy_code',
            'description',
            'is_enabled',
            'absent_days_threshold',
            'notification_recipients',
            'notification_recipients_display',
            'is_default',
            'is_active',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj: AbsenceAlertPolicy) -> str | None:
        return obj.created_by.full_name if obj.created_by else None

    def get_updated_by_name(self, obj: AbsenceAlertPolicy) -> str | None:
        return obj.updated_by.full_name if obj.updated_by else None


# ─── Shared validation mixin ──────────────────────────────────────────────────

class _AbsenceAlertPolicyValidationMixin:

    def _cross_field_validate(self, attrs: dict, instance=None) -> dict:
        def _get(field, default=None):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, default) if instance else default

        name = _get('name')

        # ── Duplicate name check ──────────────────────────────────────────────
        if name:
            qs = AbsenceAlertPolicy.objects.filter(name__iexact=name.strip())
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'name': f'An absence alert policy named "{name}" already exists.',
                })

        return attrs


# ─── Create ───────────────────────────────────────────────────────────────────

class AbsenceAlertPolicyCreateSerializer(
    _AbsenceAlertPolicyValidationMixin,
    serializers.ModelSerializer,
):
    class Meta:
        model = AbsenceAlertPolicy
        fields = (
            'name',
            'policy_code',
            'description',
            'is_enabled',
            'absent_days_threshold',
            'notification_recipients',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_policy_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 2:
            raise serializers.ValidationError('Policy code must be at least 2 characters long.')
        if AbsenceAlertPolicy.objects.filter(policy_code__iexact=value).exists():
            raise serializers.ValidationError(
                f'An absence alert policy with code "{value}" already exists.'
            )
        return value

    def validate_absent_days_threshold(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                'Absent days threshold must be at least 1.'
            )
        if value > _MAX_ABSENT_DAYS_THRESHOLD:
            raise serializers.ValidationError(
                f'Absent days threshold cannot exceed {_MAX_ABSENT_DAYS_THRESHOLD} days.'
            )
        return value

    def validate_notification_recipients(self, value: str) -> str:
        if value not in _VALID_NOTIFY_RECIPIENTS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid recipient option. '
                f'Allowed values: {", ".join(sorted(_VALID_NOTIFY_RECIPIENTS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=None)

    def create(self, validated_data: dict) -> AbsenceAlertPolicy:
        if validated_data.get('is_default'):
            AbsenceAlertPolicy.objects.filter(is_default=True).update(is_default=False)
        return super().create(validated_data)


# ─── Update ───────────────────────────────────────────────────────────────────

class AbsenceAlertPolicyUpdateSerializer(
    _AbsenceAlertPolicyValidationMixin,
    serializers.ModelSerializer,
):
    """PUT / PATCH — policy_code is immutable after creation."""

    class Meta:
        model = AbsenceAlertPolicy
        fields = (
            'name',
            'description',
            'is_enabled',
            'absent_days_threshold',
            'notification_recipients',
            'is_default',
            'is_active',
        )

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('Policy name must be at least 3 characters long.')
        if len(value) > 100:
            raise serializers.ValidationError('Policy name must not exceed 100 characters.')
        return value

    def validate_absent_days_threshold(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                'Absent days threshold must be at least 1.'
            )
        if value > _MAX_ABSENT_DAYS_THRESHOLD:
            raise serializers.ValidationError(
                f'Absent days threshold cannot exceed {_MAX_ABSENT_DAYS_THRESHOLD} days.'
            )
        return value

    def validate_notification_recipients(self, value: str) -> str:
        if value not in _VALID_NOTIFY_RECIPIENTS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid recipient option. '
                f'Allowed values: {", ".join(sorted(_VALID_NOTIFY_RECIPIENTS))}.'
            )
        return value

    def validate(self, attrs: dict) -> dict:
        return self._cross_field_validate(attrs, instance=self.instance)

    def update(self, instance: AbsenceAlertPolicy, validated_data: dict) -> AbsenceAlertPolicy:
        if validated_data.get('is_default') and not instance.is_default:
            AbsenceAlertPolicy.objects.filter(is_default=True).exclude(pk=instance.pk).update(
                is_default=False
            )
        return super().update(instance, validated_data)
