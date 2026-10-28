from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hrms', '0046_parental_leave_gender_eligibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='separationsettlement',
            name='is_recovery',
            field=models.BooleanField(default=False),
        ),
    ]
