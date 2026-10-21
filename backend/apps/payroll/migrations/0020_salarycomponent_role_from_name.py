"""
Fill SalaryComponent.role from the component name, using exactly the rule
payroll applied until now (_compute_employee_payslip compared name.lower()
with 'basic', 'hra' and 'special allowance'), so existing structures keep
calculating the same way. Everything else stays 'other'.
"""
from django.db import migrations

_ROLE_BY_NAME = {'basic': 'basic', 'hra': 'hra', 'special allowance': 'special_allowance'}


def forwards(apps, schema_editor):
    SalaryComponent = apps.get_model('payroll', 'SalaryComponent')
    for component in SalaryComponent.objects.all().only('id', 'name'):
        role = _ROLE_BY_NAME.get(component.name.lower())
        if role:
            SalaryComponent.objects.filter(pk=component.pk).update(role=role)


def backwards(apps, schema_editor):
    # The role column is dropped by reversing 0019; nothing else to undo.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0019_employee_salary_components'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
