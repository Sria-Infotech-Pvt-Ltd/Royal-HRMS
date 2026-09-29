"""
Seeds a StatutoryConfig row for Telangana with the real, public Professional
Tax slab table (Telangana Professional Tax Act, 1987 — unchanged rates as of
this migration). QA report #48 found the Hire wizard's salary preview always
showed Rs 0 Professional Tax regardless of gross salary; the root cause
wasn't a formula bug in compute_pt() (that logic is correct) — there were
simply ZERO StatutoryConfig rows in the database at all, for any state, so
pt_applicable defaulted to False everywhere. This seeds the one state the QA
report explicitly tested against; other states remain unconfigured until an
admin sets them up via Settings, same as before.
"""
from django.db import migrations


TELANGANA_PT_SLABS = [
    {'min': 0,     'max': 15000,  'amount': 0},
    {'min': 15001, 'max': 20000,  'amount': 150},
    {'min': 20001, 'max': None,   'amount': 200},
]


def seed_telangana_statutory_config(apps, schema_editor):
    State = apps.get_model('branch', 'State')
    StatutoryConfig = apps.get_model('payroll', 'StatutoryConfig')

    telangana = State.objects.filter(code='TG').first()
    if not telangana:
        return

    StatutoryConfig.objects.get_or_create(
        state=telangana,
        defaults={
            'pt_applicable': True,
            'pt_slabs': TELANGANA_PT_SLABS,
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0023_employeepayslip_income_tax'),
        ('branch', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_telangana_statutory_config, noop_reverse),
    ]
