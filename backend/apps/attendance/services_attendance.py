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

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import (
    AttendanceAbsenceAlert,
    AttendancePunch,
    AttendanceRecord,
    AttendanceSettings,
    AttendanceWorkingHours,
    AttendanceWeeklyOff,
    AttendancePunchRules,
    AttendanceOvertimeRules,
)

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_settings() -> Optional[AttendanceSettings]:
    return (
        AttendanceSettings.objects
        .select_related(
            'working_hours', 'weekly_off',
            'punch_rules', 'overtime_rules',
        )
        .filter(is_active=True)
        .order_by('-created_at')
        .first()
    )


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
          source          — 'web' | 'mobile' | 'biometric' | 'manual'
          attendance_mode — 'office' | 'wfh' | 'field' | ...
          latitude        — float or None
          longitude       — float or None
          accuracy        — float or None
          device_time     — datetime or None
          device_name     — str
          device_id       — str
          browser         — str
          operating_system— str
          ip_address      — str or None  (injected by the view from request)

        Raises ValueError with a user-facing message on validation failure.
        Raises PermissionError with a user-facing message on geofence failure.
        """
        from apps.attendance.services_geofencing import GeofencingService

        now        = timezone.now()
        punch_type = punch_data['punch_type']
        mode       = punch_data.get('attendance_mode', AttendancePunch.MODE_OFFICE)

        # ── Consecutive punch validation ──────────────────────────────────────
        if punch_type == AttendancePunch.PUNCH_IN and cls._is_clocked_in(employee, now.date()):
            raise ValueError(
                'You are already clocked in. Please clock out before clocking in again.'
            )
        if punch_type == AttendancePunch.PUNCH_OUT and not cls._is_clocked_in(employee, now.date()):
            raise ValueError(
                'You are not currently clocked in. Please clock in first.'
            )

        # ── Geofence validation ───────────────────────────────────────────────
        geo = GeofencingService.validate(
            employee=employee,
            attendance_mode=mode,
            employee_lat=punch_data.get('latitude'),
            employee_lon=punch_data.get('longitude'),
        )
        if not geo.is_allowed:
            raise PermissionError(geo.rejection_message)

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
            )

        AttendanceProcessorService.process_day(employee, now.date())
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
        today = now.date()

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
        cfg = _get_settings()
        punches = list(
            AttendancePunch.objects
            .filter(employee=employee, punched_at__date=for_date)
            .order_by('punched_at')
        )

        record_data = cls._calculate(punches, for_date, cfg)

        record, _ = AttendanceRecord.objects.update_or_create(
            employee=employee,
            date=for_date,
            defaults=record_data,
        )
        return record

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
        is_late      = cls._check_late(first_in.time(), cfg)
        is_early_exit = cls._check_early_exit(last_out.time() if last_out else None, cfg)
        status       = cls._resolve_status(net_minutes, is_late, cfg)

        # Overtime
        ot_minutes = cls._calc_overtime(net_minutes, cfg)

        note = ''
        if is_late:
            grace = cfg.working_hours.grace_period_minutes if cfg and hasattr(cfg, 'working_hours') else 0
            note = f'Grace exceeded' if grace else 'Late arrival'

        return {
            'status':                status,
            'first_punch_in':        first_in.time(),
            'last_punch_out':        last_out.time() if last_out else None,
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
    def _resolve_status(net_minutes: int, is_late: bool, cfg) -> str:
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
        return AttendanceRecord.STATUS_ABSENT

    @staticmethod
    def _calc_overtime(net_minutes: int, cfg) -> int:
        if not cfg or not hasattr(cfg, 'overtime_rules'):
            return 0
        threshold = int(float(cfg.overtime_rules.ot_threshold_hours) * 60)
        return max(0, net_minutes - threshold)


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
        records = cls._month_records(employee, year, month)
        working_records = [
            r for r in records
            if r.status not in (
                AttendanceRecord.STATUS_WEEKLY_OFF,
                AttendanceRecord.STATUS_HOLIDAY,
            )
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
            1 for r in records if r.is_late
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
        import calendar as cal_module
        records = cls._month_records(employee, year, month)

        working_days = sum(1 for r in records if r.status not in (
            AttendanceRecord.STATUS_WEEKLY_OFF, AttendanceRecord.STATUS_HOLIDAY,
        ))
        days_present = sum(1 for r in records if r.status in (
            AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE,
        ))
        days_absent  = sum(1 for r in records if r.status == AttendanceRecord.STATUS_ABSENT)
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
        Returns per-day data keyed by day number (int).
        Shape matches CalendarGrid's Record<number, DayRecord>.
        """
        records = cls._month_records(employee, year, month)
        days: dict[int, dict] = {}

        for r in records:
            day_num = r.date.day
            can_regularize = r.status in (
                AttendanceRecord.STATUS_ABSENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_HALF_DAY,
            ) and not cls._has_pending_correction(employee, r.date)

            days[day_num] = {
                'status':        r.status_display,
                'clockIn':       r.clock_in_display,
                'clockOut':      r.clock_out_display,
                'hours':         r.total_hours_display if r.total_working_minutes else None,
                'note':          r.note or None,
                'canRegularize': can_regularize,
            }

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
