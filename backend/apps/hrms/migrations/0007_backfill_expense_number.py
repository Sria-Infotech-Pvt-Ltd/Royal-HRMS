from django.db import migrations


def backfill_expense_number(apps, schema_editor):
    Expense = apps.get_model('hrms', 'Expense')
    expenses = Expense.objects.filter(expense_number__isnull=True).order_by('created_at')
    if not expenses.exists():
        return
    max_num = Expense.objects.filter(expense_number__isnull=False).aggregate(
        m=__import__('django.db.models', fromlist=['Max']).Max('expense_number')
    )['m'] or 0
    for i, expense in enumerate(expenses, start=max_num + 1):
        expense.expense_number = i
        expense.save(update_fields=['expense_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0006_expense_number'),
    ]

    operations = [
        migrations.RunPython(backfill_expense_number, migrations.RunPython.noop),
    ]
