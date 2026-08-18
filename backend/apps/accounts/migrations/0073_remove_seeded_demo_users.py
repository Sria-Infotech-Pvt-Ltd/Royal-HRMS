"""
0003_seed_demo_users seeds 4 hardcoded accounts (one per role) with a
shared, never-rotated password ('Hrms@1234') — fine for the original
single-tenant demo/dev deployment it was written for, but it's part of
the standard migration chain every TENANT_APP replays, so every company
provisioned since multi-tenancy was introduced (see apps/tenants/services.py
provision_company) silently got the same 4 logins, including a
system_admin, with a publicly-guessable password baked into this file.

Removes those 4 specific accounts by email in every schema this migration
runs against — both new companies going forward (0003 still runs as part
of their migration replay, but this now runs after it in the same pass,
so the accounts never actually persist) and any company that already has
them (this tenant's own admin explicitly asked for existing occurrences to
be removed too, not just suppressed for new ones).

Deliberately does not touch 0003 itself (already-applied, already-committed
migration) or reverse-seed anything on rollback — there is nothing safe to
restore a real company's data to.

Deletes each account individually, catching ProtectedError per-account
rather than letting one company's real usage of a demo account (e.g. real
payslips/payroll cycles created under it) abort this migration outright —
that would permanently block every later migration for that company, not
just this one. A company that has genuinely started using one of these
logins for real work keeps that account; the fix here is "never seed these
into a NEW company" (which this migration guarantees, since brand new
schemas have no data yet to protect it), not "force-delete an account a
company already depends on".
"""
from django.db import migrations
from django.db.models.deletion import ProtectedError

DEMO_EMAILS = [
    'hradmin@royal.com',
    'sysadmin@royal.com',
    'manager@royal.com',
    'employee@royal.com',
]


def remove_demo_users(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for email in DEMO_EMAILS:
        try:
            User.objects.filter(email=email).delete()
        except ProtectedError:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0072_fix_audit_log_branch_column_cross_schema_guard'),
    ]

    operations = [
        migrations.RunPython(remove_demo_users, migrations.RunPython.noop),
    ]
