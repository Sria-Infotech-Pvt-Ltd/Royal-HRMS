from django.db import migrations, models

# These two columns already exist in the real database — they were added by
# a teammate's migration (accounts.0048_add_uan_aadhar_to_employee_profile,
# applied 2026-07-31) that lives on the `demo` branch under a migration
# number ('0048') that collided with this branch's own unrelated 0048. Since
# this branch's migration history/model never declared these fields, every
# EmployeeProfile INSERT (e.g. onboarding's get_or_create) omitted them
# entirely from the SQL — and because the DB columns are NOT NULL with no
# server-side default, every new employee's first onboarding page load
# crashed with a NotNullViolation.
#
# SeparateDatabaseAndState updates Django's model/migration STATE to match
# what the database already physically has, without re-running AddField
# (which would fail with "column already exists"). When this branch is
# eventually merged with demo, the two colliding 0048 files need
# renumbering — this migration's dependency will need re-pointing at that
# point, but the state-only operation itself is unaffected by renumbering.
class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0051_flip_payroll_admin_hr'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='employeeprofile',
                    name='name_as_per_aadhar',
                    field=models.CharField(blank=True, help_text='Name exactly as printed on the Aadhaar card', max_length=150),
                ),
                migrations.AddField(
                    model_name='employeeprofile',
                    name='uan_number',
                    field=models.CharField(blank=True, help_text='12-digit Universal Account Number issued by EPFO', max_length=12),
                ),
            ],
            database_operations=[],
        ),
    ]
