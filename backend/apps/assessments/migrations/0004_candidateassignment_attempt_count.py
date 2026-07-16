from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0003_alter_assessment_id_alter_assessmentitem_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidateassignment',
            name='attempt_count',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
