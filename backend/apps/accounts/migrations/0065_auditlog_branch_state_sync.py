# hrms_audit_logs already has a `branch` column in the real database — same
# class of drift as 0054_employeeprofile_aadhar_uan_state_sync.py and
# 0059_widen_employee_document_file_name_column.py: it was added by a
# migration living on a different branch history sharing this dev database,
# so this branch's model/migration state never declared it. The column is
# varchar(100) NOT NULL with no server-side default, so every
# AuditLog.objects.create() call (login, logout, password reset, role/dept
# CRUD, document uploads, ...) omitted it entirely from the INSERT and
# crashed with a NotNullViolation.
#
# SeparateDatabaseAndState brings Django's model/migration STATE in line
# with what the database already physically has, without re-running
# AddField (which would fail with "column already exists"). Nothing in the
# app reads AuditLog.branch today — audit-log branch scoping goes through
# the related user (user__branch) — so the field's default empty string is
# fine for now.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0064_merge_20260812_1213'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='auditlog',
                    name='branch',
                    field=models.CharField(blank=True, max_length=100),
                ),
            ],
            database_operations=[],
        ),
    ]
