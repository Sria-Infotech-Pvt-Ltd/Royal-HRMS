"""
Cancelled Cheque is optional in the Hire wizard's Documents step.

0170_fix_required_document_types made Cancelled Cheque and Signed Offer Letter required; 0219_signed_offer_letter_optional
then made only the Signed Offer Letter optional again and left Cancelled Cheque required. HR now wants both optional, and
the screen shows a required document as a red asterisk, so the server's answer must match what the screen shows:
HireActionCompleteView and the onboarding submit read DocumentTypeConfig.required (through DocumentTypeConfigCacheService),
so this row has to change here, not only in the front end.

This only changes the one `required` flag on the existing row. Nothing else about the document type is touched, and a company
that has configured it differently since can set it back in Settings.
"""
from django.db import migrations


def _invalidate_cache() -> None:
    try:
        from core.cache_service import DocumentTypeConfigCacheService
        DocumentTypeConfigCacheService.invalidate()
    except Exception:  # noqa: BLE001 - the cache is an optimisation; the row itself is already updated
        pass


def make_optional(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(type_key='cancelled_cheque').update(required=False)
    _invalidate_cache()


def make_required(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(type_key='cancelled_cheque').update(required=True)
    _invalidate_cache()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0221_drop_obsolete_employee_code_series_columns'),
    ]

    operations = [
        migrations.RunPython(make_optional, make_required),
    ]
