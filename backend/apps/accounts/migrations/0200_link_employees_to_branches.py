"""
Link employees to their branch where only the branch NAME text is set.

0133 did this once; employees created afterwards (hire wizard, bulk import, candidate conversion) only got the text,
so the Company Codes employee counts read 0 for them. Only fills a link that is missing, matching the name
case-insensitively; it never changes a link that is already set. Safe to run more than once.
"""
from django.db import migrations


def link_employees(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Branch = apps.get_model('branch', 'Branch')

    branches_by_name = {b.branch_name.strip().lower(): b.pk for b in Branch.objects.all()}
    linked = 0
    unmatched = {}
    for user in User.objects.filter(branch_fk__isnull=True).exclude(branch='').exclude(branch__isnull=True).iterator():
        branch_pk = branches_by_name.get(user.branch.strip().lower())
        if branch_pk is None:
            unmatched[user.branch] = unmatched.get(user.branch, 0) + 1
            continue
        User.objects.filter(pk=user.pk).update(branch_fk=branch_pk)
        linked += 1

    print(f'\n  Employees linked to their branch: {linked}.')
    for name, count in sorted(unmatched.items()):
        print(f'  {count} employee(s) have branch text {name!r}, which matches no branch (left unlinked).')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0199_employee_permissions'),
        ('branch', '0012_branch_attributes'),
    ]

    operations = [
        migrations.RunPython(link_employees, migrations.RunPython.noop),
    ]
