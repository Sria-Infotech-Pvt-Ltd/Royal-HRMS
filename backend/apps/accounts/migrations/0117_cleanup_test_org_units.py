"""
One-time cleanup: removes a "Founder -> Executive management -> Root" test
chain of org units created directly on production while trying out the
"Add org unit" UI (not part of the real SRIA structure seeded in 0116).
This is exactly the situation OrgUnitDetailView.delete() is meant to allow
safely: every unit here is checked for children and placement history
(never blind — a name match alone isn't enough to justify deleting real
data), and anything that fails that check is left alone and logged rather
than silently forced through.
"""
from django.db import migrations


def cleanup_forward(apps, schema_editor):
    OrgUnit = apps.get_model('accounts', 'OrgUnit')
    Position = apps.get_model('accounts', 'Position')

    try:
        founder = OrgUnit.objects.get(name='Founder', parent=None)
    except OrgUnit.DoesNotExist:
        print('0117 cleanup: no root "Founder" unit found — nothing to do.')
        return

    exec_mgmt = OrgUnit.objects.filter(name='Executive management', parent=founder).first()
    root = (
        OrgUnit.objects.filter(name='Root', parent=exec_mgmt).first()
        if exec_mgmt else None
    )

    def safe_to_delete(unit):
        if unit.children.exists():
            return False
        return not Position.objects.filter(org_unit=unit, placements__isnull=False).exists()

    # Leaf-first: Root, then its parent Executive management, then Founder —
    # matches the same "no children, no placement history" rule
    # OrgUnitDetailView.delete() enforces for a real admin-initiated delete.
    for unit in [u for u in (root, exec_mgmt, founder) if u is not None]:
        unit.refresh_from_db()
        if safe_to_delete(unit):
            name = unit.name
            unit.delete()
            print(f'0117 cleanup: deleted test org unit "{name}".')
        else:
            print(f'0117 cleanup: skipped "{unit.name}" — has children or placement history, not auto-deleting.')


def cleanup_reverse(apps, schema_editor):
    # Deliberately not reversed — this deletes test data, not something a
    # rollback should try to recreate.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0116_seed_sria_org_structure'),
    ]

    operations = [
        migrations.RunPython(cleanup_forward, cleanup_reverse),
    ]
