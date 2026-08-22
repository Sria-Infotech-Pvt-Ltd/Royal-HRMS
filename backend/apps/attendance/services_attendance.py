"""
My Attendance service layer.

Three services, each with a single responsibility:

  PunchService               — clock-in / clock-out business logic
  AttendanceProcessorService — converts raw punches into one AttendanceRecord per day
  AttendanceDashboardService — reads processed records for API responses (zero calculations)

The dashboard never touches AttendancePunch.  All computation happens in the
processor, which runs synchronously after every web punch.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

_IST = ZoneInfo('Asia/Kolkata')

from apps.attendance.models import (
    AttendancePunch,
    AttendanceRecord,
    AttendanceSettings,
)

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_settings() -> Optional[AttendanceSettings]:
    from core.cache_service import AttendanceSettingsCacheService
    return AttendanceSettingsCacheService.get()


def _minutes_to_display(minutes: int) -> str:
    """Converts 547 → '9h 07m' (format the frontend expects)."""
    if not minutes:
        return '—'
    h = minutes // 60
    m = minutes % 60
    return f'{h}h {m:02d}m'


def _time_to_display(t: Optional[time]) -> Optional[str]:
    """Converts time(9, 3) → '09:03'."""
    return t.strftime('%H:%M') if t else None


def _ist_time(dt: datetime) -> time:
    """Return the IST wall-clock time for a UTC-aware datetime from punched_at.

    punched_at is stored as UTC (timezone.now()).  shift_start / shift_end in
    AttendanceWorkingHours are plain IST times.  Comparing them correctly requires
    converting the punch timestamp to IST before extracting the time component.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    return dt.astimezone(_IST).time()


# ══════════════════════════════════════════════════════════════════════════════
#  PunchService
# ══════════════════════════════════════════════════════════════════════════════

