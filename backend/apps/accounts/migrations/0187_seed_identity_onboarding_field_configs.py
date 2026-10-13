"""
Adds nationality/place_of_birth as real, seeded OnboardingFieldConfig rows
for step 0 (Personal) — these are real existing EmployeeProfile columns
(migration 0021) that were never exposed to the self-service onboarding
wizard before (see 0077_seed_onboarding_field_configs' STEP_0_PERSONAL
list, which predates this). Needed to match the Hire wizard's own Personal
identity step, which already collects both.

salutation/display_name are NOT seeded here — those render from a new,
self-service-specific hardcoded "Identity" header (same fields Hire's own
step 0 hardcodes, not admin-configurable there either), not through the
generic per-company field config system this migration seeds into.

nationality is required (matches the Hire wizard's own red-asterisk on this
field); place_of_birth is optional, same as Hire. Inserted right after
blood_group (reading its CURRENT live order rather than a hardcoded
number) and every row ordered after it shifted by +2 to make room —
DynamicStepFields.buildRuns pairs current_address/current_address_line2
into one row only when they're genuinely ADJACENT in the final sorted
list, so a hardcoded insertion point risked silently breaking that pairing
if this deploy's order values had already drifted from the migration
0077 baseline (confirmed they had, in exactly this way, during manual
testing before this migration shipped).
"""
from django.db import migrations

NEW_FIELDS = [
    # (field_key, label, required)
    ('nationality',    'Nationality',    True),
    ('place_of_birth', 'Place of Birth', False),
]


def seed_forward(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')

    blood_group = OnboardingFieldConfig.objects.filter(field_key='blood_group', step=0).first()
    insert_after_order = blood_group.order if blood_group else 4

    # Shift every step-0 row after the insertion point up by 2 (room for
    # the 2 new fields), ordered descending so no two rows collide
    # mid-update even where live orders already have ties.
    to_shift = list(
        OnboardingFieldConfig.objects.filter(step=0, order__gt=insert_after_order).order_by('-order')
    )
    for row in to_shift:
        row.order = row.order + 2
        row.save(update_fields=['order'])

    for offset, (field_key, label, required) in enumerate(NEW_FIELDS, start=1):
        OnboardingFieldConfig.objects.get_or_create(
            field_key=field_key,
            defaults={
                'label': label, 'field_type': 'text', 'options': [],
                'step': 0, 'order': insert_after_order + offset, 'visible': True, 'required': required,
                'is_custom': False, 'is_locked': False,
            },
        )

    # OnboardingFieldConfigPublicView reads through a cache (core.cache_service
    # .OnboardingFieldConfigCacheService) that every admin-facing edit endpoint
    # already invalidates on write — a migration bypasses those endpoints
    # entirely, so without this the new rows above stay invisible to every
    # already-running process until the cache's own TTL happens to expire.
    from core.cache_service import OnboardingFieldConfigCacheService
    OnboardingFieldConfigCacheService.invalidate()


def seed_reverse(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    OnboardingFieldConfig.objects.filter(
        field_key__in=[f[0] for f in NEW_FIELDS], is_custom=False,
    ).delete()
    from core.cache_service import OnboardingFieldConfigCacheService
    OnboardingFieldConfigCacheService.invalidate()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0186_merge_20261013_1055'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
