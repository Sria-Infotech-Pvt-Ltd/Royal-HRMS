"""
UAT-014 — the 2026 holiday calendar was empty (0 rows for any branch), so
every national/regional holiday showed as a missing punch needing
regularization instead of a holiday. Six 2026 holidays already exist in
some environments (added ad hoc through the Settings UI, not via a
migration, so they weren't guaranteed to exist everywhere) — this seeds
the complete list idempotently via get_or_create keyed on (date, name), so
re-running it is a no-op wherever those six already exist, and it fills in
the rest (including Republic Day, a mandatory national holiday that was
missing outright) for every branch currently in the system (Chennai/Tamil
Nadu, Pune/Maharashtra, Bengaluru/Karnataka, Kondapur/Telangana).

Dates verified against 2026 public holiday references at the time of this
migration (Republic Day and Independence Day are fixed by law; Holi,
Ugadi, Gudi Padwa, Pongal, Ganesh Chaturthi, Dussehra and Diwali follow
the lunar calendar and are sourced from published 2026 Indian holiday
calendars — re-verify against an official state gazette before relying on
this for payroll/attendance in production).
"""
from django.db import migrations


NATIONAL_HOLIDAYS = [
    # (date, name)
    ('2026-01-26', 'Republic Day'),
    ('2026-03-04', 'Holi'),
]

# (date, name, branch_name) — branch_name resolves to that Branch; the
# holiday only applies there, mirroring Holiday.branch's "null = company-
# wide" convention for the national list above.
REGIONAL_HOLIDAYS = [
    ('2026-01-14', 'Pongal', 'Chennai Office'),
    ('2026-03-19', 'Ugadi', 'Bengaluru Office'),
    ('2026-03-19', 'Ugadi', 'Kondapur Office'),
    ('2026-03-19', 'Gudi Padwa', 'Pune Office'),
]


def seed_2026_holidays(apps, schema_editor):
    Holiday = apps.get_model('hrms', 'Holiday')
    Branch = apps.get_model('branch', 'Branch')

    for date, name in NATIONAL_HOLIDAYS:
        Holiday.objects.get_or_create(
            date=date, name=name,
            defaults={'holiday_type': 'national', 'branch': None},
        )

    for date, name, branch_name in REGIONAL_HOLIDAYS:
        branch = Branch.objects.filter(branch_name=branch_name).first()
        if not branch:
            continue
        Holiday.objects.get_or_create(
            date=date, name=name, branch=branch,
            defaults={'holiday_type': 'regional'},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0046_parental_leave_gender_eligibility'),
        ('branch', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_2026_holidays, noop_reverse),
    ]
