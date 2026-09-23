from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Adds the 'role_change' choice to notification_type/module — metadata
    only (Django CharField choices are not enforced at the database level,
    so this is a no-op ALTER at the schema level, same as every prior
    *_choices migration in this app, e.g. 0003_add_security_alert_choices).
    Needed so the role-change Notification rows created by
    apps.notifications.signals._on_promotion_record_created (role-only
    branch) match the model's declared choices/migration state exactly.
    """

    dependencies = [
        ("notifications", "0009_alter_notification_module_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="module",
            field=models.CharField(
                choices=[
                    ("leave", "Leave"),
                    ("attendance", "Attendance"),
                    ("regularization", "Regularization"),
                    ("permission", "Permission"),
                    ("holiday", "Holiday"),
                    ("announcement", "Announcement"),
                    ("birthday", "Birthday"),
                    ("promotion", "Promotion"),
                    ("role_change", "Role Change"),
                    ("security", "Security"),
                    ("expense", "Expense"),
                    ("separation", "Separation"),
                    ("documents", "Documents"),
                    ("facial_recognition", "Facial Recognition"),
                    ("payroll", "Payroll"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("leave_applied", "Leave Applied"),
                    ("leave_manager_approved", "Leave Approved by Manager"),
                    ("leave_manager_rejected", "Leave Rejected by Manager"),
                    ("leave_hr_approved", "Leave Approved by HR"),
                    ("leave_hr_rejected", "Leave Rejected by HR"),
                    ("leave_cancelled", "Leave Cancelled"),
                    ("attendance", "Attendance"),
                    ("regularization", "Regularization"),
                    ("permission", "Permission"),
                    ("holiday", "Holiday"),
                    ("announcement", "Announcement"),
                    ("birthday", "Birthday"),
                    ("promotion", "Promotion"),
                    ("role_change", "Role Change"),
                    ("security_alert", "Security Alert"),
                    ("expense_submitted", "Expense Submitted"),
                    ("expense_status", "Expense Status Update"),
                    ("separation_submitted", "Separation Request Submitted"),
                    ("separation_status", "Separation Status Update"),
                    ("document_uploaded", "Document Uploaded"),
                    ("password_reset", "Password Reset"),
                    ("face_registration_status", "Face ID Registration Status"),
                    ("payslip_dispatched", "Payslip Dispatched"),
                    ("payslip_paid", "Payslip Paid"),
                ],
                db_index=True,
                max_length=50,
            ),
        ),
    ]
