from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0031_merge_0029'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='assessment_status',
            field=models.CharField(
                max_length=20,
                choices=[('pending', 'Pending'), ('complete', 'Complete')],
                default='pending',
            ),
        ),
    ]