class PunchService:
    """
    Handles Clock In and Clock Out with geofence validation.

    Rules enforced:
    - Cannot punch IN when already clocked in.
    - Cannot punch OUT when not clocked in.
    - Office mode: employee must be within branch geofence (if configured).
    - Full audit trail stored on every punch (GPS, IP, device, distance).
    - After each successful punch the processor runs to keep AttendanceRecord current.
    """

    @classmethod
    def record_punch(cls, employee, punch_data: dict) -> AttendancePunch:
        """
        Unified entry point for Clock In and Clock Out.

        punch_data keys (all from validated serializer):
          punch_type      — 'IN' | 'OUT'
          source          — 'web' | 'mobile' | 'biometric' | 'manual' | 'voice'
          attendance_mode — 'office' | 'wfh' | 'field' | ...
          latitude        — float or None
          longitude       — float or None
          accuracy        — float or None
          device_time     — datetime or None
          device_name     — str
          device_id       — str
          browser         — str
          operating_system— str
          face_embedding  — list[float] or None (web/voice only — see FaceVerificationService)
          liveness_passed — bool or None (only meaningful alongside face_embedding)
          liveness_score  — float or None (only meaningful alongside face_embedding)
          capture_session_id — str (client-generated UUID per camera session; used
                                for FaceVerificationService's anti-replay check)
          is_secure       — bool (injected by the view from request.is_secure())
          ip_address      — str or None  (injected by the view from request)

        Raises ValueError with a user-facing message on validation failure.
        Raises PermissionError with a user-facing message on geofence or
        face-verification failure.
        """
        from apps.attendance.services_geofencing import GeofencingService
        from apps.attendance.services_face_matching import FaceVerificationService

        now        = timezone.now()
        today      = timezone.localdate()   # IST calendar date — not now.date() (UTC)
        punch_type = punch_data['punch_type']
        source     = punch_data.get('source', AttendancePunch.SOURCE_WEB)
        mode       = punch_data.get('attendance_mode', AttendancePunch.MODE_OFFICE)

        # ── Consecutive punch validation ──────────────────────────────────────
        if punch_type == AttendancePunch.PUNCH_IN and cls._is_clocked_in(employee, today):
            raise ValueError(
                'You are already clocked in. Please clock out before clocking in again.'
            )
        if punch_type == AttendancePunch.PUNCH_OUT and not cls._is_clocked_in(employee, today):
            raise ValueError(
                'You are not currently clocked in. Please clock in first.'
            )

        # ── Geofence validation ───────────────────────────────────────────────
        # Runs BEFORE face verification (matches apps/voice_commands
        # /conversation_clock_in_face.py's already-reasoned ordering — see
        # that module's docstring). A punch from outside an office branch's
        # geofence is rejected for that reason specifically, rather than an
        # employee who's simply in the wrong place also having their face
        # capture attempted/fail first and seeing a confusing face-related
        # error that has nothing to do with the actual blocker.
        geo = GeofencingService.validate(
            employee=employee,
            attendance_mode=mode,
            employee_lat=punch_data.get('latitude'),
            employee_lon=punch_data.get('longitude'),
            employee_accuracy=punch_data.get('accuracy'),
        )
        if not geo.is_allowed:
            raise PermissionError(geo.rejection_message)

        # ── Face verification (web/voice only, only when employee has an
        #    approved registration) ────────────────────────────────────────────
        face = FaceVerificationService.verify_for_punch(
            employee, source, punch_data.get('face_embedding'),
            capture_session_id=punch_data.get('capture_session_id') or '',
            liveness_passed=punch_data.get('liveness_passed'),
            liveness_score=punch_data.get('liveness_score'),
            is_secure=punch_data.get('is_secure', True),
        )
        if face.required and not face.embedding_provided:
            raise ValueError(face.rejection_message)
        if face.required and face.embedding_provided and not face.is_match:
            raise PermissionError(face.rejection_message)

        # ── Persist punch with full audit trail ───────────────────────────────
        with transaction.atomic():
            punch = AttendancePunch.objects.create(
                employee=employee,
                branch=geo.branch,
                punch_type=punch_type,
                punched_at=now,
                device_time=punch_data.get('device_time'),
                source=punch_data.get('source', AttendancePunch.SOURCE_WEB),
                attendance_mode=mode,
                latitude=punch_data.get('latitude'),
                longitude=punch_data.get('longitude'),
                accuracy=punch_data.get('accuracy'),
                calculated_distance=geo.calculated_distance,
                is_inside_geofence=geo.is_inside_geofence,
                ip_address=punch_data.get('ip_address'),
                browser=punch_data.get('browser', ''),
                operating_system=punch_data.get('operating_system', ''),
                device_name=punch_data.get('device_name', ''),
                device_id=punch_data.get('device_id', ''),
                face_verified=face.is_match if face.required else False,
                face_match_distance=face.distance,
            )

        record = AttendanceProcessorService.process_day(employee, today)
        _write_punch_audit(punch, record, employee, today)
        logger.info(
            'Punch %s: employee=%s mode=%s geofence=%s distance=%sm',
            punch_type, employee.pk, mode,
            geo.is_inside_geofence, geo.calculated_distance,
        )
        return punch

    @classmethod
    def get_today_session(cls, employee) -> dict:
        """
        Returns all data needed to render ClockWidget:
          is_clocked_in, punches[], total_seconds, session_seconds
        """
        now   = timezone.now()
        today = timezone.localdate()   # IST calendar date

        punches = list(
            AttendancePunch.objects
            .select_related('branch')
            .filter(employee=employee, punched_at__date=today)
            .order_by('punched_at')
        )

        is_clocked_in = cls._is_clocked_in(employee, today)

        punch_list = [
            {
                'type':                p.punch_type,
                'time':                p.punch_time_display,
                'location':            _build_location_label(employee, p),
                'attendance_mode':     p.attendance_mode,
                'is_inside_geofence':  p.is_inside_geofence,
                'calculated_distance': float(p.calculated_distance) if p.calculated_distance is not None else None,
            }
            for p in punches
        ]

        total_seconds   = cls._compute_total_seconds(punches, now)
        session_seconds = cls._compute_session_seconds(punches, now, is_clocked_in)

        return {
            'is_clocked_in':   is_clocked_in,
            'punches':         punch_list,
            'total_seconds':   total_seconds,
            'session_seconds': session_seconds,
            'date_display':    today.strftime('%A, %d %B %Y'),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _is_clocked_in(employee, for_date: date) -> bool:
        """
        An employee is clocked in if the last punch of the day is an IN.
        """
        last = (
            AttendancePunch.objects
            .filter(employee=employee, punched_at__date=for_date)
            .order_by('-punched_at')
            .values_list('punch_type', flat=True)
            .first()
        )
        return last == AttendancePunch.PUNCH_IN

    @staticmethod
    def _compute_total_seconds(punches: list, now: datetime) -> int:
        """
        Sums all completed IN→OUT pairs plus any open session if still clocked in.
        """
        total = 0
        last_in: Optional[datetime] = None

        for p in punches:
            if p.punch_type == AttendancePunch.PUNCH_IN:
                last_in = p.punched_at
            elif p.punch_type == AttendancePunch.PUNCH_OUT and last_in is not None:
                total  += int((p.punched_at - last_in).total_seconds())
                last_in = None

        # Open session still running
        if last_in is not None:
            total += int((now - last_in).total_seconds())

        return total

    @staticmethod
    def _compute_session_seconds(punches: list, now: datetime, is_clocked_in: bool) -> int:
        """Seconds since the most recent IN punch (current open session)."""
        if not is_clocked_in:
            return 0
        for p in reversed(punches):
            if p.punch_type == AttendancePunch.PUNCH_IN:
                return int((now - p.punched_at).total_seconds())
        return 0


# ══════════════════════════════════════════════════════════════════════════════
#  AttendanceProcessorService
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceProcessorService:
    """
    Converts raw punches into a single AttendanceRecord for (employee, date).

    Called synchronously after every web punch.  For batch/backfill, call
    process_day() directly from a management command.
    """

    @classmethod
    def process_day(cls, employee, for_date: date) -> AttendanceRecord:
        """Build or update the AttendanceRecord for this employee on this date."""
        cfg         = _get_settings()
        branch_name = getattr(employee, 'branch', '') or ''
        punches     = list(
            AttendancePunch.objects
            .filter(employee=employee, punched_at__date=for_date)
            .order_by('punched_at')
        )

        # Holiday check takes priority over weekly off and punch calculation
        if cls._is_holiday(for_date, branch_name):
            record_data = {
                'status':                AttendanceRecord.STATUS_HOLIDAY,
                'first_punch_in':        None,
                'last_punch_out':        None,
                'total_working_minutes': 0,
                'overtime_minutes':      0,
                'is_late':               False,
                'is_early_exit':         False,
                'note':                  cls._holiday_name(for_date, branch_name),
            }
        # Weekly off with no punches → mark weekly_off, not absent
        elif not punches and cls._is_weekly_off(employee, for_date):
            record_data = {
                'status':                AttendanceRecord.STATUS_WEEKLY_OFF,
                'first_punch_in':        None,
                'last_punch_out':        None,
                'total_working_minutes': 0,
                'overtime_minutes':      0,
                'is_late':               False,
                'is_early_exit':         False,
                'note':                  'Weekly off',
            }
        else:
            record_data = cls._calculate(punches, for_date, cfg)

        # work_mode is orthogonal to status (presence/absence) — a day can be
        # "present" and "wfh" at once — so it's derived here on every
        # (re)build of the record, not just set once at leave-style approval
        # time, the same lookup punch-time geofence validation uses.
        from apps.hrms.models import WorkFromHomeRequest
        record_data['work_mode'] = (
            AttendanceRecord.WORK_MODE_WFH
            if WorkFromHomeRequest.approved_for(employee, for_date)
            else AttendanceRecord.WORK_MODE_OFFICE
        )

        record, _ = AttendanceRecord.objects.update_or_create(
            employee=employee,
            date=for_date,
            defaults=record_data,
        )
        return record

    @staticmethod
    def _is_holiday(for_date: date, branch_name: str = '') -> bool:
        """Return True if for_date is an active holiday for this branch."""
        from apps.hrms.models import Holiday
        from django.db.models import Q
        qs = Holiday.objects.filter(date=for_date, is_active=True)
        if branch_name:
            qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=branch_name))
        else:
            qs = qs.filter(branch__isnull=True)
        return qs.exists()

    @staticmethod
    def _holiday_name(for_date: date, branch_name: str = '') -> str:
        """Returns the specific holiday's name for for_date, falling back to 'Holiday'."""
        from core.cache_service import HolidayCacheService
        holidays = HolidayCacheService.get_holidays_with_names(for_date, for_date, branch_name)
        return holidays[0]['name'] if holidays else 'Holiday'

    @staticmethod
    def _is_weekly_off(employee, for_date: date) -> bool:
        """
        Return True if `for_date` is a configured weekly off day for `employee`.

        Resolves via the centralized WeeklyOffCacheService.get_effective():
        the employee's own EmployeeWeeklyOffAssignment (if one covers this
        date) takes priority, falling back to the org-wide default (unchanged
        from before this method resolved employee-specific assignments).
        """
        from core.cache_service import WeeklyOffCacheService
        day_name = for_date.strftime('%A').lower()   # 'monday' … 'sunday'
        return day_name in WeeklyOffCacheService.get_effective(employee, for_date)

    # ── Calculation ───────────────────────────────────────────────────────────

    @classmethod
    def _calculate(cls, punches: list, for_date: date, cfg) -> dict:
        """
        Returns a dict suitable for AttendanceRecord.objects.update_or_create(defaults=...).
        """
        if not punches:
            return cls._no_punch_record(for_date, cfg)

        # Pair IN→OUT punches
        pairs: list[tuple[datetime, Optional[datetime]]] = []
        last_in: Optional[datetime] = None

        for p in punches:
            if p.punch_type == AttendancePunch.PUNCH_IN:
                last_in = p.punched_at
            elif p.punch_type == AttendancePunch.PUNCH_OUT and last_in is not None:
                pairs.append((last_in, p.punched_at))
                last_in = None

        # Open session (employee still IN, no OUT yet)
        if last_in is not None:
            pairs.append((last_in, None))

        if not pairs:
            return cls._no_punch_record(for_date, cfg)

        first_in   = punches[0].punched_at
        last_punch = punches[-1]
        last_out   = last_punch.punched_at if last_punch.punch_type == AttendancePunch.PUNCH_OUT else None

        # Net working minutes: sum all closed pairs only
        closed_minutes = sum(
            int((out - in_).total_seconds() / 60)
            for in_, out in pairs
            if out is not None
        )

        # Deduct break if configured
        break_deduction = 0
        if cfg and hasattr(cfg, 'working_hours'):
            break_deduction = cfg.working_hours.break_duration_minutes
        net_minutes = max(0, closed_minutes - break_deduction)

        # Determine status
        has_open_session    = any(out is None for _, out in pairs)
        has_complete_pair   = any(out is not None for _, out in pairs)
        is_late             = cls._check_late(_ist_time(first_in), cfg)
        is_early_exit       = cls._check_early_exit(_ist_time(last_out) if last_out else None, cfg)
        status              = cls._resolve_status(
            net_minutes, is_late, cfg, has_open_session, has_complete_pair
        )

        # Overtime
        ot_minutes = cls._calc_overtime(net_minutes, cfg)

        note = ''
        if is_late:
            grace = cfg.working_hours.grace_period_minutes if cfg and hasattr(cfg, 'working_hours') else 0
            note = 'Grace exceeded' if grace else 'Late arrival'

        return {
            'status':                status,
            'first_punch_in':        _ist_time(first_in),
            'last_punch_out':        _ist_time(last_out) if last_out else None,
            'total_working_minutes': net_minutes,
            'overtime_minutes':      ot_minutes,
            'is_late':               is_late,
            'is_early_exit':         is_early_exit,
            'note':                  note,
        }

    @staticmethod
    def _no_punch_record(for_date: date, cfg) -> dict:
        """Status for a working day with zero punches."""
        return {
            'status':                AttendanceRecord.STATUS_ABSENT,
            'first_punch_in':        None,
            'last_punch_out':        None,
            'total_working_minutes': 0,
            'overtime_minutes':      0,
            'is_late':               False,
            'is_early_exit':         False,
            'note':                  'No punch recorded',
        }

    @staticmethod
    def _check_late(punch_in_time: time, cfg) -> bool:
        if not cfg or not hasattr(cfg, 'working_hours'):
            return False
        wh = cfg.working_hours
        grace_end = (
            datetime.combine(date.today(), wh.shift_start)
            + timedelta(minutes=wh.grace_period_minutes)
        ).time()
        return punch_in_time > grace_end

    @staticmethod
    def _check_early_exit(punch_out_time: Optional[time], cfg) -> bool:
        if not punch_out_time or not cfg or not hasattr(cfg, 'working_hours'):
            return False
        wh = cfg.working_hours
        early_threshold = (
            datetime.combine(date.today(), wh.shift_end)
            - timedelta(minutes=30)
        ).time()
        return punch_out_time < early_threshold

    @staticmethod
    def _resolve_status(
        net_minutes: int,
        is_late: bool,
        cfg,
        has_open_session: bool = False,
        has_complete_pair: bool = False,
    ) -> str:
        # Still clocked in — mark present/late immediately, don't wait for hours
        if has_open_session:
            return AttendanceRecord.STATUS_LATE if is_late else AttendanceRecord.STATUS_PRESENT

        if not cfg or not hasattr(cfg, 'punch_rules'):
            min_full = 480
            min_half = 240
        else:
            pr = cfg.punch_rules
            min_full = int(float(pr.min_hours_full_day) * 60)
            min_half = int(float(pr.min_hours_half_day) * 60)

        if net_minutes >= min_full:
            return AttendanceRecord.STATUS_LATE if is_late else AttendanceRecord.STATUS_PRESENT
        if net_minutes >= min_half:
            return AttendanceRecord.STATUS_HALF_DAY
        # Employee did physically clock in and out — floor at half_day, not absent
        if has_complete_pair:
            return AttendanceRecord.STATUS_HALF_DAY
        return AttendanceRecord.STATUS_ABSENT

    @staticmethod
    def _calc_overtime(net_minutes: int, cfg) -> int:
        if not cfg or not hasattr(cfg, 'overtime_rules'):
            return 0
        threshold = int(float(cfg.overtime_rules.ot_threshold_hours) * 60)
        return max(0, net_minutes - threshold)


