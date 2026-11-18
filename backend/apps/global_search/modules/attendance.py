"""Attendance records: a person's own days, plus the employees they may see when they hold attendance.view."""
from apps.attendance.models import AttendanceRecord
from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register
from apps.global_search.scope import own_or_in_scope

from ._helpers import choices_of, label_of, short_date


def _queryset(user):
    return AttendanceRecord.objects.filter(own_or_in_scope(user, 'employee', permission='attendance.view')).select_related('employee')


def _describe(record: AttendanceRecord) -> dict:
    return {
        'id': str(record.pk),
        'title': record.employee.full_name,
        'subtitle': ' · '.join(part for part in (short_date(record.date), label_of(record, 'status')) if part),
        'meta': {
            'Employee ID': record.employee.employee_id,
            'In': record.first_punch_in.strftime('%H:%M') if record.first_punch_in else '',
            'Out': record.last_punch_out.strftime('%H:%M') if record.last_punch_out else '',
            'Mode': label_of(record, 'work_mode'),
        },
        'url': '/dashboard/attendance',
    }


ATTENDANCE = register(SearchModule(
    key='attendance', label='Attendance', icon='ti-clock', permission=None, queryset=_queryset,
    fields=(
        FieldSpec('employee_name', 'Employee', f.TEXT, 'employee__full_name', searchable=True),
        FieldSpec('employee_id', 'Employee ID', f.TEXT, 'employee__employee_id', searchable=True),
        FieldSpec('branch', 'Company code', f.TEXT, 'employee__branch'),
        FieldSpec('department', 'Department', f.TEXT, 'employee__department'),
        FieldSpec('date', 'Date', f.DATE, 'date'),
        FieldSpec('status', 'Status', f.CHOICE, 'status', choices=choices_of(AttendanceRecord, 'status')),
        FieldSpec('work_mode', 'Work mode', f.CHOICE, 'work_mode', choices=choices_of(AttendanceRecord, 'work_mode')),
        FieldSpec('first_punch_in', 'Punch in', f.TIME, 'first_punch_in'),
        FieldSpec('last_punch_out', 'Punch out', f.TIME, 'last_punch_out'),
        FieldSpec('total_working_minutes', 'Working minutes', f.NUMBER, 'total_working_minutes'),
        FieldSpec('overtime_minutes', 'Overtime minutes', f.NUMBER, 'overtime_minutes'),
        FieldSpec('is_late', 'Late', f.BOOLEAN, 'is_late'),
        FieldSpec('is_early_exit', 'Early exit', f.BOOLEAN, 'is_early_exit'),
    ),
    describe=_describe, order_by=('-date', 'employee__full_name', '-pk'), default_url='/dashboard/attendance',
))
