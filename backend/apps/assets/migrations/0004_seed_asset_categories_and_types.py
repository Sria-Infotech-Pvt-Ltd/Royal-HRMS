from django.db import migrations

# name -> ordered list of default Asset Type names for that category.
# "Other" is seeded once per category (not a single global row) since
# AssetType.category is a required FK — this keeps every visible type
# option genuinely belonging to its category for the cascading dropdown,
# rather than special-casing a category-less "Other" type.
CATEGORIES_AND_TYPES = {
    'IT Equipment': [
        'Laptop', 'Desktop', 'Monitor', 'Keyboard', 'Mouse', 'Headset',
        'Printer', 'Scanner', 'Router', 'Server', 'Other',
    ],
    'Mobile Devices': ['Mobile Phone', 'Tablet', 'SIM Card', 'Other'],
    'Office Equipment': ['Projector', 'UPS', 'Biometric Device', 'Camera', 'Other'],
    'Furniture': ['Office Chair', 'Office Desk', 'Cabinet', 'Other'],
    'Access & Security': ['ID Card', 'Access Card', 'Security Token', 'Other'],
    'Other': ['Other'],
}


def seed_forward(apps, schema_editor):
    AssetCategory = apps.get_model('assets', 'AssetCategory')
    AssetType = apps.get_model('assets', 'AssetType')

    for category_name, type_names in CATEGORIES_AND_TYPES.items():
        category, _ = AssetCategory.objects.get_or_create(
            name=category_name, defaults={'is_active': True},
        )
        for type_name in type_names:
            AssetType.objects.get_or_create(
                name=type_name, category=category, defaults={'is_active': True},
            )


def seed_reverse(apps, schema_editor):
    AssetCategory = apps.get_model('assets', 'AssetCategory')
    AssetType = apps.get_model('assets', 'AssetType')
    AssetType.objects.filter(category__name__in=CATEGORIES_AND_TYPES.keys()).delete()
    AssetCategory.objects.filter(name__in=CATEGORIES_AND_TYPES.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0003_assetcategory_asset_asset_type_other_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
