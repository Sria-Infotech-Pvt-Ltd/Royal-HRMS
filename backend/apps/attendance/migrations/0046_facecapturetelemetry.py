import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0045_seed_sgt_ict_and_uk_shifts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FaceCaptureTelemetry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("capture_session_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("purpose", models.CharField(choices=[("verify", "Punch verification"), ("register", "Registration")], default="verify", max_length=10)),
                ("outcome", models.CharField(choices=[("captured", "Captured"), ("cancelled", "Cancelled by user"), ("failed", "Ended on a failure screen"), ("error", "Camera/model error")], max_length=10)),
                ("duration_ms", models.PositiveIntegerField(default=0, help_text="Camera open → session end.")),
                ("liveness_attempts", models.PositiveSmallIntegerField(default=0)),
                ("quality_failures", models.PositiveSmallIntegerField(default=0)),
                ("auto_resumes", models.PositiveSmallIntegerField(default=0)),
                ("manual_retries", models.PositiveSmallIntegerField(default=0)),
                ("tf_backend", models.CharField(blank=True, default="", max_length=16)),
                ("avg_fps", models.FloatField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=255)),
                ("details", models.JSONField(blank=True, default=dict, help_text="Bounded diagnostics: failure-reason counts, liveness signals seen, last quality metrics, lighting hints shown, flow version.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="face_capture_telemetry", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "attendance_face_capture_telemetry",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["employee", "created_at"], name="fct_emp_time_idx"),
                    models.Index(fields=["purpose", "outcome", "created_at"], name="fct_purpose_outcome_idx"),
                ],
            },
        ),
    ]
