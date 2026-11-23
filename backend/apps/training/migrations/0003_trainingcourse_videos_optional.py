from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0002_seed_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingcourse',
            name='videos_optional',
            field=models.BooleanField(default=False),
        ),
    ]
