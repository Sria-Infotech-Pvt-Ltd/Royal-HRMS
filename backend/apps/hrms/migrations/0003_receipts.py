import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0002_seed_expense_permissions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='expense',
            name='receipt',
        ),
        migrations.CreateModel(
            name='ExpenseReceipt',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file',       models.FileField(upload_to='expenses/receipts/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expense',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='receipts',
                    to='hrms.expense',
                )),
            ],
            options={
                'db_table': 'hrms_expense_receipt',
            },
        ),
    ]
