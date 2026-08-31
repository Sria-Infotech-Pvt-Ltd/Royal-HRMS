"""
Seed the email templates used by Face ID registration review
(FaceRegistrationReviewView.patch). This event previously had no
notification at all — no in-app Notification, no email — leaving an
employee whose Face ID was rejected with no way to find out except
asking HR directly. See apps/attendance/views/face_registration.py.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'face_registration_approved',
        'display_name': 'Face ID Registration Approved',
        'description':  'Sent to the employee when their Face ID registration is approved.',
        'template_type': 'hrms',
        'subject':      'Your Face ID registration has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your Face ID registration has been <strong style="color:#1b8a6b;">approved</strong>. '
            'You can now use it to clock in and out.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'company_name'],
    },
    {
        'name':         'face_registration_rejected',
        'display_name': 'Face ID Registration Rejected',
        'description':  'Sent to the employee when their Face ID registration is rejected.',
        'template_type': 'hrms',
        'subject':      'Your Face ID registration was not approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your Face ID registration was <strong style="color:#b91c1c;">not approved</strong>.</p>'
            '<p style="color:#888;font-size:13px;">Details: {notes}</p>'
            '<p>Please try registering again, or contact your HR representative if you need help.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'notes', 'company_name'],
    },
]


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(
            name=tpl['name'],
            defaults={k: v for k, v in tpl.items() if k != 'name'},
        )


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0041_seed_regularization_email_templates'),
        ('accounts',   '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
