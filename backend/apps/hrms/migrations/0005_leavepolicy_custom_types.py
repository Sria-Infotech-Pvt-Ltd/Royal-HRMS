from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0004_leave_module'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leavepolicy',
            name='leave_type',
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='leave_type_label',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
