"""
Backfill User.branch_fk from the legacy User.branch string, matching against
Branch.branch_name case-insensitively (same __iexact convention already used
at every branch-scoped call site, e.g. CandidateListCreateView.get's
branch__branch_name__iexact).

Deliberately does NOT touch the old `branch` CharField or drop it — this is
step 1 of a multi-step migration (see User.branch_fk's own docstring in
models.py): every call site that filters/compares User.branch as a string
needs to move to branch_fk first, one at a time, before the old column can
safely go. Re-running this migration is safe/idempotent — it only ever
(re)assigns branch_fk from the current branch string, never touches
anything else.

Any User.branch value that doesn't match any real Branch.branch_name (a typo,
or a branch that's since been renamed/deleted) is left with branch_fk=None
and printed here so HR can correct the source data — silently dropping these
would be exactly the kind of data loss this migration exists to prevent.
"""
from django.db import migrations


def backfill_branch_fk(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Branch = apps.get_model('branch', 'Branch')

    branches_by_name = {b.branch_name.strip().lower(): b for b in Branch.objects.all()}

    matched = 0
    unmatched = []
    for user in User.objects.exclude(branch='').exclude(branch__isnull=True).iterator():
        branch = branches_by_name.get(user.branch.strip().lower())
        if branch:
            User.objects.filter(pk=user.pk).update(branch_fk=branch.pk)
            matched += 1
        else:
            unmatched.append((user.employee_id or str(user.pk), user.email, user.branch))

    print(f'\n  User.branch_fk backfill: {matched} matched to a real Branch.')
    if unmatched:
        print(f'  {len(unmatched)} user(s) have a branch string that matches NO real Branch '
              f'(typo, or a renamed/deleted branch) — branch_fk left NULL for these, '
              f'HR needs to correct the source data:')
        for employee_id, email, branch_str in unmatched:
            print(f'    - {employee_id} ({email}): branch={branch_str!r}')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0132_user_branch_fk'),
        ('branch', '0010_remove_branch_employees_count'),
    ]

    operations = [
        migrations.RunPython(backfill_branch_fk, noop_reverse),
    ]
