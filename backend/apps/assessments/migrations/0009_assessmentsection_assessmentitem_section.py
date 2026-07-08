import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0008_assessmentsettings_assessment_max_attempts_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessmentSection',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('assessment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sections',
                    to='assessments.assessment',
                )),
                ('title',      models.CharField(max_length=200)),
                ('order',      models.PositiveIntegerField(db_index=True, default=0)),
                ('score',      models.PositiveSmallIntegerField(default=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assessments_section',
                'ordering': ['order'],
            },
        ),
        migrations.AddField(
            model_name='assessmentitem',
            name='section',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='items',
                to='assessments.assessmentsection',
            ),
        ),
    ]
