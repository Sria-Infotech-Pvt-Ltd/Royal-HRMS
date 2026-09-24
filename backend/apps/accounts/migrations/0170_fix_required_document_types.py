"""
The Hire wizard's Documents step (DOC_ITEMS in DocumentsChecklistStep.tsx)
has always labeled Cancelled Cheque and Signed Offer Letter "Required", but
the actual DocumentTypeConfig rows backing them were seeded required=False
— so the real, server-side "is this document required" answer disagreed
with what HR was shown on screen. HireActionCompleteView now enforces
required documents server-side (reads DocumentTypeConfig directly, not the
frontend's own copy of which types are required), so this had to be fixed
here first — otherwise the server-side gate would have silently accepted
hires missing documents the UI called required.
"""
from django.db import migrations


def set_required(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(
        type_key__in=['cancelled_cheque', 'signed_offer_letter'],
    ).update(required=True)

    try:
        from core.cache_service import DocumentTypeConfigCacheService
        DocumentTypeConfigCacheService.invalidate()
    except Exception:
        pass


def unset_required(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(
        type_key__in=['cancelled_cheque', 'signed_offer_letter'],
    ).update(required=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0169_employeeprofile_certifications_and_more'),
    ]

    operations = [
        migrations.RunPython(set_required, unset_required),
    ]
