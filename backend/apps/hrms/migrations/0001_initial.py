import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0023_onboarding_permission_and_portal_template'),
        ('branch',   '0003_branch_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id',           models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title',        models.CharField(max_length=200)),
                ('category',     models.CharField(
                    choices=[
                        ('travel',    'Travel'),
                        ('meals',     'Meals'),
                        ('equipment', 'Equipment'),
                        ('other',     'Other'),
                    ],
                    max_length=20,
                )),
                ('amount',       models.DecimalField(decimal_places=2, max_digits=10)),
                ('expense_date', models.DateField()),
                ('description',  models.TextField(blank=True, default='')),
                ('receipt',      models.FileField(upload_to='expenses/receipts/')),
                ('status',       models.CharField(
                    choices=[
                        ('pending',  'Pending'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
                ('employee',     models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='expenses',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('branch',       models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='expenses',
                    to='branch.branch',
                )),
            ],
            options={
                'db_table': 'hrms_expense',
                'ordering': ['-created_at'],
            },
        ),
    ]
