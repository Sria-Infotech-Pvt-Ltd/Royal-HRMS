"""
Migration 0077 seeded every built-in onboarding field as field_type='text'
except date_of_birth — accurate for most, but wrong for the fields that are
actually long-text (textarea) or numeric (number) inputs, and for the four
fields backed by a fixed backend choice set (gender, marital_status,
blood_group, account_type — EmployeeProfile.*_CHOICES). Since 0077 is
already applied/pushed, fixed here rather than editing it (CLAUDE.md: never
edit an already-committed migration).

The four choice fields are marked field_type='dropdown' with their real
values in `options` for accurate display on the settings page, but the
wizard's DynamicField renderer special-cases these four field_keys with
their own hardcoded value/label pairs rather than reading `options` — a
plain string list can't carry EmployeeProfile's value/label distinction
(e.g. stored value 'male' vs displayed label 'Male'), so a generic
value==label dropdown render would submit the wrong value to a backend
CHOICES field. Every other field (including any future built-in addition,
and all HR-created custom fields) goes through the fully generic path.
"""
from django.db import migrations

TEXTAREA_FIELDS = ['current_address', 'permanent_address', 'leaving_reason']
NUMBER_FIELDS = ['year_of_passing', 'total_experience_years']
CHOICE_FIELDS = {
    'gender':         ['male', 'female', 'other'],
    'marital_status': ['single', 'married', 'divorced', 'widowed'],
    'blood_group':    ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'],
    'account_type':   ['savings', 'current'],
}


def fix_field_types(apps, schema_editor):
    OnboardingFieldConfig = apps.get_model('accounts', 'OnboardingFieldConfig')
    OnboardingFieldConfig.objects.filter(field_key__in=TEXTAREA_FIELDS).update(field_type='textarea')
    OnboardingFieldConfig.objects.filter(field_key__in=NUMBER_FIELDS).update(field_type='number')
    for field_key, options in CHOICE_FIELDS.items():
        OnboardingFieldConfig.objects.filter(field_key=field_key).update(field_type='dropdown', options=options)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0077_seed_onboarding_field_configs'),
    ]

    operations = [
        migrations.RunPython(fix_field_types, noop_reverse),
    ]
