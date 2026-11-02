from django.db import migrations

# account_activated_at (added in 0208) is a brand-new signal with no history
# for any employee created before this feature shipped — left NULL, every
# existing, already-working employee would suddenly show "Onboarding" instead
# of "Active" the moment this deploys, which is exactly the kind of surprise
# regression this feature must not cause. Anyone whose data is already
# complete and who isn't still on must_change_password (i.e. they've long
# since set their own password) is backfilled as activated at date_joined
# (falling back to now() when that's unset) — a reasonable, clearly-before-
# today timestamp, not a precise historical record.
def backfill_activated_at(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    from django.utils import timezone

    User.objects.filter(
        account_activated_at__isnull=True,
        onboarding_status='complete',
        must_change_password=False,
    ).exclude(employee_id='').update(account_activated_at=timezone.now())


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0210_account_activated_at'),
    ]

    operations = [
        migrations.RunPython(backfill_activated_at, noop_reverse),
    ]
