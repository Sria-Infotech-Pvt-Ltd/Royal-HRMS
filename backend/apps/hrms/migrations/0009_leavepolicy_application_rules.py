from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0008_backfill_expense_number'),
    ]

    operations = [
        # ── Leave Application Rules ──
        migrations.AddField(
            model_name='leavepolicy',
            name='minimum_leave_duration',
            field=models.DecimalField(decimal_places=1, default=0.5, max_digits=4),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='maximum_leave_duration',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='maximum_consecutive_days',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='minimum_notice_period',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_half_day',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_backdated_leave',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='maximum_backdated_days',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_future_leave',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='maximum_future_days',
            field=models.PositiveIntegerField(default=0),
        ),
        # ── Holiday & Week-off Rules ──
        migrations.AddField(
            model_name='leavepolicy',
            name='sandwich_leave_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='count_holidays_as_leave',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='count_weekoffs_as_leave',
            field=models.BooleanField(default=False),
        ),
        # ── Eligibility Rules ──
        migrations.AddField(
            model_name='leavepolicy',
            name='applicable_branches',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='applicable_departments',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='applicable_designations',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='applicable_employment_types',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='applicable_gender',
            field=models.CharField(
                choices=[('all', 'All'), ('male', 'Male'), ('female', 'Female')],
                default='all',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='minimum_service_period',
            field=models.PositiveIntegerField(default=0),
        ),
        # ── Documentation Rules ──
        migrations.AddField(
            model_name='leavepolicy',
            name='attachment_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='medical_certificate_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='medical_certificate_after_days',
            field=models.PositiveIntegerField(default=3),
        ),
        # ── Leave Restrictions ──
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_negative_balance',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='convert_to_lop',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_leave_cancellation',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='cancellation_allowed_until',
            field=models.PositiveIntegerField(default=0),
        ),
        # ── Additional Rules ──
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_probation_leave',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_notice_period_leave',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_leave_extension',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='leavepolicy',
            name='allow_leave_combination',
            field=models.BooleanField(default=False),
        ),
    ]
