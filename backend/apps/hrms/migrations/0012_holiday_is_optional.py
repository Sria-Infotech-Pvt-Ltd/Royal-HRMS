from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0011_holiday'),
    ]

    operations = [
        migrations.AddField(
            model_name='holiday',
            name='is_optional',
            field=models.BooleanField(
                default=False,
                help_text='Optional/restricted holiday — employee can choose to take it.',
            ),
        ),
        # Remove 'optional' from holiday_type choices — it was added by mistake in 0011.
        # Choices are only validated at the Python layer; no DB column change needed.
        migrations.AlterField(
            model_name='holiday',
            name='holiday_type',
            field=models.CharField(
                choices=[
                    ('national', 'National Holiday'),
                    ('regional', 'Regional Holiday'),
                    ('company',  'Company Holiday'),
                ],
                default='national',
                max_length=20,
            ),
        ),
    ]
