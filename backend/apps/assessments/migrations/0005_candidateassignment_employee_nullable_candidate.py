from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0004_candidateassignment_attempt_count'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Make candidate nullable (existing rows already have a value — no data loss)
        migrations.AlterField(
            model_name='candidateassignment',
            name='candidate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='assessment_assignments',
                to='recruitment.candidate',
            ),
        ),
        # Add employee FK
        migrations.AddField(
            model_name='candidateassignment',
            name='employee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='employee_assessment_assignments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Drop the old unique_together
        migrations.AlterUniqueTogether(
            name='candidateassignment',
            unique_together=set(),
        ),
        # Add conditional unique constraints
        migrations.AddConstraint(
            model_name='candidateassignment',
            constraint=models.UniqueConstraint(
                condition=models.Q(candidate__isnull=False),
                fields=['candidate', 'assessment'],
                name='unique_candidate_assessment',
            ),
        ),
        migrations.AddConstraint(
            model_name='candidateassignment',
            constraint=models.UniqueConstraint(
                condition=models.Q(employee__isnull=False),
                fields=['employee', 'assessment'],
                name='unique_employee_assessment',
            ),
        ),
    ]
