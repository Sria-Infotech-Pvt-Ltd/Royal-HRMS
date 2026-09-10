# Seeds OnboardingFieldConfig rows for current_address_line2/
# permanent_address_line2 (0144's new model columns) — optional second
# address line (apartment/floor/landmark), placed right after its own
# Address Line 1 so DynamicStepFields.tsx's addressPair pairing (line1
# immediately followed by line2 in `order`) renders them side by side in
# one half-width row instead of each getting its own full-width row.
#
# Existing rows from current_village (order 6) through permanent_pin_code
# (order 14) all shift up by 2 to make room for the two new line2 rows —
# safe to reorder here since nothing in this feature has been deployed yet.
from django.db import migrations

NEW_ROWS = [
    ('current_address_line2',   'Address Line 2', 6,  'text', False),
    ('permanent_address_line2', 'Address Line 2', 12, 'text', False),
]

# (field_key, new_order) — every row from current_village onward, shifted.
REORDERED = [
    ('current_village',    7),
    ('current_district',   8),
    ('current_state',      9),
    ('current_pin_code',   10),
    ('permanent_address',  11),
    ('permanent_village',  13),
    ('permanent_district', 14),
    ('permanent_state',    15),
    ('permanent_pin_code', 16),
]


def seed(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')

    for field_key, new_order in REORDERED:
        OnboardingFieldConfig.objects.filter(field_key=field_key).update(order=new_order)

    for field_key, label, order, field_type, required in NEW_ROWS:
        OnboardingFieldConfig.objects.get_or_create(
            field_key=field_key,
            defaults={
                'label': label,
                'field_type': field_type,
                'options': [],
                'step': 0,
                'order': order,
                'visible': True,
                'required': required,
                'is_custom': False,
                'is_locked': False,
            },
        )

    try:
        from core.cache_service import OnboardingFieldConfigCacheService
        OnboardingFieldConfigCacheService.invalidate()
    except Exception:
        pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0144_add_address_line2'),
    ]

    operations = [
        migrations.RunPython(seed, noop_reverse),
    ]
