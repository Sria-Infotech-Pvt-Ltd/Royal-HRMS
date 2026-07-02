import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('branch', '0006_branch_gps_precision_12_8'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeBranchAccess',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_primary', models.BooleanField(default=False, help_text="True if this is the employee's home branch.")),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee',   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branch_access', to=settings.AUTH_USER_MODEL)),
                ('branch',     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employee_access', to='branch.branch')),
            ],
            options={
                'db_table': 'employee_branch_access',
                'ordering': ['-is_primary', 'branch__branch_name'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='employeebranchaccess',
            unique_together={('employee', 'branch')},
        ),
    ]
