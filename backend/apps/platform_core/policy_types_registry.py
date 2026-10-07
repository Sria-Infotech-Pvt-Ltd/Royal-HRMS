"""
Phase 3A Task D.1 — policy types are registered in code (each needs code
that actually consumes it) and synced to the database by
`sync_policy_types` (idempotent get_or_create by code, same convention
as Task A's sync_entity_registry).

Task F.1 — the 7 attendance policy types below cover every field of
BOTH existing attendance configuration systems (AttendanceSettings'
one-to-one tables, and the named WorkingHoursPolicy/WeeklyDayPolicy/
PunchRulesPolicy/OvertimePolicy/LateMarkLOPPolicy/AbsenceAlertPolicy
models — AttendanceFaceVerificationRules/geofence constants are also
covered). Registering the TYPE here is NOT the same as migrating real
data into it — see PHASE3A_REPORT.md's Task F section for why the
actual System1/System2 data migration, the get_attendance_policy()
call-site rewiring, and the "identical resolution" verification report
are explicitly deferred to their own pass, same discipline as the
Company->LegalEntity cutover in Phase 1.
"""
from __future__ import annotations

ATTENDANCE_WORKING_HOURS = {
    'code': 'ATT_WORKING_HOURS', 'name': 'Working hours', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {
            'start_time': {'type': 'string', 'format': 'time'},
            'end_time': {'type': 'string', 'format': 'time'},
            'break_minutes': {'type': 'integer', 'minimum': 0},
            'grace_minutes': {'type': 'integer', 'minimum': 0},
            'min_working_hours': {'type': 'number'},
            'max_working_hours': {'type': 'number'},
        },
        'required': ['start_time', 'end_time'],
    },
}

ATTENDANCE_WEEKLY_OFF = {
    'code': 'ATT_WEEKLY_OFF', 'name': 'Weekly off', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {day: {'type': 'string', 'enum': ['working', 'off', 'half_day']} for day in
                       ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']},
    },
}

ATTENDANCE_PUNCH_RULES = {
    'code': 'ATT_PUNCH_RULES', 'name': 'Punch rules', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {
            'punch_mode': {'type': 'string'}, 'max_punches_per_day': {'type': 'integer'},
            'auto_checkout_enabled': {'type': 'boolean'}, 'auto_checkout_time': {'type': 'string'},
            'early_checkout_grace_minutes': {'type': 'integer'},
            'missing_punch_action': {'type': 'string'},
        },
    },
}

ATTENDANCE_OVERTIME = {
    'code': 'ATT_OVERTIME', 'name': 'Overtime', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {
            'minimum_minutes': {'type': 'integer'}, 'per_day_cap_minutes': {'type': 'integer'},
            'per_month_cap_minutes': {'type': 'integer'}, 'round_off_minutes': {'type': 'integer'},
            'approval_type': {'type': 'string'},
            'holiday_multiplier': {'type': 'number'}, 'weekly_off_multiplier': {'type': 'number'},
        },
    },
}

ATTENDANCE_LATE_MARK = {
    'code': 'ATT_LATE_MARK', 'name': 'Late mark / LOP', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {'late_marks_per_lop': {'type': 'integer'}, 'deduction_unit': {'type': 'string'}},
    },
}

ATTENDANCE_ABSENCE_ALERT = {
    'code': 'ATT_ABSENCE_ALERT', 'name': 'Absence alert', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {
            'enabled': {'type': 'boolean'}, 'threshold_days': {'type': 'integer'},
            'recipients': {'type': 'array', 'items': {'type': 'string'}},
        },
    },
}

ATTENDANCE_FACE_VERIFICATION = {
    'code': 'ATT_FACE_VERIFICATION', 'name': 'Face verification', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {'match_threshold': {'type': 'number'}, 'required_for_punch_types': {'type': 'array', 'items': {'type': 'string'}}},
    },
}

ATTENDANCE_GEOFENCE = {
    'code': 'ATT_GEOFENCE', 'name': 'Geofence', 'module': 'attendance',
    'parameter_schema': {
        'type': 'object',
        'properties': {'radius_meters': {'type': 'integer'}, 'enforced': {'type': 'boolean'}},
    },
}

# Task G.2 — read-only, exposes LeavePolicy.applicable_* through the
# explainer; LeavePlanPolicyAdapter.legacy_resolve is the only path ever
# actually exercised in this phase (leave behavior itself is Phase 6).
LEAVE_PLAN = {
    'code': 'LEAVE_PLAN', 'name': 'Leave plan (read-only explainer)', 'module': 'hrms',
    'parameter_schema': {
        'type': 'object',
        'properties': {'applicable_policies': {'type': 'array'}},
    },
}

ALL_POLICY_TYPES = [
    ATTENDANCE_WORKING_HOURS, ATTENDANCE_WEEKLY_OFF, ATTENDANCE_PUNCH_RULES, ATTENDANCE_OVERTIME,
    ATTENDANCE_LATE_MARK, ATTENDANCE_ABSENCE_ALERT, ATTENDANCE_FACE_VERIFICATION, ATTENDANCE_GEOFENCE,
    LEAVE_PLAN,
]


def sync() -> dict:
    from apps.platform_core.models import PolicyType
    created = updated = unchanged = 0
    for spec in ALL_POLICY_TYPES:
        obj, was_created = PolicyType.objects.get_or_create(
            code=spec['code'],
            defaults={'name': spec['name'], 'module': spec['module'], 'parameter_schema': spec['parameter_schema'], 'is_system': True},
        )
        if was_created:
            created += 1
            continue
        changed = []
        if obj.parameter_schema != spec['parameter_schema']:
            obj.parameter_schema = spec['parameter_schema']
            changed.append('parameter_schema')
        if changed:
            obj.save(update_fields=changed)
            updated += 1
        else:
            unchanged += 1
    return {'created': created, 'updated': updated, 'unchanged': unchanged}
