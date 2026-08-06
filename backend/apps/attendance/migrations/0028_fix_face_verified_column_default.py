"""
Fix attendance_punches.face_verified blocking every single punch.

Same class of drift as tonight's other fixes (aadhaar/uan, can_manage_branch,
l1/l2_approver_role): this database's attendance_punches table has two extra
columns, face_verified (boolean NOT NULL, no default) and face_match_distance
(nullable), that AttendancePunch (apps/attendance/models.py) has never
declared in any migration in this branch's history — they're leftovers from
a different branch that was building a facial-recognition punch feature
(the "facial_recognition.approve" permission exists in the permission seed,
suggesting the feature was planned, but never landed in this branch's
AttendancePunch model).

Since Django's generated INSERT never mentions a column the model doesn't
know about, and face_verified has no default, every single clock-in/clock-out
was hitting a NOT NULL violation and 500ing (AttendancePunchView).

This is a database-only fix (SeparateDatabaseAndState, no state change) —
just give the column a default so inserts succeed. face_match_distance is
already nullable and isn't blocking anything, so it's left as-is. If the
facial-recognition feature is ever built out in this branch, both columns
are still there, untouched, ready to be adopted into the model properly.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0027_face_verification_attempt'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE attendance_punches ALTER COLUMN face_verified SET DEFAULT false;",
            reverse_sql="ALTER TABLE attendance_punches ALTER COLUMN face_verified DROP DEFAULT;",
        ),
    ]
