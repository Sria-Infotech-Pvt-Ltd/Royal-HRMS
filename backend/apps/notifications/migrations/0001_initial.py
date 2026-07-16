import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('notification_type', models.CharField(
                    db_index=True, max_length=50,
                    choices=[
                        ('leave_applied',          'Leave Applied'),
                        ('leave_manager_approved', 'Leave Approved by Manager'),
                        ('leave_manager_rejected', 'Leave Rejected by Manager'),
                        ('leave_hr_approved',      'Leave Approved by HR'),
                        ('leave_hr_rejected',      'Leave Rejected by HR'),
                        ('leave_cancelled',        'Leave Cancelled'),
                        ('attendance',             'Attendance'),
                        ('regularization',         'Regularization'),
                        ('permission',             'Permission'),
                        ('holiday',                'Holiday'),
                        ('announcement',           'Announcement'),
                    ],
                )),
                ('module', models.CharField(
                    db_index=True, max_length=50,
                    choices=[
                        ('leave',          'Leave'),
                        ('attendance',     'Attendance'),
                        ('regularization', 'Regularization'),
                        ('permission',     'Permission'),
                        ('holiday',        'Holiday'),
                        ('announcement',   'Announcement'),
                    ],
                )),
                ('reference_id', models.CharField(blank=True, default='', max_length=100)),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at'],
            },
        ),
    ]
