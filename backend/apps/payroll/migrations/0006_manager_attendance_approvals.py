from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0005_payroll_adjustments'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagerAttendanceApproval',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cycle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='manager_approvals',
                    to='payroll.payrollcycle',
                )),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payroll_attendance_approvals',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'payroll_manager_attendance_approvals',
                'ordering': ['manager__full_name'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='managerattendanceapproval',
            unique_together={('cycle', 'manager')},
        ),
    ]
