"""
Seeds 3 DocumentTypeConfig rows the Hire wizard's Documents step already
lists (Latest Payslips, Signed Offer Letter, Address Proof) but that were
never actually configured — uploads for these would have failed with
"Invalid document type." since HireActionDocumentListCreateView (and the
real EmployeeDocumentView it mirrors) both validate against this table, not
a `choices=` enum. Continues the order sequence from the last built-in row
(0..6 already seeded), same get_or_create pattern as every other
DocumentTypeConfig seed migration.
"""
from django.db import migrations

NEW_TYPES = [
    # (type_key, label, order)
    ('latest_payslips',    'Latest Payslips',     7),
    ('signed_offer_letter','Signed Offer Letter', 8),
    ('address_proof',      'Address Proof',       9),
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
                'required': False,
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
        ('accounts', '0163_hireactiondocument'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
