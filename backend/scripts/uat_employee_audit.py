"""Read-only field and lifecycle audit for the synthetic workforce UAT."""
import csv
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
django.setup()

from django.apps import apps
from django.db.models import Count

User = apps.get_model('accounts', 'User')
Profile = apps.get_model('accounts', 'EmployeeProfile')
Placement = apps.get_model('accounts', 'Placement')
Salary = apps.get_model('payroll', 'EmployeeSalaryConfig')
Attendance = apps.get_model('attendance', 'AttendanceRecord')
Punch = apps.get_model('attendance', 'AttendancePunch')
Correction = apps.get_model('attendance', 'AttendanceCorrection')
Balance = apps.get_model('hrms', 'LeaveBalance')
Leave = apps.get_model('hrms', 'LeaveRequest')
Cycle = apps.get_model('payroll', 'PayrollCycle')
Payslip = apps.get_model('payroll', 'EmployeePayslip')
Document = apps.get_model('accounts', 'EmployeeDocument')
WeeklyOff = apps.get_model('attendance', 'EmployeeWeeklyOffAssignment')

suffix = '.wf@example.com'
users = list(User.objects.filter(email__endswith=suffix).order_by('email'))
ids = [u.pk for u in users]
profiles = {p.user_id: p for p in Profile.objects.filter(user_id__in=ids)}