# Status → hex colour used by CalendarGrid and DayRecordSerializer
_STATUS_COLOR: dict[str, str] = {
    AttendanceRecord.STATUS_PRESENT:    '#22c55e',   # green-500
    AttendanceRecord.STATUS_LATE:       '#f59e0b',   # amber-500
    AttendanceRecord.STATUS_ABSENT:     '#ef4444',   # red-500
    AttendanceRecord.STATUS_HALF_DAY:   '#f97316',   # orange-500
    AttendanceRecord.STATUS_WEEKLY_OFF: '#94a3b8',   # slate-400
    AttendanceRecord.STATUS_HOLIDAY:    '#a855f7',   # purple-500
    AttendanceRecord.STATUS_ON_LEAVE:   '#3b82f6',   # blue-500
    AttendanceRecord.STATUS_INCOMPLETE: '#f59e0b',   # amber-500 (same as late)
}


# ══════════════════════════════════════════════════════════════════════════════
#  AttendanceDashboardService
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceDashboardService:
    """
    Reads AttendanceRecord to power the dashboard. Zero calculations here.
    Every value was already computed by the processor.
    """

    @classmethod
    def get_stats(cls, employee, year: int, month: int) -> dict:
        """
        Powers the four stat cards on the My Attendance page.
        """
        import calendar as _cal
        _, days_in_month = _cal.monthrange(year, month)
        month_start   = date(year, month, 1)
        month_end     = date(year, month, days_in_month)
        branch_name   = getattr(employee, 'branch', '') or ''
        records       = cls._month_records(employee, year, month)
        holiday_dates = cls._holiday_dates(month_start, month_end, branch_name)

        working_records = [
            r for r in records
            if r.status not in (
                AttendanceRecord.STATUS_WEEKLY_OFF,
                AttendanceRecord.STATUS_HOLIDAY,
            ) and r.date not in holiday_dates
        ]
        days_present  = sum(1 for r in records if r.status in (
            AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE,
        ))
        late_arrivals = sum(1 for r in records if r.is_late)
        working_days  = len(working_records)

        total_minutes = sum(r.total_working_minutes for r in records)
        avg_hours     = round(total_minutes / 60 / max(days_present, 1), 1)

        attendance_pct = (
            round(days_present / working_days * 100)
            if working_days else 0
        )

        lop_pending = sum(
            1 for r in records
            if r.status == AttendanceRecord.STATUS_ABSENT
            and r.date not in holiday_dates
        )

        return {
            'days_present':      days_present,
            'late_arrivals':     late_arrivals,
            'lop_pending':       lop_pending,
            'avg_hours_per_day': avg_hours,
            'attendance_percentage': attendance_pct,
            'working_days':      working_days,
        }

    @classmethod
    def get_monthly_summary(cls, employee, year: int, month: int) -> dict:
        """
        Powers the Monthly Summary grid (6-cell grid on the page).
        """
        import calendar as _cal
        _, days_in_month = _cal.monthrange(year, month)
        month_start   = date(year, month, 1)
        month_end     = date(year, month, days_in_month)
        branch_name   = getattr(employee, 'branch', '') or ''
        records       = cls._month_records(employee, year, month)
        holiday_dates = cls._holiday_dates(month_start, month_end, branch_name)

        working_days = sum(
            1 for r in records
            if r.status not in (
                AttendanceRecord.STATUS_WEEKLY_OFF, AttendanceRecord.STATUS_HOLIDAY,
            ) and r.date not in holiday_dates
        )
        days_present = sum(1 for r in records if r.status in (
            AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE,
        ))
        days_absent  = sum(
            1 for r in records
            if r.status == AttendanceRecord.STATUS_ABSENT
            and r.date not in holiday_dates
        )
        leave_days   = sum(1 for r in records if r.status == AttendanceRecord.STATUS_ON_LEAVE)
        half_days    = sum(1 for r in records if r.status == AttendanceRecord.STATUS_HALF_DAY)
        ot_minutes   = sum(r.overtime_minutes for r in records)
        ot_hours_display = _minutes_to_display(ot_minutes) if ot_minutes else '0h'

        return {
            'working_days': working_days,
            'days_present': days_present,
            'days_absent':  days_absent,
            'leave_days':   leave_days,
            'half_days':    half_days,
            'ot_hours':     ot_hours_display,
        }

    @classmethod
    def get_calendar(cls, employee, year: int, month: int) -> dict:
        """
        Returns per-day data keyed by day number (int) for every day of the month.
        Covers weekly-off days, approved leaves, and missing-clock-out (regularization).
        Shape matches CalendarGrid's Record<number, DayRecord>.
        """
        import calendar as _cal
        _, days_in_month = _cal.monthrange(year, month)
        month_start   = date(year, month, 1)
        month_end     = date(year, month, days_in_month)
        today         = timezone.localdate()
        branch_name   = getattr(employee, 'branch', '') or ''
        records       = {r.date: r for r in cls._month_records(employee, year, month)}
        leave_dates   = cls._leave_dates(employee, month_start, month_end)
        holiday_names = cls._holiday_names(month_start, month_end, branch_name)
        holiday_dates = set(holiday_names.keys())
        off_dates     = cls._weekly_off_dates(employee, month_start, month_end)
        pending_dates = cls._pending_correction_dates(employee, year, month)

        days: dict[int, dict] = {}
        for day_num in range(1, days_in_month + 1):
            entry = cls._build_day(
                day_num, year, month, records, leave_dates, off_dates,
                pending_dates, today, holiday_dates, holiday_names,
            )
            if entry is not None:
                days[day_num] = entry
        return {'days': days}

    @classmethod
    def get_history(cls, employee, year: int, month: int) -> list[dict]:
        """
        Returns the AttendanceHistory table rows for the given month,
        newest first.
        """
        records = (
            cls._month_records(employee, year, month)
        )
        rows = []
        for r in sorted(records, key=lambda x: x.date, reverse=True):
            can_regularize = r.status in (
                AttendanceRecord.STATUS_ABSENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_HALF_DAY,
            ) and not cls._has_pending_correction(employee, r.date)

            rows.append({
                'date':          r.date.strftime('%d %b'),
                'day':           r.date.strftime('%a'),
                'clockIn':       r.clock_in_display or '—',
                'clockOut':      r.clock_out_display or '—',
                'hours':         r.total_hours_display,
                'status':        r.status_display,
                'canRegularize': can_regularize,
            })
        return rows

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _month_records(employee, year: int, month: int) -> list[AttendanceRecord]:
        return list(
            AttendanceRecord.objects
            .filter(employee=employee, date__year=year, date__month=month)
            .order_by('date')
        )

    @staticmethod
    def _has_pending_correction(employee, for_date: date) -> bool:
        from apps.attendance.models import AttendanceCorrection
        return AttendanceCorrection.objects.filter(
            employee=employee,
            date=for_date,
            status=AttendanceCorrection.STATUS_PENDING,
        ).exists()

    @staticmethod
    def _pending_correction_dates(employee, year: int, month: int) -> set:
        """Single query for all pending corrections in the month (avoids N+1)."""
        from apps.attendance.models import AttendanceCorrection
        return set(
            AttendanceCorrection.objects
            .filter(
                employee=employee,
                date__year=year, date__month=month,
                status=AttendanceCorrection.STATUS_PENDING,
            )
            .values_list('date', flat=True)
        )

    @staticmethod
    def _leave_dates(employee, month_start: date, month_end: date) -> set:
        """Returns set of dates in [month_start, month_end] that have approved leave."""
        from apps.hrms.models import LeaveRequest, STATUS_APPROVED
        leave_dates: set = set()
        for lr in LeaveRequest.objects.filter(
            employee=employee,
            status=STATUS_APPROVED,
            start_date__lte=month_end,
            end_date__gte=month_start,
        ):
            cur = max(lr.start_date, month_start)
            end = min(lr.end_date, month_end)
            while cur <= end:
                leave_dates.add(cur)
                cur += timedelta(days=1)
        return leave_dates

    @staticmethod
    def _weekly_off_dates(employee, month_start: date, month_end: date) -> set[date]:
        """
        Actual calendar dates (not weekday names) that resolve as weekly-off
        for `employee` across [month_start, month_end] — per-day via the
        centralized resolver, since the employee's assigned pattern can change
        mid-month (that's the whole point of effective-dating). One query for
        the employee's assignment rows regardless of days-in-range.
        """
        from core.cache_service import WeeklyOffCacheService
        resolved = WeeklyOffCacheService.get_effective_range(employee, month_start, month_end)
        return {d for d, off_days in resolved.items() if d.strftime('%A').lower() in off_days}

    @staticmethod
    def _holiday_dates(month_start: date, month_end: date, branch_name: str = '') -> set:
        from core.cache_service import HolidayCacheService
        return HolidayCacheService.get_holiday_dates(month_start, month_end, branch_name)

    @staticmethod
    def _holiday_names(month_start: date, month_end: date, branch_name: str = '') -> dict:
        """Returns {date: holiday name} for the range — lets the calendar show which holiday it is."""
        from core.cache_service import HolidayCacheService
        holidays = HolidayCacheService.get_holidays_with_names(month_start, month_end, branch_name)
        return {h['date']: h['name'] for h in holidays}

    @staticmethod
    def _build_day(
        day_num: int, year: int, month: int,
        records: dict, leave_dates: set, off_dates: set,
        pending_dates: set, today: date,
        holiday_dates: set = None,
        holiday_names: dict = None,
    ) -> dict | None:
        """Builds the response dict for one calendar day; returns None for blank future days."""
        cur           = date(year, month, day_num)
        rec           = records.get(cur)
        holiday_dates = holiday_dates or set()
        holiday_names = holiday_names or {}

        if cur in holiday_dates or (rec and rec.status == AttendanceRecord.STATUS_HOLIDAY):
            key = AttendanceRecord.STATUS_HOLIDAY
        elif cur in off_dates or (rec and rec.status == AttendanceRecord.STATUS_WEEKLY_OFF):
            key = AttendanceRecord.STATUS_WEEKLY_OFF
        elif cur in leave_dates or (rec and rec.status == AttendanceRecord.STATUS_ON_LEAVE):
            key = AttendanceRecord.STATUS_ON_LEAVE
        elif rec:
            key = rec.status
        elif cur > today:
            return None
        else:
            key = AttendanceRecord.STATUS_ABSENT

        reg_required = key == AttendanceRecord.STATUS_INCOMPLETE
        can_reg = (
            key in (
                AttendanceRecord.STATUS_ABSENT, AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_INCOMPLETE,
            )
            and cur not in pending_dates
        )
        label = 'Missing Clock Out' if reg_required else AttendanceRecord.STATUS_DISPLAY_MAP.get(key, key)
        holiday_name = None
        if key == AttendanceRecord.STATUS_HOLIDAY:
            holiday_name = holiday_names.get(cur) or (rec.note if rec and rec.note else 'Holiday')
        return {
            'date':                    cur.strftime('%Y-%m-%d'),
            'status':                  label,
            'color':                   _STATUS_COLOR.get(key, '#94a3b8'),
            'clockIn':                 rec.clock_in_display if rec else None,
            'clockOut':                rec.clock_out_display if rec else None,
            'hours':                   (rec.total_hours_display
                                        if rec and rec.total_working_minutes else None),
            'note':                    rec.note if rec else None,
            'holiday_name':            holiday_name,
            'canRegularize':           can_reg,
            'regularization_required': reg_required,
        }


