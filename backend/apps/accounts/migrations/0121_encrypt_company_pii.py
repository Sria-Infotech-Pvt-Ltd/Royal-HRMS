"""
Encrypt Company's own PAN, bank account number/IFSC, and signatory DIN/PAN
at rest — the same PII tier already encrypted on the employee side
(EmployeeProfile.pan_number, BankDetail.account_number/ifsc_code, see
0064_encrypt_sensitive_pii and core/encrypted_fields.py), left as plain
CharField here since Company was added after 0064 and never got the same
treatment. No blind-index hash is added for any of these — Company is a
singleton table (one row ever, per the model's own docstring), so unlike
EmployeeProfile.pan_number there's no cross-row uniqueness or exact-match
lookup to preserve.

CompanyDirector.din is NOT touched here even though it can hold a
Partnership/Trust partner's PAN (see its own docstring) — it carries a real
DB-level `unique_together = [('company', 'din')]` constraint this session
depends on for live duplicate-DIN detection (409 Conflict), and Fernet
encryption is non-deterministic (same plaintext encrypts differently each
time), which would silently defeat that constraint. Encrypting it safely
needs a blind-index hash column plus reworking the uniqueness check to use
it instead, the same way pan_number_hash does for EmployeeProfile — a
separate, deliberate follow-up, not bundled into this migration.
"""
import core.encrypted_fields
from django.db import migrations


def encrypt_existing_company_pii(apps, schema_editor):
    """One-pass, idempotent backfill — reassigning each field to its own
    current value re-saves it through EncryptedCharField.get_prep_value,
    encrypting legacy plaintext for the first time. Re-running this simply
    re-encrypts with a fresh IV, not data loss (same convention as 0064)."""
    Company = apps.get_model('accounts', 'Company')
    for company in Company.objects.all().iterator():
        company.save(update_fields=['pan', 'bank_account_number', 'bank_ifsc', 'signatory_din_pan'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0120_fix_payroll_run_revoke_from_hr'),
    ]

    operations = [
        migrations.AlterField(
            model_name='company',
            name='pan',
            field=core.encrypted_fields.EncryptedCharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='company',
            name='bank_account_number',
            field=core.encrypted_fields.EncryptedCharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='company',
            name='bank_ifsc',
            field=core.encrypted_fields.EncryptedCharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='company',
            name='signatory_din_pan',
            field=core.encrypted_fields.EncryptedCharField(blank=True, max_length=255),
        ),
        migrations.RunPython(encrypt_existing_company_pii, migrations.RunPython.noop),
    ]
