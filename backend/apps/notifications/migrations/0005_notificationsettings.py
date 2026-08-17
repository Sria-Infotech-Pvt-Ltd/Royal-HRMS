import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0004_alter_notification_module_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationSettings',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_leave_enabled', models.BooleanField(default=True)),
                ('is_expense_enabled', models.BooleanField(default=True)),
                ('is_separation_enabled', models.BooleanField(default=True)),
                ('is_payroll_enabled', models.BooleanField(default=True)),
                ('is_approval_enabled', models.BooleanField(default=True)),
                ('is_document_enabled', models.BooleanField(default=True)),
                ('is_attendance_enabled', models.BooleanField(default=True)),
                ('is_system_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_settings',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'notification_settings',
            },
        ),
    ]
