"""
Phase 2 Task C.5 — GIN index on CustomRecord.data for fast attribute
filtering, using jsonb_path_ops (smaller, faster for containment/
equality lookups than the default jsonb_ops — the only operator class
services_attributes.py's filter helper actually needs).

Postgres-specific; not expressible through plain Django field options,
hence RunSQL. Guarded with IF NOT EXISTS / IF EXISTS so it's safe to
re-run and safe on a fresh (non-SQLite — see apps/accounts/migration_utils.py
for this repo's own existing convention of Postgres-only index
migrations) database.
"""
from django.db import migrations


def _create_index(apps, schema_editor):
    # GIN/jsonb_path_ops has no SQLite equivalent — local dev (USE_SQLITE=1)
    # simply skips this, same convention apps.accounts.migration_utils
    # already established for Postgres-only ExclusionConstraints.
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'CREATE INDEX IF NOT EXISTS pcr_data_gin_idx ON platform_custom_records USING GIN (data jsonb_path_ops);'
    )


def _drop_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP INDEX IF EXISTS pcr_data_gin_idx;')


class Migration(migrations.Migration):

    dependencies = [
        ('platform_core', '0003_phase2_field_form_custom_object_engine'),
    ]

    operations = [
        migrations.RunPython(_create_index, _drop_index),
    ]
