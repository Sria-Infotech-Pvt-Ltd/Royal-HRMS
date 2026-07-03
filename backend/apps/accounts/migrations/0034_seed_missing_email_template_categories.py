"""
Seed the two missing email template categories:
  - recruitment  (order 5)
  - onboarding   (order 6)

These categories already have templates assigned (portal_invite, rejection,
selection, welcome_employee, onboarding_approved, onboarding_rejected) but
the category rows were never created, so they showed as orphaned.
"""
from django.db import migrations

MISSING_CATEGORIES = [
    {'name': 'recruitment', 'display_name': 'Recruitment',  'is_builtin': True, 'order': 5},
    {'name': 'onboarding',  'display_name': 'Onboarding',   'is_builtin': True, 'order': 6},
]


def seed_categories(apps, schema_editor):
    EmailTemplateCategory = apps.get_model('accounts', 'EmailTemplateCategory')
    for cat in MISSING_CATEGORIES:
        EmailTemplateCategory.objects.get_or_create(
            name=cat['name'],
            defaults={
                'display_name': cat['display_name'],
                'is_builtin':   cat['is_builtin'],
                'order':        cat['order'],
            },
        )


def remove_categories(apps, schema_editor):
    EmailTemplateCategory = apps.get_model('accounts', 'EmailTemplateCategory')
    EmailTemplateCategory.objects.filter(
        name__in=[c['name'] for c in MISSING_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0033_portal_invite_assessment_mention'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
