from django.db import migrations


class Migration(migrations.Migration):
    """Repairs environments where hrms_employee_code_series is missing the
    prefix/padding columns — django_migrations recorded 0154 as applied, but
    the table it actually created predates 0154's current (prefix/padding)
    field definitions on at least one environment. Idempotent raw SQL so
    it's a no-op on databases where 0154 already produced the right columns.
    Leaves any pre-existing range_start/range_end columns untouched — they
    are unused by current code but dropping them is not required for the fix."""

    dependencies = [
        ("accounts", "0211_backfill_account_activated_at"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE hrms_employee_code_series
                    ADD COLUMN IF NOT EXISTS prefix varchar(10) NOT NULL DEFAULT 'EMP';
                ALTER TABLE hrms_employee_code_series
                    ADD COLUMN IF NOT EXISTS padding smallint NOT NULL DEFAULT 5;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
