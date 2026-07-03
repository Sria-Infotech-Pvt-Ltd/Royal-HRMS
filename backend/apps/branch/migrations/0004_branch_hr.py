from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_department_manager'),
        ('branch', '0003_branch_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='hr',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='managed_branches',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
