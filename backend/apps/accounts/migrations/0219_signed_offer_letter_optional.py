"""
Signed Offer Letter was marked required (0170_fix_required_document_types)
alongside Cancelled Cheque. In practice this has been blocking/confusing
HR during onboarding review for candidates who haven't (or can't) upload
a signed copy yet -- making it optional again, same as it was before 0170.
Cancelled Cheque is untouched.
"""
from django.db import migrations


def make_optional(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(type_key='signed_offer_letter').update(required=False)

    try:
        from core.cache_service import DocumentTypeConfigCacheService
        DocumentTypeConfigCacheService.invalidate()
    except Exception:
        pass


def make_required(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(type_key='signed_offer_letter').update(required=True)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0218_employee_import_job'),
    ]

    operations = [
        migrations.RunPython(make_optional, make_required),
    ]
