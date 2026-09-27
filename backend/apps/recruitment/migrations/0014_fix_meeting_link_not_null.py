from django.db import migrations


def drop_not_null(apps, schema_editor):
    # Postgres-only drift fix (see module docstring) — a fresh SQLite
    # install never has this stray column, so there's nothing to fix.
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE hrms_candidates ALTER COLUMN meeting_link DROP NOT NULL;")


def set_not_null(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE hrms_candidates ALTER COLUMN meeting_link SET NOT NULL;")


class Migration(migrations.Migration):
    """
    hrms_candidates.meeting_link is a stray column with no corresponding
    Candidate model field (added outside Django's migration history and
    never wired up). Its NOT NULL constraint with no default rejects every
    Candidate insert (referrals, direct creation, bulk import). Dropping the
    constraint is state-less on purpose — the model still has no field for
    this column.
    """

    dependencies = [
        ('recruitment', '0013_interview_email_templates_with_location'),
    ]

    operations = [
        migrations.RunPython(drop_not_null, set_not_null),
    ]
