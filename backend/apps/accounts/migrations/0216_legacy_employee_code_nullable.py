from django.db import migrations


class Migration(migrations.Migration):
    """hrms_users.legacy_employee_code is not a Django-tracked field — it does
    not appear in models.py, in any migration, or anywhere in git history for
    this repo. It exists only on this environment's actual table (added by
    some out-of-band SQL at an unknown point), carrying a NOT NULL constraint
    nothing in the codebase ever satisfies. That blocks every ordinary
    User.objects.create_user() call on this database with a NotNullViolation.
    Relaxes the constraint only — doesn't touch the column or its data,
    since whatever values already exist in it might still matter to whoever
    added it, and dropping it outright isn't needed to unblock user creation."""

    dependencies = [
        ('accounts', '0215_seed_report_shared_email_template'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE hrms_users ALTER COLUMN legacy_employee_code DROP NOT NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
