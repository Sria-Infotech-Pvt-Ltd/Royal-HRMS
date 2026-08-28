from django.db import migrations


def backfill_target_org_unit(apps, schema_editor):
    """Match each existing announcement's target_department.name to an
    OrgUnit with the identical name (case-insensitive) — the two are
    already named identically for every department that's been linked via
    the Phase 3 OrgUnit<->Department bridge (see TEAMCONTEXT.md §17). Any
    row whose department has no same-named OrgUnit is left with
    target_org_unit=None rather than guessed at."""
    Announcement = apps.get_model('announcements', 'Announcement')
    OrgUnit = apps.get_model('accounts', 'OrgUnit')

    for ann in Announcement.objects.filter(target_department__isnull=False):
        unit = OrgUnit.objects.filter(name__iexact=ann.target_department.name).first()
        if unit is not None:
            ann.target_org_unit = unit
            ann.save(update_fields=['target_org_unit'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("announcements", "0003_announcement_target_org_unit"),
    ]

    operations = [
        migrations.RunPython(backfill_target_org_unit, noop_reverse),
    ]
