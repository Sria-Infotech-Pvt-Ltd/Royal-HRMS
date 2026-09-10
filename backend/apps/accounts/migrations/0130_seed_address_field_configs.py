# Seeds one OnboardingFieldConfig row per new address sub-field added in
# 0129 — same get_or_create pattern as 0077_seed_onboarding_field_configs.py
# (CLAUDE.md: data migrations use get_or_create, never bare create()).
#
# current_district/current_state/current_pin_code are required=True,
# matching current_address's own required/is_locked=True seed — a complete
# current address needs all three. current_village and every permanent_*
# field are required=False, matching permanent_address's own optional
# default; HR can turn any of these on/off later from Settings > Onboarding
# Fields exactly like any other non-locked field. None are is_locked=True so
# HR retains full control post-deploy.
#
# Ordered so each address's sub-fields sit right after its own address line
# (current_address=5, current_village=6..current_pin_code=9, then
# permanent_address moved to 10, permanent_village=11..permanent_pin_code=14)
# — the wizard's DynamicStepFields renders fields in raw `order` sequence,
# not bucketed by type, so leaving permanent_address at 0077's original
# order=6 would sit it between current_address and current_village. Moving
# an already-seeded row's order (permanent_address) is safe here only because
# this migration hasn't been applied/pushed anywhere yet (CLAUDE.md's "never
# edit an already-committed migration" doesn't apply pre-commit); HR can
# still drag any of these into a different order later from Settings.
from django.db import migrations

# Same 36 India states/UTs the frontend's `state` dropdown already used for
# Company addresses (frontend/app/dashboard/settings/company/_data.ts
# STATES) — duplicated here as a plain literal (matching that file's own
# convention) since this is a one-time DB seed, not a shared runtime import.
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

# (field_key, label, order, field_type, required)
STEP_0_ADDRESS_ADDITIONS = [
    ('current_village',    'Village / Town / Area', 6,  'text',     False),
    ('current_district',   'District',              7,  'text',     True),
    ('current_state',      'State',                 8,  'dropdown', True),
    ('current_pin_code',   'PIN Code',              9,  'text',     True),
    ('permanent_village',  'Village / Town / Area', 11, 'text',     False),
    ('permanent_district', 'District',              12, 'text',     False),
    ('permanent_state',    'State',                 13, 'dropdown', False),
    ('permanent_pin_code', 'PIN Code',              14, 'text',     False),
]


def seed_address_field_configs(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    for field_key, label, order, field_type, required in STEP_0_ADDRESS_ADDITIONS:
        OnboardingFieldConfig.objects.get_or_create(
            field_key=field_key,
            defaults={
                'label': label,
                'field_type': field_type,
                'options': STATES if field_type == 'dropdown' else [],
                'step': 0,
                'order': order,
                'visible': True,
                'required': required,
                'is_custom': False,
                'is_locked': False,
            },
        )

    # permanent_address was seeded by 0077 with order=6 (right after
    # current_address) — get_or_create above only sets `order` for rows it
    # newly creates, so this pre-existing row needs its own explicit update
    # to move it past current's new sub-fields (order 6-9) to order 10.
    OnboardingFieldConfig.objects.filter(field_key='permanent_address').update(order=10)

    # Historical models bypass the real model's signal receivers, so the
    # cache OnboardingFieldConfigCacheService keeps needs an explicit poke —
    # same pattern as 0090_fix_manager_role_can_manage_team.py's
    # ApprovalWorkflowCacheService.invalidate() call.
    try:
        from core.cache_service import OnboardingFieldConfigCacheService
        OnboardingFieldConfigCacheService.invalidate()
    except Exception:
        pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0129_employeeprofile_address_breakdown'),
    ]

    operations = [
        migrations.RunPython(seed_address_field_configs, noop_reverse),
    ]
