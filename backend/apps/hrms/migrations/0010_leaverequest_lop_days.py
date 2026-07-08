from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0009_leavepolicy_application_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='lop_days',
            field=models.DecimalField(decimal_places=1, default=0, max_digits=4),
        ),
    ]
