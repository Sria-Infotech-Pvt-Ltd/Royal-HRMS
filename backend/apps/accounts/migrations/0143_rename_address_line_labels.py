# Relabels current_address/permanent_address from "Current Address"/
# "Permanent Address" to "Address Line 1" — each already sits right above
# its own Village/District/State/PIN Code fields (0129/0130), so "Current"/
# "Permanent" is now conveyed by the section heading DynamicStepFields
# renders above each run instead of by the field's own label, and "Address
# Line 1" describes what the field actually holds (just the house/street
# line, per 0129's own comment) more accurately than a bare "Address" ever
# did.
from django.db import migrations


def relabel(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    OnboardingFieldConfig.objects.filter(
        field_key__in=['current_address', 'permanent_address'],
    ).update(label='Address Line 1')

    try:
        from core.cache_service import OnboardingFieldConfigCacheService
        OnboardingFieldConfigCacheService.invalidate()
    except Exception:
        pass


def revert(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    OnboardingFieldConfig.objects.filter(field_key='current_address').update(label='Current Address')
    OnboardingFieldConfig.objects.filter(field_key='permanent_address').update(label='Permanent Address')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0142_alter_educationrecord_options_and_more'),
    ]

    operations = [
        migrations.RunPython(relabel, revert),
    ]
