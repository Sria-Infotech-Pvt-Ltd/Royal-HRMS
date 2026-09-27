# Placement model (holder history, date-effective), plus OrgUnit/Position
# `is_active` for "deactivate instead of delete" once real history exists.
#
# Deliberately does NOT remove Position.holder yet — 0106 backfills existing
# Position.holder values into real Placement rows while the field still
# exists to read from; 0107 removes it once that backfill is done.

import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.contrib.postgres.operations
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

from apps.accounts.migration_utils import PortableExclusionConstraint, PostgresOnlyAddConstraint


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0104_position_branch"),
        ("branch", "0009_branch_gst_registration"),
    ]

    operations = [
        django.contrib.postgres.operations.BtreeGistExtension(),
        migrations.CreateModel(
            name="Placement",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("effective_from", models.DateField()),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "position",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placements",
                        to="accounts.position",
                    ),
                ),
            ],
            options={
                "db_table": "hrms_placements",
                "ordering": ["-effective_from"],
            },
        ),
        migrations.AddIndex(
            model_name="placement",
            index=models.Index(
                fields=["position", "effective_from"],
                name="hrms_placem_positio_61f0b1_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="placement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("effective_to__isnull", True),
                    ("effective_to__gte", models.F("effective_from")),
                    _connector="OR",
                ),
                name="placement_effective_to_gte_from",
            ),
        ),
        PostgresOnlyAddConstraint(
            model_name="placement",
            constraint=PortableExclusionConstraint(
                expressions=[
                    ("position", "="),
                    (
                        models.Func(
                            "effective_from",
                            "effective_to",
                            django.contrib.postgres.fields.ranges.RangeBoundary(
                                inclusive_lower=True, inclusive_upper=True
                            ),
                            function="daterange",
                            output_field=django.contrib.postgres.fields.ranges.DateRangeField(),
                        ),
                        "&&",
                    ),
                ],
                name="placement_position_no_overlap",
            ),
        ),
        PostgresOnlyAddConstraint(
            model_name="placement",
            constraint=PortableExclusionConstraint(
                expressions=[
                    ("employee", "="),
                    (
                        models.Func(
                            "effective_from",
                            "effective_to",
                            django.contrib.postgres.fields.ranges.RangeBoundary(
                                inclusive_lower=True, inclusive_upper=True
                            ),
                            function="daterange",
                            output_field=django.contrib.postgres.fields.ranges.DateRangeField(),
                        ),
                        "&&",
                    ),
                ],
                name="placement_employee_no_overlap",
            ),
        ),
        migrations.AddField(
            model_name="orgunit",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="position",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddConstraint(
            model_name="position",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_chief", True)),
                fields=("org_unit",),
                name="position_one_chief_per_unit",
            ),
        ),
    ]
