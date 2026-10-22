# Step 1 of removing roles: copy what roles allowed onto the org chart. Kept separate from the schema step
# (0196) because Postgres cannot ALTER a table in the same transaction that updated its rows.

from django.db import migrations


SEAT_FLAGS = ('can_manage_team', 'can_manage_branch', 'exclude_from_payroll', 'exclude_from_headcount')
LEGACY_UNIT_NAME = 'Legacy access (review)'


def move_role_access_to_the_org_chart(apps, schema_editor):
    """Nobody loses access when roles go away: what a role allowed is copied onto the org chart first.

    1. The default employee role's permissions become the company BASELINE (what every employee can do).
    2. Each current seat holder's role permissions (beyond the baseline) and scope flags are copied onto their SEAT,
       so whoever holds that seat later inherits them.
    3. People with a role but NO seat: a full-access role makes the person a super-admin; anyone with extra
       permissions or flags gets a clearly-named seat under "Legacy access (review)" so their access continues and
       an admin can place them properly in the org chart afterwards. Plain employees need nothing.
    Safe to re-run; nothing is ever removed here.
    """
    from datetime import date

    from django.db.models import Q

    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    Permission = apps.get_model('accounts', 'Permission')
    PositionPermission = apps.get_model('accounts', 'PositionPermission')
    BaselinePermission = apps.get_model('accounts', 'BaselinePermission')
    Placement = apps.get_model('accounts', 'Placement')
    Position = apps.get_model('accounts', 'Position')
    OrgUnit = apps.get_model('accounts', 'OrgUnit')
    User = apps.get_model('accounts', 'User')

    def role_codenames(role):
        codenames = set(RolePermission.objects.filter(role=role).values_list('permission__codename', flat=True))
        if role.is_full_access:
            codenames.add('settings.edit')
        return codenames

    def grant(position, codenames):
        for permission in Permission.objects.filter(codename__in=codenames):
            PositionPermission.objects.get_or_create(position=position, permission=permission)

    # 1. baseline
    baseline = set()
    default_role = Role.objects.filter(is_default_employee_role=True).first()
    if default_role is not None:
        baseline = role_codenames(default_role) - {'settings.edit'}
        for permission in Permission.objects.filter(codename__in=baseline):
            BaselinePermission.objects.get_or_create(permission=permission)
    baseline |= set(BaselinePermission.objects.values_list('permission__codename', flat=True))

    # 2. seats that are held today
    today = date.today()
    seated = set()
    placements = (
        Placement.objects.filter(effective_from__lte=today, position__is_active=True)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .select_related('position', 'employee__role')
    )
    for placement in placements:
        employee, seat = placement.employee, placement.position
        seated.add(employee.pk)
        role = employee.role
        if role is None:
            continue
        grant(seat, role_codenames(role) - baseline)
        changed = False
        for flag in SEAT_FLAGS:
            if getattr(role, flag) and not getattr(seat, flag):
                setattr(seat, flag, True)
                changed = True
        if changed:
            seat.save(update_fields=list(SEAT_FLAGS))

    # 3. people with a role but no seat
    legacy_unit = None
    for user in User.objects.filter(is_active=True, role__isnull=False, is_superuser=False).exclude(pk__in=seated).select_related('role'):
        role = user.role
        codenames = role_codenames(role) - baseline
        flags = {flag: getattr(role, flag) for flag in SEAT_FLAGS}
        if role.is_full_access or 'settings.edit' in codenames:
            user.is_superuser = True
            user.save(update_fields=['is_superuser'])
            print(f'  [roles] {user.employee_id or user.email}: full-access role "{role.name}" -> super-admin')
            codenames.discard('settings.edit')
        if not codenames and not any(flags.values()):
            continue
        if legacy_unit is None:
            legacy_unit, _ = OrgUnit.objects.get_or_create(name=LEGACY_UNIT_NAME)
        seat = Position.objects.create(
            org_unit=legacy_unit, title=f'{role.display_name} - {user.full_name}'[:150], grade='', **flags,
        )
        grant(seat, codenames)
        Placement.objects.create(position=seat, employee=user, effective_from=user.date_of_joining or today)
        print(f'  [roles] {user.employee_id or user.email}: no seat -> legacy seat "{seat.title}" ({len(codenames)} permissions)')


class Migration(migrations.Migration):

    dependencies = [
        # Data migrations elsewhere still grant permissions to roles; they must run before the roles are deleted.
        ("assessments", "0002_seed_permissions"),
        ("attendance", "0023_seed_face_registration_permission"),
        ("branch", "0003_branch_permissions"),
        ("hrms", "0002_seed_expense_permissions"),
        ("hrms", "0033_seed_hr_help_respond_permission"),
        ("payroll", "0021_seed_tax_declarations_approve_permission"),
        ("performance", "0002_seed_performance_manage_cycles_permission"),
        ("performance", "0005_seed_review_team_permission"),
        ("platform_core", "0019_seed_privacy_manage_dsr_permission"),
        ("platform_core", "0022_remove_role_links"),
        ("accounts", "0194_approval_rule_approver_kinds"),
    ]

    operations = [
        migrations.RunPython(move_role_access_to_the_org_chart, migrations.RunPython.noop),
    ]
