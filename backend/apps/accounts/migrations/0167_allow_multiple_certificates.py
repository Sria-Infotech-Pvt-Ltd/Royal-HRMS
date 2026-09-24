"""
Allows more than one Degree Certificate / Experience Letter per employee —
someone with two degrees or two previous employers legitimately has two
separate certificate files, not one shared slot. Previously a re-upload of
either type silently replaced whatever was there before. Only these two
types change; every other type (PAN, Aadhaar, Passport, etc.) stays a single
slot as before.
"""
from django.db import migrations


def set_allow_multiple(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(
        type_key__in=['degree_certificate', 'experience_letter'],
    ).update(allow_multiple=True)

    try:
        from core.cache_service import DocumentTypeConfigCacheService
        DocumentTypeConfigCacheService.invalidate()
    except Exception:
        pass


def unset_allow_multiple(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    DocumentTypeConfig.objects.filter(
        type_key__in=['degree_certificate', 'experience_letter'],
    ).update(allow_multiple=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0166_employeeprofile_passport_country_of_issue_and_more'),
    ]

    operations = [
        migrations.RunPython(set_allow_multiple, unset_allow_multiple),
    ]
