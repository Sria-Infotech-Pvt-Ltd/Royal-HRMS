from django.db import migrations


class Migration(migrations.Migration):
    """Drops the obsolete prefix/padding columns from hrms_employee_code_series.

    0212_employee_id_ranges removed these two fields from the EmployeeCodeSeries
    model (employee IDs are now purely numeric ranges, no alphabetic prefix).
    But 0212_repair_employee_code_series_columns, brought in from the
    05-nov-2026 branch, re-adds the columns at the database level
    (ADD COLUMN IF NOT EXISTS) and, on a fresh database, runs AFTER
    0212_employee_id_ranges, leaving two dead NOT NULL columns that the model
    does not know about. This migration runs after both chains have been
    merged (0220) and removes them, so every database ends up matching the model.

    Idempotent: DROP COLUMN IF EXISTS is a no-op where the columns are already
    gone (e.g. a database that never re-added them).

    Forward effect: any values stored in prefix/padding are discarded. No code
    reads them; the only values they can hold are the old defaults ('EMP', 5)
    or the pre-0212 prefix/padding settings, which 0212/0213 already retired.

    Reverse is deliberately a no-op: the columns are NOT restored. Nothing uses
    them, and restoring them here would make a later reversal of
    0212_employee_id_ranges (whose own reverse re-adds prefix/padding) fail
    with "column already exists"."""

    dependencies = [
        ('accounts', '0220_merge_password_reset_link_and_signed_offer_letter'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE hrms_employee_code_series
                    DROP COLUMN IF EXISTS prefix,
                    DROP COLUMN IF EXISTS padding;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
