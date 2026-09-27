# Encrypts FaceRegistrationRequest.face_embedding at rest, same tier of
# sensitivity as PAN/Aadhaar/bank details (see
# apps/accounts/migrations/0064_encrypt_sensitive_pii.py, the precedent this
# migration mirrors).
#
# Unlike that migration, the underlying column here is jsonb, not a plain
# CharField — Fernet ciphertext is an opaque base64 string, not valid JSON,
# so it can't be written into a jsonb column as-is. Django's own migration
# autodetector considers a JSONField -> EncryptedJSONField (TextField
# subclass) AlterField a schema no-op (confirmed via sqlmigrate) since it
# only compares Python field classes' declared parameters, not the fact that
# the two field types map to genuinely different Postgres column types here
# — so the actual jsonb->text column cast below is done explicitly via
# RunSQL, the same "Django's automatic ALTER doesn't do what's actually
# needed" situation apps/attendance/migrations/0028 and 0029 already hit and
# hand-fixed the same way.
#
# Order matters: the raw column-type cast must run BEFORE the data is
# touched through the new field class, so RunPython below (which reads then
# re-saves every row to encrypt it) is doing so against a column that's
# already really `text`, not still `jsonb` underneath a Python-level type
# that no longer matches it.
from django.db import migrations

import core.encrypted_fields


def cast_jsonb_to_text(apps, schema_editor):
    # Postgres-only: AlterField alone doesn't actually change the column
    # type there (see module docstring — Django's autodetector treats this
    # AlterField as a no-op since it only compares field classes, not the
    # underlying jsonb-vs-text column types). SQLite has no such gap — its
    # schema editor implements every AlterField via a real table rebuild
    # using the NEW field's type, so the AlterField operation right after
    # this one already does the real work there; this raw cast would just
    # be invalid SQLite syntax for a no-op.
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE attendance_face_registration_request "
            "ALTER COLUMN face_embedding TYPE text USING face_embedding::text;"
        )


def encrypt_existing_face_embeddings(apps, schema_editor):
    """
    One-pass, idempotent backfill — same pattern as
    accounts/migrations/0064_encrypt_sensitive_pii.py's encrypt_existing_pii:
    reassigning the field to its own current value re-saves it through
    EncryptedJSONField.get_prep_value, encrypting legacy plaintext (now
    stored as plain JSON text after the jsonb->text cast above) for the
    first time. Rows already encrypted (e.g. if this migration is re-run)
    are simply decrypted then re-encrypted with a fresh IV — same value,
    harmless churn, not data loss.
    """
    FaceRegistrationRequest = apps.get_model('attendance', 'FaceRegistrationRequest')
    for row in FaceRegistrationRequest.objects.all().iterator():
        row.save(update_fields=['face_embedding'])


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0038_alter_faceverificationattempt_rejection_reason'),
    ]

    operations = [
        migrations.RunPython(cast_jsonb_to_text, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='faceregistrationrequest',
            name='face_embedding',
            field=core.encrypted_fields.EncryptedJSONField(),
        ),
        migrations.RunPython(encrypt_existing_face_embeddings, migrations.RunPython.noop),
    ]
