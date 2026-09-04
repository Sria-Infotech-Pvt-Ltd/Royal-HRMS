"""
Encrypt CompanyDirector.din at rest and switch its uniqueness constraint to
a deterministic blind-index column (din_hash) instead of the (now
non-deterministic-ciphertext) din column itself.

din can hold a Partnership/Trust partner's PAN (not just a DIN — see the
model's own docstring), the same PII tier as EmployeeProfile.pan_number,
which already gets this treatment. This was deliberately deferred out of
0121_encrypt_company_pii for exactly this reason: encrypting din without
also reworking the uniqueness constraint first would have silently broken
the (company, din) duplicate check the 409-Conflict live test earlier this
session depends on — same plaintext, different ciphertext every time under
Fernet, so a DB-level unique constraint on the encrypted column alone would
never fire again.

Ordering matters here: din_hash must be backfilled with real, distinct
values for every existing row BEFORE the new (company, din_hash) uniqueness
constraint is added — adding the constraint first would immediately fail
against any company with 2+ existing directors, since they'd all still
have an equal (blank) din_hash at that point.
"""
import core.encrypted_fields
from django.db import migrations, models


def encrypt_and_hash_existing_dins(apps, schema_editor):
    """One-pass, idempotent backfill — same convention as
    0064_encrypt_sensitive_pii / 0121_encrypt_company_pii. Also computes
    din_hash explicitly since the historical model used inside a migration
    doesn't carry CompanyDirector's real save() override."""
    from core.encrypted_fields import blind_index

    CompanyDirector = apps.get_model('accounts', 'CompanyDirector')
    for director in CompanyDirector.objects.all().iterator():
        director.din_hash = blind_index(director.din) if director.din else ''
        director.save(update_fields=['din', 'din_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0122_grant_all_permissions_to_system_admin'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='companydirector',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='companydirector',
            name='din_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AlterField(
            model_name='companydirector',
            name='din',
            field=core.encrypted_fields.EncryptedCharField(max_length=255),
        ),
        migrations.RunPython(encrypt_and_hash_existing_dins, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='companydirector',
            unique_together={('company', 'din_hash')},
        ),
    ]
