from django.db import migrations, models


def seed_allowance_catalogue(apps, schema_editor):
    PayComponent = apps.get_model('payroll', 'PayComponent')
    allowances = [
        ('ALW_DA', 'Dearness Allowance'),
        ('ALW_HRA', 'House Rent Allowance'),
        ('ALW_CONVEYANCE', 'Conveyance Allowance'),
        ('ALW_MEDICAL', 'Medical Allowance'),
        ('ALW_LTA', 'Leave Travel Allowance'),
        ('ALW_SPECIAL', 'Special Allowance'),
    ]
    for index, (code, name) in enumerate(allowances, start=1):
        component, _ = PayComponent.objects.get_or_create(
            code=code,
            defaults={
                'name': name,
                'payslip_label': name,
                'category': 'earning',
                'calculation_method': 'input',
                'is_taxable': True,
                'display_order': index * 10,
                'payslip_group': 'Earnings',
                'status': 'published',
                'is_active': True,
            },
        )
        component.is_company_allowance = True
        component.save(update_fields=['is_company_allowance'])


def remove_seeded_allowances(apps, schema_editor):
    PayComponent = apps.get_model('payroll', 'PayComponent')
    PayComponent.objects.filter(code__in=[
        'ALW_DA', 'ALW_HRA', 'ALW_CONVEYANCE', 'ALW_MEDICAL', 'ALW_LTA', 'ALW_SPECIAL',
    ]).update(is_company_allowance=False)


class Migration(migrations.Migration):
    dependencies = [
        ('payroll', '0036_merge_20261013_1055'),
    ]

    operations = [
        migrations.AddField(
            model_name='paycomponent',
            name='is_company_allowance',
            field=models.BooleanField(
                default=False,
                help_text='Company-managed allowance available for selection in legacy salary structures.',
            ),
        ),
        migrations.RunPython(seed_allowance_catalogue, remove_seeded_allowances),
    ]
