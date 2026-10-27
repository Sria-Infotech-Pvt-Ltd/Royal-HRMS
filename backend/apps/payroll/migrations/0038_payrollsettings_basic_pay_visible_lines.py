from django.db import migrations, models

from apps.payroll.models import default_basic_pay_visible_lines


class Migration(migrations.Migration):
    dependencies = [
        ('payroll', '0037_company_allowance_catalogue'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollsettings',
            name='basic_pay_visible_lines',
            field=models.JSONField(
                default=default_basic_pay_visible_lines,
                help_text='Pay breakup rows visible in the employee Basic Pay editor. Hiding a row does not change its calculations.',
            ),
        ),
    ]
