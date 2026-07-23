import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0013_seed_leave_approval_workflow'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # LeavePolicy — new carry-forward config fields
        migrations.AddField(
            model_name='leavepolicy',
            name='carry_forward_type',
            field=models.CharField(
                max_length=20,
                choices=[('limited', 'Limited'), ('unlimited', 'Unlimited')],
                default='limited',
            ),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='carry_forward_mode',
            field=models.CharField(
                max_length=20,
                choices=[('automatic', 'Automatic'), ('manual', 'Manual')],
                default='automatic',
            ),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='carry_forward_expiry_days',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Days before carry-forwarded balance expires. 0 = never.',
            ),
        ),

        # LeaveBalance — expiry date for carry-forwarded amount
        migrations.AddField(
            model_name='leavebalance',
            name='carry_forward_expiry_date',
            field=models.DateField(null=True, blank=True),
        ),

        # CarryForwardLog — audit table
        migrations.CreateModel(
            name='CarryForwardLog',
            fields=[
                ('id',              models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('from_year',       models.PositiveIntegerField()),
                ('to_year',         models.PositiveIntegerField()),
                ('leave_type',      models.CharField(max_length=50, blank=True, default='')),
                ('process_mode',    models.CharField(max_length=20, default='execute')),
                ('total_processed', models.PositiveIntegerField(default=0)),
                ('total_skipped',   models.PositiveIntegerField(default=0)),
                ('total_failed',    models.PositiveIntegerField(default=0)),
                ('is_completed',    models.BooleanField(default=False)),
                ('notes',           models.TextField(blank=True, default='')),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('updated_at',      models.DateTimeField(auto_now=True)),
                ('executed_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='carry_forward_executions',
                )),
            ],
            options={
                'db_table': 'hrms_carry_forward_logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
