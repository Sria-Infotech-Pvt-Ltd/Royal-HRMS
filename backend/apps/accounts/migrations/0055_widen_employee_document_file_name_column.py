"""
Widen hrms_employee_documents.file_name to varchar(255) in the database.

0021_onboarding_models.py declared EmployeeDocument.file_name as
CharField(max_length=255) from the very start, and nothing since has ever
declared it any narrower — so Django's migration state has always said 255.
But this database's actual column is varchar(100) (same class of drift as
0052_employeeprofile_aadhar_uan_state_sync.py's aadhaar/uan columns: the
physical table was created outside what these migration files describe,
likely from an earlier/different branch history sharing this dev database).

EmployeeDocumentView.post() (apps/accounts/views.py) stores the uploaded
file's original filename verbatim via file_name=file_obj.name — any
onboarding document with a filename over 100 characters (common for phone
camera exports and descriptively-named scans) hit
psycopg2.errors.StringDataRightTruncation and surfaced as a 500 on
POST /api/onboarding/documents/.

Since Django's model state already says 255, this is a database-only fix
(SeparateDatabaseAndState with no state_operations) — there is no model
change to record, just the live column to bring in line with it.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0054_grant_recruitment_view_to_system_admin'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.AlterField(
                    model_name='employeedocument',
                    name='file_name',
                    field=models.CharField(max_length=255),
                ),
            ],
        ),
    ]
