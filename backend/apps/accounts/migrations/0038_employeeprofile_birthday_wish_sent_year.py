from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0037_update_email_templates_for_new_assessment_flow'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeprofile',
            name='birthday_wish_sent_year',
            field=models.PositiveSmallIntegerField(
                null=True, blank=True,
                help_text='Year in which the last birthday wish email was sent. '
                          'Used to prevent duplicate sends on Celery beat retries.',
            ),
        ),
    ]
