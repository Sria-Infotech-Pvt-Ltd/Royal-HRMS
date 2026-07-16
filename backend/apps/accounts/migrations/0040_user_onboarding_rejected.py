"""Add 'rejected' to User.onboarding_status choices and update existing rejected rows."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0039_seed_birthday_wish_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='onboarding_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending',   'Pending'),
                    ('draft',     'In Progress'),
                    ('submitted', 'Submitted — awaiting approval'),
                    ('complete',  'Complete'),
                    ('rejected',  'Needs Revision'),
                ],
                default='pending',
            ),
        ),
    ]
