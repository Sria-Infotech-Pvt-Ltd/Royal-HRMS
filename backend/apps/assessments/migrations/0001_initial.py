import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recruitment', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assessment',
            fields=[
                ('id',          models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('title',       models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, default='')),
                ('is_active',   models.BooleanField(default=True, db_index=True)),
                ('is_default',  models.BooleanField(default=False)),
                ('created_by',  models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='created_assessments',
                )),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('updated_at',  models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assessments_assessment',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AssessmentItem',
            fields=[
                ('id',             models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('assessment',     models.ForeignKey(
                    'assessments.Assessment',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                )),
                ('item_type',      models.CharField(max_length=10, choices=[('video', 'Video'), ('quiz', 'Quiz / MCQ')])),
                ('title',          models.CharField(max_length=200)),
                ('order',          models.PositiveIntegerField(default=0, db_index=True)),
                ('video_url',      models.URLField(blank=True, default='')),
                ('duration_secs',  models.PositiveIntegerField(null=True, blank=True)),
                ('question',       models.TextField(blank=True, default='')),
                ('option_a',       models.CharField(max_length=500, blank=True, default='')),
                ('option_b',       models.CharField(max_length=500, blank=True, default='')),
                ('option_c',       models.CharField(max_length=500, blank=True, default='')),
                ('option_d',       models.CharField(max_length=500, blank=True, default='')),
                ('correct_option', models.CharField(max_length=1, blank=True, default='')),
                ('pass_score',     models.PositiveSmallIntegerField(default=1)),
                ('created_at',     models.DateTimeField(auto_now_add=True)),
                ('updated_at',     models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assessments_item',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='CandidateAssignment',
            fields=[
                ('id',           models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('candidate',    models.ForeignKey(
                    'recruitment.Candidate',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assessment_assignments',
                )),
                ('assessment',   models.ForeignKey(
                    'assessments.Assessment',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignments',
                )),
                ('assigned_by',  models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='assessment_assignments_made',
                )),
                ('status',       models.CharField(
                    max_length=20,
                    choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('complete', 'Complete')],
                    default='pending',
                    db_index=True,
                )),
                ('score',        models.PositiveSmallIntegerField(default=0)),
                ('max_score',    models.PositiveSmallIntegerField(default=0)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assessments_candidate_assignment',
                'ordering': ['-created_at'],
                'unique_together': {('candidate', 'assessment')},
            },
        ),
        migrations.CreateModel(
            name='CandidateResponse',
            fields=[
                ('id',              models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('assignment',      models.ForeignKey(
                    'assessments.CandidateAssignment',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='responses',
                )),
                ('item',            models.ForeignKey(
                    'assessments.AssessmentItem',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='responses',
                )),
                ('is_watched',      models.BooleanField(default=False)),
                ('selected_option', models.CharField(max_length=1, blank=True, default='')),
                ('is_correct',      models.BooleanField(null=True, blank=True)),
                ('score_awarded',   models.PositiveSmallIntegerField(default=0)),
                ('responded_at',    models.DateTimeField(null=True, blank=True)),
                ('created_at',      models.DateTimeField(auto_now_add=True)),
                ('updated_at',      models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assessments_candidate_response',
                'unique_together': {('assignment', 'item')},
            },
        ),
    ]
