"""
Late-arrival justification: the medical-proof permission and the email
templates used by its lifecycle (apps/notifications/signals.py,
_on_late_justification_save).

attendance.medical_proof_view lets a reviewer open uploaded medical proof.
It is granted to the HR and System Admin roles only — managers see the
request, reason and status but not the attachment unless an admin grants
them this permission explicitly (Settings → Roles).
"""
from django.db import migrations

PERMISSION = 'attendance.medical_proof_view'

_SIGN = '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'

_TEMPLATES = [
    {
        'name': 'late_justification_submitted',
        'display_name': 'Late Arrival Justification Submitted — Employee Confirmation',
        'description': 'Sent to the employee when their late arrival justification is submitted or resubmitted.',
        'subject': 'Your late arrival justification for {date} has been submitted',
        'body': ('<p>Dear {employee_name},</p>'
                 '<p>Your justification for arriving late on <strong>{date}</strong> has been submitted '
                 'and is awaiting review.</p>'
                 '<p style="color:#888;font-size:13px;">Reason: {reason}</p>' + _SIGN),
        'available_variables': ['employee_name', 'date', 'reason', 'company_name'],
    },
    {
        'name': 'late_justification_pending_approval',
        'display_name': 'Late Arrival Justification — Awaiting Your Review',
        'description': 'Sent to the reviewer at the current approval stage.',
        'subject': 'Late arrival justification awaiting your review — {employee_name}',
        'body': ('<p>Dear {approver_name},</p>'
                 '<p><strong>{employee_name}</strong> has explained a late arrival on <strong>{date}</strong>.</p>'
                 '<p style="color:#888;font-size:13px;">Reason: {reason}</p>'
                 '<p>Please review it in Royal HRMS. Attachments are available there to authorised reviewers '
                 'only.</p>' + _SIGN),
        'available_variables': ['approver_name', 'employee_name', 'date', 'reason', 'company_name'],
    },
    {
        'name': 'late_justification_approved',
        'display_name': 'Late Arrival Excused',
        'description': 'Sent to the employee when their late arrival justification is fully approved.',
        'subject': 'Your late arrival on {date} has been excused',
        'body': ('<p>Dear {employee_name},</p>'
                 '<p>Your late arrival on <strong>{date}</strong> has been '
                 '<strong style="color:#1b8a6b;">excused</strong>. It is shown as Late (Excused) and does not '
                 'count towards late-mark deductions.</p>' + _SIGN),
        'available_variables': ['employee_name', 'date', 'company_name'],
    },
    {
        'name': 'late_justification_rejected',
        'display_name': 'Late Arrival Justification Rejected',
        'description': 'Sent to the employee when their late arrival justification is rejected.',
        'subject': 'Your late arrival justification for {date} was rejected',
        'body': ('<p>Dear {employee_name},</p>'
                 '<p>Your justification for arriving late on <strong>{date}</strong> was '
                 '<strong style="color:#b91c1c;">rejected</strong>.</p>'
                 '<p>Reason: {remarks}</p>' + _SIGN),
        'available_variables': ['employee_name', 'date', 'remarks', 'company_name'],
    },
    {
        'name': 'late_justification_resubmission_required',
        'display_name': 'Late Arrival Justification — Resubmission Required',
        'description': 'Sent to the employee when a reviewer asks them to resubmit.',
        'subject': 'Please resubmit your late arrival justification for {date}',
        'body': ('<p>Dear {employee_name},</p>'
                 '<p>Your justification for arriving late on <strong>{date}</strong> needs to be resubmitted.</p>'
                 '<p>Reviewer\'s note: {remarks}</p>'
                 '<p>Open My Attendance → Corrections to update it within 3 days.</p>' + _SIGN),
        'available_variables': ['employee_name', 'date', 'remarks', 'company_name'],
    },
]


def seed(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')

    perm, _ = Permission.objects.get_or_create(
        codename=PERMISSION, defaults={'module': 'attendance', 'action': 'medical_proof_view'})
    for role in Role.objects.filter(name__in=('hr', 'system_admin')):
        RolePermission.objects.get_or_create(role=role, permission=perm)

    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(name=tpl['name'], defaults={
            **{k: v for k, v in tpl.items() if k != 'name'},
            'template_type': 'hrms', 'is_active': True, 'is_builtin': True,
        })


def unseed(apps, schema_editor):
    apps.get_model('accounts', 'Permission').objects.filter(codename=PERMISSION).delete()
    apps.get_model('accounts', 'EmailTemplate').objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0049_late_arrival_justification'),
        ('accounts', '0103_employeecodesettings_id_format'),
    ]

    operations = [migrations.RunPython(seed, unseed)]
