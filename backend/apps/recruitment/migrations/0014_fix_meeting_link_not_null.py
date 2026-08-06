from django.db import migrations


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
        migrations.RunSQL(
            sql="ALTER TABLE hrms_candidates ALTER COLUMN meeting_link DROP NOT NULL;",
            reverse_sql="ALTER TABLE hrms_candidates ALTER COLUMN meeting_link SET NOT NULL;",
        ),
    ]
