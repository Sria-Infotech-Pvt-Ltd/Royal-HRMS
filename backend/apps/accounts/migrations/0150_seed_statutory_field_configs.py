"""
Seeds one OnboardingFieldConfig row per new statutory/personal field added in
0149 — same get_or_create pattern as 0077_seed_onboarding_field_configs.py /
0130_seed_address_field_configs.py (CLAUDE.md: data migrations use
get_or_create, never bare create()).

All seeded required=False — none of these are structural minimums the way
current_address/highest_qualification are; they're optional declarations
(disability, international worker) or numbers an existing employee may not
have on hand yet. HR can flip any of these to required later from Settings >
Onboarding Fields exactly like any other non-locked field.

Step 0 (Personal) already ends at order=14 (permanent_pin_code, seeded by
0130) — these continue from order=15. Step 2 (Bank Details) already ends at
order=5 (bank_branch_name, seeded by 0077) — PF/ESI coverage flags continue
from order=6 there, since they're statutory/payroll-adjacent rather than
personal-identity fields.
"""
from django.db import migrations

DISABILITY_TYPES = ['Visual', 'Hearing', 'Locomotor', 'Intellectual', 'Multiple', 'Other']

# (field_key, label, order, field_type, options)
STEP_0_ADDITIONS = [
    ('aadhaar_number',               'Aadhaar Number',            15, 'text',     []),
    ('is_disabled',                  'Specially Abled',           16, 'checkbox', []),
    ('disability_type',              'Disability Type',           17, 'dropdown', DISABILITY_TYPES),
    ('disability_percentage',        'Disability %',              18, 'number',   []),
    ('disability_certificate_number','Disability Certificate No.',19, 'text',     []),
    ('is_international_worker',      'International Worker',      20, 'checkbox', []),
    ('international_worker_country', 'Country of Origin',         21, 'text',     []),
    ('passport_number',              'Passport Number',           22, 'text',     []),
    ('passport_expiry',              'Passport Expiry',           23, 'date',     []),
]

STEP_2_ADDITIONS = [
    ('pf_covered',  'Covered Under PF',  6, 'checkbox', []),
    ('pf_number',   'PF Number',         7, 'text',     []),
    ('esi_covered', 'Covered Under ESI', 8, 'checkbox', []),
]


def seed_forward(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')

    def seed(step, fields):
        for field_key, label, order, field_type, options in fields:
            OnboardingFieldConfig.objects.get_or_create(
                field_key=field_key,
                defaults={
                    'label': label,
                    'field_type': field_type,
                    'options': options,
                    'step': step,
                    'order': order,
                    'visible': True,
                    'required': False,
                    'is_custom': False,
                    'is_locked': False,
                },
            )

    seed(0, STEP_0_ADDITIONS)
    seed(2, STEP_2_ADDITIONS)

    try:
        from core.cache_service import OnboardingFieldConfigCacheService
        OnboardingFieldConfigCacheService.invalidate()
    except Exception:
        pass


def seed_reverse(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    keys = [f[0] for f in STEP_0_ADDITIONS + STEP_2_ADDITIONS]
    OnboardingFieldConfig.objects.filter(field_key__in=keys).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0149_employeeprofile_statutory_fields'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
