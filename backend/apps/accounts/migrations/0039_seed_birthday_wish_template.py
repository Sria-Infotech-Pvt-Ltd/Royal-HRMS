"""Seed the birthday_wish email template sent to employees on their birthday."""
from django.db import migrations

TEMPLATE = {
    'name':         'birthday_wish',
    'display_name': 'Birthday Wish',
    'description':  'Sent automatically to an employee on their birthday at 9 AM.',
    'template_type': 'hrms',
    'subject':      'Happy Birthday, {employee_name}! 🎂',
    'body': (
        '<p>Dear {employee_name},</p>'
        '<p>On behalf of everyone at <strong>{company_name}</strong>, '
        'we wish you a very <strong>Happy Birthday!</strong> 🎉</p>'
        '<p>May this special day bring you joy, good health, and all the happiness '
        'you deserve. Your dedication and hard work make our team stronger every day, '
        'and we are grateful to have you with us.</p>'
        '<p>Here\'s to another wonderful year ahead!</p>'
        '<p style="margin-top:24px;">Warm regards,<br/>'
        '<strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': ['employee_name', 'company_name'],
}


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.update_or_create(
        name=TEMPLATE['name'],
        defaults={k: v for k, v in TEMPLATE.items() if k != 'name'},
    )


def remove_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name=TEMPLATE['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0038_employeeprofile_birthday_wish_sent_year'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
