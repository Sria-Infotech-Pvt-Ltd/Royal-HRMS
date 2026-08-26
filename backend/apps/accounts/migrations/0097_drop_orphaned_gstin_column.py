from django.db import migrations


class Migration(migrations.Migration):
    """
    Drops a `gstin` column that reappeared on `hrms_company` outside of this
    repo's migration history — some out-of-band process applied an unrecorded
    migration directly against the shared database after 0096 had already
    removed the field (see the "Company Profile Expansion" TEAMCONTEXT.md
    entry). Nothing in the current Company model references this column, so
    there is no model-state change here, only a raw column drop to bring the
    live schema back in sync with what 0096 already established. Confirmed
    the table is empty before writing this — no data at risk.
    """

    dependencies = [
        ('accounts', '0096_remove_company_gstin_company_bank_account_holder_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE hrms_company DROP COLUMN IF EXISTS gstin;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
