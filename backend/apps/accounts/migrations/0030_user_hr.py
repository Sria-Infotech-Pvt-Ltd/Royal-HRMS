from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_department_manager'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='hr',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='hr_employees',
                to='accounts.user',
            ),
        ),
    ]
