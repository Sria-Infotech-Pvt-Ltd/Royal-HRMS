from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0006_manager_attendance_approvals'),
        ('branch', '0008_merge_0007'),
    ]

    operations = [
        migrations.AddField(
            model_name='payrollcycle',
            name='branch',
            field=models.ForeignKey(
                blank=True,
                help_text='Branch this cycle is scoped to. Null = company-wide (legacy).',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='payroll_cycles',
                to='branch.branch',
            ),
        ),
    ]
