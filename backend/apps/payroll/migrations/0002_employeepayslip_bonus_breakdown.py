from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeepayslip',
            name='bonus_breakdown',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='[{"type": "Annual", "amount": "5000.00", "note": ""}]',
            ),
        ),
    ]
