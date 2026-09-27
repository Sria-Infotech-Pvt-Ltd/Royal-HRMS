"""
Fix attendance_face_registration_request.is_active blocking every face
registration submission and HR-register call.

Same class of drift as 0028 (face_verified default) and 0029 (FK
constraints): this database's attendance_face_registration_request table
has an extra column, is_active (boolean NOT NULL, no default), that
FaceRegistrationRequest (apps/attendance/models.py) has never declared in
any migration in this branch's history — another leftover from the
different, uncommitted checkout that created this table on the shared Neon
dev database (see 0029's docstring for the full story).

Since Django's generated INSERT never mentions a column the model doesn't
know about, and is_active has no default, every single face registration
submission and HR-register call was hitting a NOT NULL violation and
500ing (FaceRegistrationSubmitSerializer / FaceRegistrationHRRegisterSerializer).

This is a database-only fix (plain RunSQL, no state change) — give the
column a default of true, matching every other is_active flag in this app
(WorkingHoursPolicy, WeeklyDayPolicy, etc. all default to True). Left in
place rather than dropped, same reasoning as 0028: if this branch's face
registration model is ever extended with its own is_active semantics, the
column and its data are still there to adopt.
"""
from django.db import migrations


def set_default(apps, schema_editor):
    # Postgres-only drift fix (see module docstring) — a fresh SQLite
    # install never has this extra column, so there's nothing to fix.
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE attendance_face_registration_request ALTER COLUMN is_active SET DEFAULT true;")


def drop_default(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE attendance_face_registration_request ALTER COLUMN is_active DROP DEFAULT;")


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0031_face_registration_consent'),
    ]

    operations = [
        migrations.RunPython(set_default, drop_default),
    ]
