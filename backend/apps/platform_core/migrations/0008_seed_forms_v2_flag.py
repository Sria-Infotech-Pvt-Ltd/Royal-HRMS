from django.db import migrations


def seed_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('platform_core', 'FeatureFlag')
    FeatureFlag.objects.get_or_create(
        code='forms.v2',
        defaults={
            'description': 'Switches the onboarding wizard onto the new field/form engine (Phase 2 Task J). OFF by default — the legacy OnboardingFieldConfig/OnboardingSection endpoints remain the source of truth until explicitly enabled.',
            'enabled': False,
            'rollout_percentage': 0,
            'is_system': True,
        },
    )


def unseed_flag(apps, schema_editor):
    FeatureFlag = apps.get_model('platform_core', 'FeatureFlag')
    FeatureFlag.objects.filter(code='forms.v2').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('platform_core', '0007_import_job_local_file_storage'),
    ]

    operations = [
        migrations.RunPython(seed_flag, unseed_flag),
    ]
