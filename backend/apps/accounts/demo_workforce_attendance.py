"""
Backdated attendance for the `seed_demo_workforce` command. Builds, per employee and per day, the same rows the
attendance processor leaves behind (AttendanceRecord + the raw AttendancePunch pair), with a believable mix of
on-time days, late marks, half days, work-from-home, approved leave, unexplained absences and punch corrections.

Deterministic: each employee's days come from a random generator seeded with their employee code, so re-running
gives the same history. Rows are written with bulk_create, which skips model signals — nothing is emailed or
notified. Days an employee already has a record for are never touched.
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from apps.attendance.models import (
    DAY_TYPE_OFF, AttendanceCorrection, AttendancePunch, AttendanceRecord,
)
from apps.hrms.models import (
    APPROVAL_APPROVED, DURATION_FULL, REQ_APPROVED, LeaveBalance, LeaveRequest,
)

IST = ZoneInfo('Asia/Kolkata')
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
BREAK_MINUTES = 60
FULL_DAY_MINUTES = 540
# (leave type, min days, max days) — one spell of each is tried per employee, if their balance allows it.
LEAVE_SPELLS = [('casual', 1, 1), ('sick', 1, 2), ('earned', 2, 3)]


def weekly_off_weekdays(policy) -> set:
    """Monday=0 … Sunday=6 for every day the policy marks as a full day off."""
    return {index for index, name in enumerate(WEEKDAYS) if getattr(policy, name) == DAY_TYPE_OFF}


def _at(day: date, minute_of_day: int) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=IST) + timedelta(minutes=minute_of_day)


def _plan_leave(rng, working_days, balances) -> dict:
    """date → leave type for each spell (consecutive working days) that fits the balance left."""
    plan = {}
    for leave_type, low, high in LEAVE_SPELLS:
        days = rng.randint(low, high)
        left = balances.get(leave_type, Decimal(0))
        if len(working_days) < 30 or left < days:
            continue
        start = rng.randint(5, len(working_days) - days - 3)
        spell = working_days[start:start + days]
        if any(day in plan for day in spell):
            continue
        plan.update({day: leave_type for day in spell})
        balances[leave_type] = left - days
    return plan


def _punches(day, in_minute, out_minute, mode, regularized_out=False):
    return [(AttendancePunch.PUNCH_IN, _at(day, in_minute), mode, False),
            (AttendancePunch.PUNCH_OUT, _at(day, out_minute), mode, regularized_out)]


def _day_row(rng, day, kind):
    """(record fields, punch tuples) for one working day of the given kind."""
    wfh = kind in ('present', 'late') and rng.random() < 0.12
    mode = AttendanceRecord.WORK_MODE_WFH if wfh else AttendanceRecord.WORK_MODE_OFFICE
    if kind == 'absent':
        return dict(status='absent', note='Absent without intimation'), []
    if kind == 'half_day':
        in_m, out_m, status = rng.randint(555, 575), rng.randint(800, 830), 'half_day'
    elif kind == 'late':
        in_m, out_m, status = rng.randint(605, 650), rng.randint(1100, 1160), 'late'
    else:
        in_m, out_m, status = rng.randint(530, 565), rng.randint(1080, 1150), 'present'
    net = out_m - in_m - (0 if kind == 'half_day' else BREAK_MINUTES)
    fields = dict(
        status=status, work_mode=mode, first_punch_in=_at(day, in_m).timetz().replace(tzinfo=None),
        last_punch_out=_at(day, out_m).timetz().replace(tzinfo=None), total_working_minutes=net,
        overtime_minutes=max(0, net - FULL_DAY_MINUTES), is_late=kind == 'late', is_early_exit=kind == 'half_day',
    )
    return fields, _punches(day, in_m, out_m, 'wfh' if wfh else 'office')


def _pick_special_days(rng, working_days, leave_plan, last_week):
    free = [d for d in working_days if d not in leave_plan and d not in last_week]
    picks = rng.sample(free, min(len(free), 5)) if free else []
    kinds = ['absent'] * 2 + ['half_day'] * 2 + ['regularised']
    special = dict(zip(picks, kinds))
    if last_week:
        special[rng.choice(last_week)] = 'incomplete'  # forgot to punch out recently → a pending regularisation
    return special


def _correction(employee, day, kind, l1_user, l2_user, rng):
    approved = kind == 'regularised'
    now = datetime.now(tz=IST)
    return AttendanceCorrection(
        employee=employee, date=day, punch_type=AttendanceCorrection.PUNCH_OUT,
        requested_out_time=time(18, rng.choice([0, 15, 30, 45])),
        reason=AttendanceCorrection.REASON_FORGOT, notes='Forgot to punch out before leaving.',
        status=AttendanceCorrection.STATUS_APPROVED if approved else AttendanceCorrection.STATUS_PENDING,
        reviewed_by=l2_user if approved else None, reviewed_at=now if approved else None,
        l1_approver=l1_user if approved else None, l1_status='approved' if approved else None,
        l1_actioned_at=now if approved else None, l2_approver=l2_user if approved else None,
        l2_status='approved' if approved else None, l2_actioned_at=now if approved else None, created_by=employee,
    )


def _working_day_rows(employee, branch, day, kind, rng, l1_user, l2_user):
    """(record, punches, correction) for one working day that is not leave."""
    fields, rows = _day_row(rng, day, 'present' if kind in ('regularised', 'incomplete') else kind)
    correction = None
    if kind == 'incomplete':
        fields.update(status='incomplete', last_punch_out=None, total_working_minutes=0, overtime_minutes=0)
        rows = rows[:1]
    if kind in ('regularised', 'incomplete'):
        correction = _correction(employee, day, kind, l1_user, l2_user, rng)
    if kind == 'regularised':
        fields['note'] = 'Regularised — forgot to punch out'
        rows = rows[:1] + [(AttendancePunch.PUNCH_OUT, rows[1][1], rows[1][2], True)]
    punches = [AttendancePunch(employee=employee, branch=branch, punch_type=t, punched_at=at, device_time=at,
                               source='web', attendance_mode=mode, is_regularized=reg) for t, at, mode, reg in rows]
    return AttendanceRecord(employee=employee, date=day, **fields), punches, correction


def _build_rows(employee, branch, days, off_weekdays, holidays, leave_plan, special, rng, l2_user):
    records, punches, corrections = [], [], []
    for day in days:
        if day.weekday() in off_weekdays:
            records.append(AttendanceRecord(employee=employee, date=day, status='weekly_off'))
        elif day in holidays:
            records.append(AttendanceRecord(employee=employee, date=day, status='holiday', note=holidays[day]))
        elif day in leave_plan:
            records.append(AttendanceRecord(employee=employee, date=day, status='on_leave',
                                            note=f'{leave_plan[day].title()} leave'))
        else:
            kind = special.get(day) or ('late' if rng.random() < 0.07 else 'present')
            record, rows, correction = _working_day_rows(employee, branch, day, kind, rng, employee.reporting_manager, l2_user)
            records.append(record)
            punches += rows
            if correction is not None:
                corrections.append(correction)
    return records, punches, corrections


def generate_for_employee(employee, branch, start, end, off_weekdays, holidays, l2_user) -> dict:
    """Write attendance for one employee between start and end (inclusive). Returns row counts."""
    rng = random.Random(employee.employee_id)
    first = max(start, employee.date_of_joining or start)
    done = set(AttendanceRecord.objects.filter(employee=employee, date__range=(first, end)).values_list('date', flat=True))
    days = [d for d in (first + timedelta(days=i) for i in range((end - first).days + 1)) if d not in done]
    working = [d for d in days if d.weekday() not in off_weekdays and d not in holidays]
    balances = {b.leave_type: b.total_days + b.carried_forward - b.used_days
                for b in LeaveBalance.objects.filter(employee=employee, year=end.year)}
    leave_plan = _plan_leave(rng, working, balances)
    special = _pick_special_days(rng, working, leave_plan, [d for d in working if (end - d).days < 7])
    records, punches, corrections = _build_rows(
        employee, branch, days, off_weekdays, holidays, leave_plan, special, rng, l2_user)
    leave_requests = _leave_requests(employee, leave_plan, l2_user)
    AttendanceRecord.objects.bulk_create(records, ignore_conflicts=True)
    AttendancePunch.objects.bulk_create(punches)
    AttendanceCorrection.objects.bulk_create(corrections)
    LeaveRequest.objects.bulk_create(leave_requests)
    _consume_balances(employee, leave_plan, end.year)
    return {'records': len(records), 'punches': len(punches), 'corrections': len(corrections), 'leaves': len(leave_requests)}


def _leave_requests(employee, leave_plan, l2_user):
    """One approved request per consecutive run of the same leave type."""
    requests, run = [], []
    for day in sorted(leave_plan):
        if run and (leave_plan[day] != leave_plan[run[-1]] or (day - run[-1]).days > 4):
            requests.append(run)
            run = []
        run.append(day)
    if run:
        requests.append(run)
    return [LeaveRequest(
        employee=employee, leave_type=leave_plan[days[0]], duration=DURATION_FULL, start_date=days[0], end_date=days[-1],
        total_days=Decimal(len(days)), reason='Personal work' if leave_plan[days[0]] != 'sick' else 'Not feeling well',
        status=REQ_APPROVED, l1_approver=employee.reporting_manager, l1_status=APPROVAL_APPROVED,
        l1_remarks='Approved', l2_approver=l2_user, l2_status=APPROVAL_APPROVED,
    ) for days in requests]


def _consume_balances(employee, leave_plan, year):
    for leave_type in set(leave_plan.values()):
        taken = Decimal(sum(1 for t in leave_plan.values() if t == leave_type))
        balance = LeaveBalance.objects.filter(employee=employee, leave_type=leave_type, year=year).first()
        if balance is not None:
            LeaveBalance.objects.filter(pk=balance.pk).update(used_days=balance.used_days + taken)
