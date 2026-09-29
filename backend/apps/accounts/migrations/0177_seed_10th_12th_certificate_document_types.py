"""
Seeds 2 new DocumentTypeConfig rows for the Hire wizard's Documents step —
10th Certificate and 12th Certificate, both required — matching this
codebase's own original design brief for this step ("Education: highest
qualification certificate + marksheets, 10th and 12th certificates"),
which had only ever been implemented as a single "Degree Certificate"
requirement. required=True here (not just on the frontend's own DOC_ITEMS
copy) so HireActionCompleteView's server-side required-document gate
agrees with what the UI shows — same reasoning as
0170_fix_required_document_types.
"""
from django.db import migrations

NEW_TYPES = [
    # (type_key, label, order)
    ('tenth_certificate',  '10th Certificate', 10),
    ('twelfth_certificate', '12th Certificate', 11),
]


def seed_forward(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    for type_key, label, order in NEW_TYPES:
        DocumentTypeConfig.objects.get_or_create(
            type_key=type_key,
            defaults={
                'label': label,
                'order': order,
                'visible': True,
                'required': True,
                'allow_multiple': False,
                'is_custom': False,
                'is_locked': False,
            },
        )

    try:
        from core.cache_service import DocumentTypeConfigCacheService
        DocumentTypeConfigCacheService.invalidate()
    except Exception:
        pass


def seed_reverse(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    keys = [t[0] for t in NEW_TYPES]
    DocumentTypeConfig.objects.filter(type_key__in=keys).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0176_employee_document_verification'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