# ── Audit helper ──────────────────────────────────────────────────────────────

def _write_punch_audit(punch, record, employee, for_date) -> None:
    """Write CLOCK_IN or CLOCK_OUT audit entry after a successful punch."""
    from apps.attendance.models import AttendanceAuditLog
    from apps.attendance.services_audit_log import write_audit_log

    event = (
        AttendanceAuditLog.EVENT_CLOCK_IN
        if punch.punch_type == AttendancePunch.PUNCH_IN
        else AttendanceAuditLog.EVENT_CLOCK_OUT
    )
    direction = 'in' if punch.punch_type == AttendancePunch.PUNCH_IN else 'out'
    write_audit_log(
        employee=employee,
        date=for_date,
        event=event,
        performed_by=employee,
        record=record,
        new_value=punch.punch_time_display,
        action=f'Employee clocked {direction} via {punch.source}',
    )


# ── Utility ────────────────────────────────────────────────────────────────────

def _build_location_label(employee, punch=None) -> str:
    """Builds a display location string from punch + employee profile."""
    parts = []
    branch_name = ''
    if punch and punch.branch:
        branch_name = punch.branch.branch_name
    elif getattr(employee, 'branch', ''):
        branch_name = employee.branch
    if branch_name:
        parts.append(branch_name)

    mode_labels = {
        'web':       'Web',
        'mobile':    'Mobile',
        'biometric': 'Biometric',
        'manual':    'Manual',
        'system':    'System',
    }
    if punch:
        parts.append(mode_labels.get(punch.source, punch.source.title()))
    return ' · '.join(parts) if parts else 'Web'
