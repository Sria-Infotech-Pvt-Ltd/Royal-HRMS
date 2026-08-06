"""
Fix attendance_face_registration_request FKs blocking user deletion.

Same class of drift as 0020 (face_verified column) and the accounts
l1_approver_role saga: attendance_face_registration_request is a table with
no corresponding model anywhere in this branch's apps/attendance/models.py
(confirmed — no FaceRegistrationRequest class, no admin registration, no
view references it). It was created by a ghost migration
(attendance.0022_face_registration_request, applied 2026-08-04 11:47:07 —
the file does not exist anywhere in this repo's history/branches/stash,
same pattern as accounts.0049_approval_workflow_role_fk) from some other,
uncommitted checkout hitting this shared Neon dev database.

Its employee_id column is a NOT NULL FK to hrms_users with no ON DELETE
clause, so Postgres defaults to NO ACTION — any attempt to delete a user
who has a face registration request (even from an unrelated feature this
branch never built) fails with a ForeignKeyViolation. This blocked deleting
users from Django admin.

Since this branch has no model or business logic touching this table at
all, there's no "correct" on_delete semantics to preserve — just make
deletes not explode. employee_id -> CASCADE (a face registration request
is meaningless without the employee it belongs to). approved_by_id is
already nullable, so -> SET NULL (approver being deleted shouldn't destroy
the request record). Data (4 rows, real face embeddings) is left intact.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0020_fix_face_verified_column_default'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE attendance_face_registration_request
                    DROP CONSTRAINT IF EXISTS attendance_face_regi_employee_id_9572e967_fk_hrms_user;
                ALTER TABLE attendance_face_registration_request
                    ADD CONSTRAINT attendance_face_regi_employee_id_9572e967_fk_hrms_user
                    FOREIGN KEY (employee_id) REFERENCES hrms_users(id) ON DELETE CASCADE;

                ALTER TABLE attendance_face_registration_request
                    DROP CONSTRAINT IF EXISTS attendance_face_regi_approved_by_id_8dc2795b_fk_hrms_user;
                ALTER TABLE attendance_face_registration_request
                    ADD CONSTRAINT attendance_face_regi_approved_by_id_8dc2795b_fk_hrms_user
                    FOREIGN KEY (approved_by_id) REFERENCES hrms_users(id) ON DELETE SET NULL;
            """,
            reverse_sql="""
                ALTER TABLE attendance_face_registration_request
                    DROP CONSTRAINT IF EXISTS attendance_face_regi_employee_id_9572e967_fk_hrms_user;
                ALTER TABLE attendance_face_registration_request
                    ADD CONSTRAINT attendance_face_regi_employee_id_9572e967_fk_hrms_user
                    FOREIGN KEY (employee_id) REFERENCES hrms_users(id);

                ALTER TABLE attendance_face_registration_request
                    DROP CONSTRAINT IF EXISTS attendance_face_regi_approved_by_id_8dc2795b_fk_hrms_user;
                ALTER TABLE attendance_face_registration_request
                    ADD CONSTRAINT attendance_face_regi_approved_by_id_8dc2795b_fk_hrms_user
                    FOREIGN KEY (approved_by_id) REFERENCES hrms_users(id);
            """,
        ),
    ]
