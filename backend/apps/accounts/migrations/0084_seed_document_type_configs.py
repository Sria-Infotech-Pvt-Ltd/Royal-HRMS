"""
Seeds one DocumentTypeConfig row per existing hardcoded document type,
matching the values EmployeeDocument.TYPE_CHOICES used to enforce via a
`choices=` enum (removed in the previous migration) — so no company's
Documents step behavior changes on deploy, with one deliberate exception.

required flags here reflect what the backend actually enforced before this
feature (PAN Card, Aadhaar Card, Degree Certificate unconditionally; nothing
else) — NOT what the frontend's static list in
frontend/app/dashboard/employees/_data.ts claimed (which marked Passport
Photo and Cancelled Cheque as required, despite the backend never checking
either). This is a pre-existing frontend/backend inconsistency being fixed
by making the backend the single source of truth, same as how migration
0077 fixed a similar year_of_passing inconsistency rather than replicating
it.

Experience Letter was previously required ONLY when the profile showed
prior work experience (a conditional check duplicated three times in
views.py, now removed entirely in favor of one static required flag per
company). Seeded here as required=False — HR can flip it to required
themselves if their company wants everyone to provide one.
"""
from django.db import migrations

# (type_key, label, order, required)
DOCUMENT_TYPES = [
    ('pan_card',           'PAN Card',            0, True),
    ('aadhaar_card',       'Aadhaar Card',        1, True),
    ('degree_certificate', 'Degree Certificate',  2, True),
    ('experience_letter',  'Experience Letter',   3, False),
    ('passport_photo',     'Passport Photo',      4, False),
    ('cancelled_cheque',   'Cancelled Cheque',    5, False),
    ('other',              'Other',               6, False),
]


def seed_document_type_configs(apps, schema_editor):
    DocumentTypeConfig = apps.get_model('accounts', 'DocumentTypeConfig')
    for type_key, label, order, required in DOCUMENT_TYPES:
        DocumentTypeConfig.objects.get_or_create(
            type_key=type_key,
            defaults={
                'label': label,
                'order': order,
                'visible': True,
                'required': required,
                'allow_multiple': False,
                'is_custom': False,
                'is_locked': False,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0083_documenttypeconfig_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_document_type_configs, noop_reverse),
    ]
