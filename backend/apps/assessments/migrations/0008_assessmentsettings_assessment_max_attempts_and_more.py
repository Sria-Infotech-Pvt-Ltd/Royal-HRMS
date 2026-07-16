from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0007_candidateassignment_deadline'),
    ]

    operations = [
        # Global settings singleton table
        migrations.CreateModel(
            name='AssessmentSettings',
            fields=[
                ('id',                      models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_pass_percentage', models.PositiveSmallIntegerField(default=70)),
                ('max_attempts',            models.PositiveSmallIntegerField(default=3)),
                ('time_limit_mins',         models.PositiveSmallIntegerField(blank=True, null=True)),
                ('created_at',              models.DateTimeField(auto_now_add=True)),
                ('updated_at',              models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'assessments_settings'},
        ),
        # Per-assessment overrides
        migrations.AddField(
            model_name='assessment',
            name='max_attempts',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='assessment',
            name='time_limit_mins',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        # Track when a candidate/employee first started an attempt
        migrations.AddField(
            model_name='candidateassignment',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
