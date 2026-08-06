"""
Fix attendance_employee_weekly_off_assignment FKs blocking user deletion.

Same ghost-table pattern as 0021 (attendance_face_registration_request):
this table has no corresponding model anywhere in apps/attendance/models.py
in this branch. It was created by attendance.0020_employeeweeklyoffassignment,
applied 2026-08-03 06:40:21 — no file with that name exists anywhere in this
repo's history, branches, or stash. Confirmed via a full scan comparing every
table in the database against every table Django's model registry knows
about in this branch (apps.get_models()) — this table, along with
attendance_face_registration_request (already fixed) and
attendance_settings_face_verification (harmless — its only FK is to
attendance_settings, not hrms_users), were the only ones without a model.

Since Django's admin delete collector only walks models it knows about, it
never visits this table's rows before deleting a user, so Postgres's default
NO ACTION FK constraint blocked any delete of a user who has a weekly-off
assignment. Same fix as 0021: employee_id -> CASCADE (assignment is
meaningless without the employee), created_by_id/updated_by_id -> SET NULL
(both already nullable, just audit metadata). Data (2 rows) left intact.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0021_fix_face_registration_request_fk_constraints'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__employee_id_52adab0b_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__employee_id_52adab0b_fk_hrms_user
                    FOREIGN KEY (employee_id) REFERENCES hrms_users(id) ON DELETE CASCADE;

                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__created_by_id_148e6f6e_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__created_by_id_148e6f6e_fk_hrms_user
                    FOREIGN KEY (created_by_id) REFERENCES hrms_users(id) ON DELETE SET NULL;

                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__updated_by_id_57915cef_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__updated_by_id_57915cef_fk_hrms_user
                    FOREIGN KEY (updated_by_id) REFERENCES hrms_users(id) ON DELETE SET NULL;
            """,
            reverse_sql="""
                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__employee_id_52adab0b_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__employee_id_52adab0b_fk_hrms_user
                    FOREIGN KEY (employee_id) REFERENCES hrms_users(id);

                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__created_by_id_148e6f6e_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__created_by_id_148e6f6e_fk_hrms_user
                    FOREIGN KEY (created_by_id) REFERENCES hrms_users(id);

                ALTER TABLE attendance_employee_weekly_off_assignment
                    DROP CONSTRAINT IF EXISTS attendance_employee__updated_by_id_57915cef_fk_hrms_user;
                ALTER TABLE attendance_employee_weekly_off_assignment
                    ADD CONSTRAINT attendance_employee__updated_by_id_57915cef_fk_hrms_user
                    FOREIGN KEY (updated_by_id) REFERENCES hrms_users(id);
            """,
        ),
    ]
