"""
Seeds one OnboardingFieldConfig row per existing onboarding wizard field,
matching the values the (now-deleted) hardcoded _STEP_REQUIRED_FIELDS /
_STEP_ALL_FIELDS dicts in OnboardingView used to encode — so no company's
wizard behavior changes on deploy for any field EXCEPT year_of_passing (see
note below, an already-existing inconsistency this feature fixes rather than
preserves).

current_address, highest_qualification, and institution are seeded as
is_locked=True — sensible defaults for "the business always wants this
collected" that HR can't turn off. Adjust later via the settings screen if a
different starting set is wanted; nothing about is_locked is hardcoded
elsewhere, it's just this migration's seed data.

year_of_passing was required in OnboardingView._submit()'s hardcoded check
but NOT in _STEP_REQUIRED_FIELDS (the per-step save) or the frontend's own
STEP_REQUIRED — an existing three-way inconsistency (a user could fill
Step 2 without it, proceed through the rest of the wizard, and only get
blocked at final submit with no earlier warning). Seeded here as
required=True, matching the stricter of the two existing behaviors — the new
unified validator checks this consistently at every step from now on, so the
inconsistency itself is fixed rather than replicated.
"""
from django.db import migrations

# (field_key, label, order, required, is_locked)
STEP_0_PERSONAL = [
    ('date_of_birth',     'Date of Birth',      0, True,  False),
    ('gender',            'Gender',             1, True,  False),
    ('marital_status',    'Marital Status',     2, True,  False),
    ('father_name',       "Father's Name",      3, True,  False),
    ('blood_group',       'Blood Group',        4, False, False),
    ('current_address',   'Current Address',    5, True,  True),
    ('permanent_address', 'Permanent Address',  6, False, False),
]

STEP_1_EDUCATION = [
    ('highest_qualification', 'Highest Qualification',        0, True,  True),
    ('institution',           'Institution / University',     1, True,  True),
    ('specialization',        'Specialization',                2, False, False),
    ('year_of_passing',       'Year of Passing',               3, True,  False),
    ('total_experience_years','Total Experience (Years)',      4, False, False),
    ('previous_employer',     'Previous Employer',             5, False, False),
    ('previous_designation',  'Previous Designation',          6, False, False),
    ('leaving_reason',        'Reason for Leaving',            7, False, False),
]

STEP_2_BANK = [
    ('account_holder_name', 'Account Holder Name', 0, True, False),
    ('account_type',        'Account Type',         1, True, False),
    ('account_number',      'Account Number',       2, True, False),
    ('ifsc_code',            'IFSC Code',            3, True, False),
    ('bank_name',            'Bank Name',            4, True, False),
    ('bank_branch_name',     'Bank Branch Name',     5, True, False),
]

STEP_3_EMERGENCY = [
    ('emergency_name',         'Emergency Contact Name', 0, True,  False),
    ('emergency_relationship', 'Relationship',           1, True,  False),
    ('emergency_phone',        'Emergency Contact Phone',2, True,  False),
    ('emergency_email',        'Emergency Contact Email',3, False, False),
]

ALL_STEPS = [
    (0, STEP_0_PERSONAL),
    (1, STEP_1_EDUCATION),
    (2, STEP_2_BANK),
    (3, STEP_3_EMERGENCY),
]


def seed_onboarding_field_configs(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    for step, fields in ALL_STEPS:
        for field_key, label, order, required, is_locked in fields:
            OnboardingFieldConfig.objects.get_or_create(
                field_key=field_key,
                defaults={
                    'label': label,
                    'field_type': 'date' if field_key == 'date_of_birth' else 'text',
                    'step': step,
                    'order': order,
                    'visible': True,
                    'required': required,
                    'is_custom': False,
                    'is_locked': is_locked,
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0076_onboardingfieldconfig_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_onboarding_field_configs, noop_reverse),
    ]
