from django.db import migrations


def seed_face_verification_rules(apps, schema_editor):
    """
    Backfill AttendanceFaceVerificationRules for every AttendanceSettings row
    that existed before this toggle was added, defaulting to is_mandatory=False
    (unchanged behaviour) so existing organisations aren't silently switched
    to mandatory face ID enforcement.
    """
    AttendanceSettings = apps.get_model('attendance', 'AttendanceSettings')
    AttendanceFaceVerificationRules = apps.get_model('attendance', 'AttendanceFaceVerificationRules')

    for settings in AttendanceSettings.objects.all():
        AttendanceFaceVerificationRules.objects.get_or_create(
            settings=settings,
            defaults={'is_mandatory': False},
        )


def noop_reverse(apps, schema_editor):
    """Nothing to reverse — the rows are removed automatically when the
    CreateModel migration (0025) that owns the table is unapplied."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0025_attendancefaceverificationrules'),
    ]

    operations = [
        migrations.RunPython(seed_face_verification_rules, noop_reverse),
    ]