def populated(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True

def row_counts(model, field='employee_id'):
    return dict(model.objects.filter(**{f'{field}__in': ids}).values(field).annotate(n=Count('pk')).values_list(field, 'n'))

placements = row_counts(Placement)
salaries = row_counts(Salary)
attendance = row_counts(Attendance)
punches = row_counts(Punch)
corrections = row_counts(Correction)
balances = row_counts(Balance)
leaves = row_counts(Leave)
docs = row_counts(Document, 'user_id')
weekly = row_counts(WeeklyOff)

cycles = list(Cycle.objects.filter(notes__contains='DEMO-WORKFORCE').order_by('cycle_start', 'branch'))
cycle_ids = [c.pk for c in cycles]
slips = list(Payslip.objects.filter(cycle_id__in=cycle_ids, employee_id__in=ids).select_related('cycle'))
slips_by_user = Counter(s.employee_id for s in slips)
verified_docs = Counter()
document_types = Counter()
for d in Document.objects.filter(user_id__in=ids):
    if d.verification_status == 'verified':
        verified_docs[d.user_id] += 1
    document_types[d.document_type] += 1

required_user = {'email', 'full_name', 'employee_id', 'department', 'designation', 'employee_type', 'branch_fk', 'phone', 'date_of_joining', 'work_location', 'work_mode', 'pay_group', 'attendance_scheme', 'payment_method', 'is_active', 'onboarding_status'}
required_profile = {'salutation', 'display_name', 'nationality', 'date_of_birth', 'gender', 'father_name', 'mother_name', 'languages_known', 'current_address', 'current_district', 'current_state', 'current_pin_code', 'highest_qualification', 'institution', 'year_of_passing', 'account_number', 'ifsc_code', 'bank_name', 'account_holder_name', 'account_type', 'name_as_per_aadhar', 'uan_number', 'pan_number', 'aadhaar_number', 'pf_number', 'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email'}
# Keep the audit's required-field checks aligned with model constraints as
# schema fields are added; the explicit sets above also retain domain-required
# fields that intentionally allow blanks at the model layer.
required_user.update(field.name for field in User._meta.concrete_fields if not field.blank)
required_profile.update(field.name for field in Profile._meta.concrete_fields if not field.blank)
secret_fields = {'password', 'account_number', 'ifsc_code', 'pending_account_number', 'pending_ifsc_code', 'name_as_per_aadhar', 'uan_number', 'esi_number', 'pan_number', 'aadhaar_number', 'pf_number', 'passport_number'}

out = Path(__file__).resolve().parents[2] / 'docs'
out.mkdir(exist_ok=True)
audit_path = out / 'UAT_EMPLOYEE_FIELD_AUDIT_2026-10-23.csv'
lifecycle_path = out / 'UAT_EMPLOYEE_LIFECYCLE_AUDIT_2026-10-23.csv'
fields = ['employee_ref', 'model', 'field', 'result', 'value_check']
with audit_path.open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    lifecycle = []
    field_tally = Counter()
    for i, u in enumerate(users, 1):
        ref = f'UAT-{i:03d}'
        p = profiles.get(u.pk)
        for model_name, obj, required in [('User', u, required_user), ('EmployeeProfile', p, required_profile)]:
            model = User if model_name == 'User' else Profile
            for field in model._meta.concrete_fields:
                name = field.name
                val = getattr(obj, name, None) if obj else None
                # Foreign-key display values are represented by presence, never serialized.
                exists = populated(val)
                if name in ('password', 'profile_photo'):
                    exists = bool(val)
                if exists:
                    result = 'PRESENT'
                elif name in required:
                    result = 'MISSING_REQUIRED'
                else:
                    result = 'BLANK_OPTIONAL'
                check = 'NOT_EXPORTED'
                if result == 'PRESENT':
                    valid = True
                    if getattr(field, 'choices', None):
                        allowed = {choice[0] for choice in field.flatchoices}
                        valid = val in allowed
                    if valid and getattr(field, 'max_length', None) and isinstance(val, str):
                        valid = len(val) <= field.max_length
                    if valid and getattr(field, 'get_internal_type', lambda: '')() == 'EmailField':
                        from django.core.validators import validate_email
                        from django.core.exceptions import ValidationError
                        try:
                            validate_email(str(val))
                        except ValidationError:
                            valid = False
                    if not valid:
                        check = 'field_validation_failed'
                    elif name == 'email':
                        check = 'reserved_example_domain' if u.email.endswith(suffix) else 'FAIL_DOMAIN'
                    elif name == 'pan_number':
                        check = 'format_valid' if re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', str(val).upper()) else 'format_invalid'
                    elif name == 'aadhaar_number':
                        check = '12_digits' if re.fullmatch(r'\d{12}', str(val)) else 'format_invalid'
                    elif name == 'ifsc_code':
                        check = 'IFSC_format_valid' if re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', str(val).upper()) else 'format_invalid'
                    elif name in secret_fields:
                        check = 'encrypted_value_present'
                    else:
                        check = 'value_present'
                w.writerow({'employee_ref': ref, 'model': model_name, 'field': name, 'result': result, 'value_check': check})
                field_tally[(model_name, name, result, check)] += 1
        user_docs = Document.objects.filter(user=u)
        d_count = user_docs.count()
        status = {
            'employee_ref': ref,
            'onboarding_status': u.onboarding_status,
            'employee_type': u.employee_type,
            'branch': u.branch,
            'branch_fk': bool(u.branch_fk_id),
            'profile': p is not None,
            'placement_count': placements.get(u.pk, 0),
            'salary_config_count': salaries.get(u.pk, 0),
            'annual_ctc_positive': bool(Salary.objects.filter(employee_id=u.pk, annual_ctc__gt=0, is_active=True).exists()),
            'attendance_records': attendance.get(u.pk, 0),
            'punches': punches.get(u.pk, 0),
            'corrections': corrections.get(u.pk, 0),
            'leave_balances': balances.get(u.pk, 0),
            'leave_requests': leaves.get(u.pk, 0),
            'documents': d_count,
            'verified_documents': verified_docs.get(u.pk, 0),
            'weekly_off_configured': bool(WeeklyOff.objects.filter(employee_id=u.pk, effective_to__isnull=True).exists()),
            'payslips': slips_by_user.get(u.pk, 0),
        }
        lifecycle.append(status)

summary = {
    'employees': len(users),
    'employee_fields_per_record': len(User._meta.concrete_fields),
    'profile_fields_per_record': len(Profile._meta.concrete_fields),
    'field_audit_rows': len(users) * (len(User._meta.concrete_fields) + len(Profile._meta.concrete_fields)),
    'required_missing': sum(v for (m, n, r, c), v in field_tally.items() if r == 'MISSING_REQUIRED'),
    'optional_blank_field_occurrences': sum(v for (m, n, r, c), v in field_tally.items() if r == 'BLANK_OPTIONAL'),
    'format_invalid': sum(v for (m, n, r, c), v in field_tally.items() if c == 'format_invalid'),
    'field_validation_failures': sum(v for (m, n, r, c), v in field_tally.items() if c == 'field_validation_failed'),
    'unique_employee_ids': User.objects.filter(pk__in=ids).values('employee_id').distinct().count(),
    'employees_by_type': dict(Counter(u.employee_type for u in users)),
    'employees_by_branch': dict(Counter(u.branch for u in users)),
    'onboarding_statuses': dict(Counter(u.onboarding_status for u in users)),
    'attendance_records': sum(attendance.values()),
    'punches': sum(punches.values()),
    'corrections': sum(corrections.values()),
    'leave_balances': sum(balances.values()),
    'leave_requests': sum(leaves.values()),
    'documents': sum(docs.values()),
    'verified_documents': sum(verified_docs.values()),
    'document_types': dict(document_types),
    'documents_with_file_and_size': Document.objects.filter(user_id__in=ids).exclude(file='').filter(file_size__gt=0).count(),
    'attendance_by_status': {str(x['status']): x['n'] for x in Attendance.objects.filter(employee_id__in=ids).values('status').annotate(n=Count('pk'))},
    'leave_requests_by_status': {str(x['status']): x['n'] for x in Leave.objects.filter(employee_id__in=ids).values('status').annotate(n=Count('pk'))},
    'leave_requests_by_type': {str(x['leave_type']): x['n'] for x in Leave.objects.filter(employee_id__in=ids).values('leave_type').annotate(n=Count('pk'))},
    'negative_leave_balances': Balance.objects.filter(employee_id__in=ids, total_days__lt=0).count(),
    'payroll_cycles': [{'id': str(c.pk), 'branch': c.branch, 'start': str(c.cycle_start), 'end': str(c.cycle_end), 'status': c.status} for c in cycles],
    'payslips': len(slips),
    'payslips_by_status': dict(Counter(s.status for s in slips)),
    'positive_net_pays': sum(1 for s in slips if s.net_pay and s.net_pay > 0),
    'payslips_missing_pdf': sum(1 for s in slips if not s.payslip_pdf),
    'lifecycle': lifecycle,
    'field_tally': [{'model': m, 'field': n, 'result': r, 'value_check': c, 'count': v} for (m, n, r, c), v in sorted(field_tally.items())],
}
with lifecycle_path.open('w', newline='', encoding='utf-8-sig') as f:
    lifecycle_fields = list(lifecycle[0]) if lifecycle else []
    writer = csv.DictWriter(f, fieldnames=lifecycle_fields)
    writer.writeheader()
    writer.writerows(lifecycle)
import json
summary_path = out / 'uat_employee_audit_summary.json'
summary_path.write_text(json.dumps(summary, default=str, indent=2), encoding='utf-8')
print(f'SUMMARY={summary_path}')
print(f'FIELD_AUDIT={audit_path}')
print(f'LIFECYCLE_AUDIT={lifecycle_path}')
