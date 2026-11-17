from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0052_short_hours_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancepunchrules',
            name='wfh_max_backdated_days',
            field=models.PositiveSmallIntegerField(default=0, help_text='How many days in the past a work-from-home request may start. 0 = today or a future date only.'),
        ),
    ]
