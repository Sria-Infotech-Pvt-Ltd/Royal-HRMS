"""
Seed OnboardingSection rows for the 4 built-in onboarding steps (Personal
Information / Education & Experience / Bank Details / Emergency Contact),
so their tab label/icon become editable from Settings the same way an
HR-created custom section already is — a rename here only ever changes the
Settings-page tab label, not the OnboardingFieldConfig.step values (0-3)
those built-in fields still key off, and not the separate hardcoded labels
the two onboarding wizards render (self-service + HR-on-behalf) — those
still show the original names. Deleting one of these rows is already
naturally blocked by OnboardingSectionDetailView.delete() (every built-in
step always has OnboardingFieldConfig rows under it), so no extra
protection flag is needed here.
"""
from django.db import migrations

_BUILTIN_SECTIONS = [
    {'step': 0, 'label': 'Personal Information',      'icon': 'ti-user',          'order': 0},
    {'step': 1, 'label': 'Education & Experience',    'icon': 'ti-school',        'order': 1},
    {'step': 2, 'label': 'Bank Details',               'icon': 'ti-building-bank', 'order': 2},
    {'step': 3, 'label': 'Emergency Contact',          'icon': 'ti-phone',         'order': 3},
]


def seed_sections(apps, schema_editor):
    OnboardingSection = apps.get_model('accounts', 'OnboardingSection')
    for s in _BUILTIN_SECTIONS:
        OnboardingSection.objects.get_or_create(
            step=s['step'],
            defaults={'label': s['label'], 'icon': s['icon'], 'order': s['order']},
        )


def remove_sections(apps, schema_editor):
    OnboardingSection = apps.get_model('accounts', 'OnboardingSection')
    OnboardingSection.objects.filter(step__in=[s['step'] for s in _BUILTIN_SECTIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0138_add_onboarding_section'),
    ]

    operations = [
        migrations.RunPython(seed_sections, remove_sections),
    ]
