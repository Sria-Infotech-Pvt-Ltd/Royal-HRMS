"""
Seeds write permissions for the new Org Structure feature (org units,
positions, chief/holder assignment) and a starter set of JobTemplate rows.

Read access reuses the existing org_chart.view codename (already granted to
every role by migration 0086) rather than minting a new one — the Org
Structure page replaces what's served at the same /dashboard/org-chart
route, so the same "everyone can view" permission carries over unchanged.

Write access (create/edit/delete units, positions, holder assignment) is
granted to whichever roles already hold departments.edit — piggybacking on
an existing, currently-real permission grant rather than matching role
names directly, since 0041's hardcoded role-name approach is already noted
elsewhere (0086's own docstring) to have drifted from the live data.
"""
from django.db import migrations

WRITE_PERMISSIONS = [
    ('org_structure', 'create', 'org_structure.create'),
    ('org_structure', 'edit',   'org_structure.edit'),
    ('org_structure', 'delete', 'org_structure.delete'),
]

JOB_TEMPLATES = [
    ('Managing Director',            'EXEC'),
    ('Practice / Function Head',     'M4'),
    ('Delivery Lead',                'M3'),
    ('SAP Architect',                'L5'),
    ('Senior Consultant',            'L4'),
    ('Consultant',                   'L3'),
    ('Recruiter',                    'L3'),
    ('Trainer',                      'L3'),
    ('Accountant',                   'L3'),
]


def seed_forward(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    JobTemplate    = apps.get_model('accounts', 'JobTemplate')

    perm_map = {}
    for module, action, codename in WRITE_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename, defaults={'module': module, 'action': action},
        )
        perm_map[codename] = perm

    dept_edit_role_ids = set(
        RolePermission.objects
        .filter(permission__codename='departments.edit')
        .values_list('role_id', flat=True)
    )
    for role_id in dept_edit_role_ids:
        for codename in perm_map:
            RolePermission.objects.get_or_create(role_id=role_id, permission=perm_map[codename])

    import uuid
    for name, band in JOB_TEMPLATES:
        JobTemplate.objects.get_or_create(name=name, defaults={'id': uuid.uuid4(), 'band': band})


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename__in=[p[2] for p in WRITE_PERMISSIONS]).delete()
    JobTemplate = apps.get_model('accounts', 'JobTemplate')
    JobTemplate.objects.filter(name__in=[n for n, _ in JOB_TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0100_jobtemplate_orgunit_position'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
