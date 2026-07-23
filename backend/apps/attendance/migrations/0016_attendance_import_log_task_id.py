from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0015_audit_log_and_invalid_punch'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendanceimportlog',
            name='skipped_rows',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='attendanceimportlog',
            name='task_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
