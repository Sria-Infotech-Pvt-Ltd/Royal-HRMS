# Seeds the fixed set of show/require toggle rows for Education/Experience
# list-entry fields — see EducationExperienceFieldConfig's own docstring for
# why this is a narrower, fixed-row system rather than OnboardingFieldConfig's
# add-your-own-custom-field one. Level/Institution (education) and Employer
# Name/Designation (experience) are the structural minimum and intentionally
# have no row here — always shown, always required.
from django.db import migrations

# (list_type, field_key, label, order)
FIELDS = [
    ('education',  'specialization',     'Specialization',        0),
    ('education',  'percentage',         'Percentage / Grade',     1),
    ('education',  'start_date',         'Start Date',             2),
    ('education',  'end_date',           'End Date',               3),
    ('experience', 'employment_type',    'Employment Type',        0),
    ('experience', 'start_date',         'Start Date',             1),
    ('experience', 'end_date',           'End Date',                2),
    ('experience', 'responsibilities',   'Key Responsibilities',   3),
    ('experience', 'reason_for_leaving', 'Reason for Leaving',     4),
]


def seed(apps, schema_editor):
    EducationExperienceFieldConfig = apps.get_model('accounts', 'EducationExperienceFieldConfig')
    for list_type, field_key, label, order in FIELDS:
        EducationExperienceFieldConfig.objects.get_or_create(
            list_type=list_type, field_key=field_key,
            defaults={'label': label, 'order': order, 'visible': True, 'required': False},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0146_education_experience_field_config'),
    ]

    operations = [
        migrations.RunPython(seed, noop_reverse),
    ]
