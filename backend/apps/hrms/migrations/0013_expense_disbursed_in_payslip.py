from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0012_holiday_is_optional'),
        ('payroll', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='disbursed_in_payslip',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='disbursed_expenses',
                to='payroll.employeepayslip',
            ),
        ),
    ]
