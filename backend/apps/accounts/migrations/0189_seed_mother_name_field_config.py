"""
Adds mother_name and languages_known as real, seeded OnboardingFieldConfig
rows for step 0 (Personal), right after father_name — mother_name gets the
same "FROM FAMILY" read-only treatment (synced from the Family &
nomination step's Mother entry) the frontend already gives father_name;
languages_known renders from the same multi-select (LanguagesSelect) the
Hire wizard's own Personal identity step already uses for this field.
Both are real EmployeeProfile columns as of migration 0188 (previously
collected on the Hire wizard's Personal identity step but silently
dropped — no column existed to persist either to).
"""
from django.db import migrations

NEW_FIELDS = [
    # (field_key, label)
    ('mother_name', "Mother's Name"),
    ('languages_known', 'Languages Known'),
]


def seed_forward(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')

    father_name = OnboardingFieldConfig.objects.filter(field_key='father_name', step=0).first()
    insert_after_order = father_name.order if father_name else 3

    to_shift = list(
        OnboardingFieldConfig.objects.filter(step=0, order__gt=insert_after_order).order_by('-order')
    )
    for row in to_shift:
        row.order = row.order + len(NEW_FIELDS)
        row.save(update_fields=['order'])

    for offset, (field_key, label) in enumerate(NEW_FIELDS, start=1):
        OnboardingFieldConfig.objects.get_or_create(
            field_key=field_key,
            defaults={
                'label': label, 'field_type': 'text', 'options': [],
                'step': 0, 'order': insert_after_order + offset, 'visible': True, 'required': False,
                'is_custom': False, 'is_locked': False,
            },
        )

    from core.cache_service import OnboardingFieldConfigCacheService
    OnboardingFieldConfigCacheService.invalidate()


def seed_reverse(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    OnboardingFieldConfig.objects.filter(
        field_key__in=[f[0] for f in NEW_FIELDS], is_custom=False,
    ).delete()
    from core.cache_service import OnboardingFieldConfigCacheService
    OnboardingFieldConfigCacheService.invalidate()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0188_employeeprofile_languages_known_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
