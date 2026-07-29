import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_cancel_payroll_cycle'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add adjustment totals to existing payslips
        migrations.AddField(
            model_name='employeepayslip',
            name='adjustments_earning',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='employeepayslip',
            name='adjustments_deduction',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        # New PayrollAdjustment table
        migrations.CreateModel(
            name='PayrollAdjustment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('month', models.DateField()),
                ('type', models.CharField(choices=[('addition', 'Addition'), ('deduction', 'Deduction'), ('arrear', 'Arrear')], max_length=20)),
                ('label', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payroll_adjustments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_payroll_adjustments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'payroll_adjustments',
                'ordering': ['month', 'employee__full_name', 'type'],
            },
        ),
    ]
