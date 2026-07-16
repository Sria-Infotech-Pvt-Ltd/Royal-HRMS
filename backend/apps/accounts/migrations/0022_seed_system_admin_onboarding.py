from django.db import migrations


def seed_onboarding_status(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    # system_admin role and django superusers bypass onboarding
    User.objects.filter(role__name='system_admin').update(onboarding_status='complete')
    User.objects.filter(is_superuser=True).update(onboarding_status='complete')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0021_onboarding_models'),
    ]

    operations = [
        migrations.RunPython(seed_onboarding_status, migrations.RunPython.noop),
    ]
