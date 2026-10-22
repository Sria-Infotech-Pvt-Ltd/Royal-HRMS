"""The migration that removes Roles (accounts 0195) must not take anyone's access away.

Runs the real migrations: goes back to the state just before, builds users/roles/seats with the OLD models, migrates
forward and checks what each kind of person ended up with.
"""
from __future__ import annotations

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [('accounts', '0194_approval_rule_approver_kinds'), ('platform_core', '0021_add_position_links')]
AFTER = [('accounts', '0196_remove_roles'), ('platform_core', '0022_remove_role_links')]


class RolesRemovalMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        self.old = executor.loader.project_state(BEFORE).apps
        self._build_old_world()
        executor = MigrationExecutor(connection)
        executor.migrate(AFTER)
        self.new = executor.loader.project_state(AFTER).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _build_old_world(self):
        Role = self.old.get_model('accounts', 'Role')
        RolePermission = self.old.get_model('accounts', 'RolePermission')
        Permission = self.old.get_model('accounts', 'Permission')
        User = self.old.get_model('accounts', 'User')
        OrgUnit = self.old.get_model('accounts', 'OrgUnit')
        Position = self.old.get_model('accounts', 'Position')
        Placement = self.old.get_model('accounts', 'Placement')

        def permission(codename):
            module, _, action = codename.partition('.')
            return Permission.objects.get_or_create(codename=codename, defaults={'module': module, 'action': action})[0]

        def role(name, codenames=(), **attrs):
            instance, _ = Role.objects.get_or_create(name=name, defaults={'display_name': name, **attrs})
            for codename in codenames:
                RolePermission.objects.get_or_create(role=instance, permission=permission(codename))
            return instance

        def user(email, employee_id, role_obj, **extra):
            return User.objects.create(email=email, full_name=email.split('@')[0], employee_id=employee_id, role=role_obj, **extra)

        Role.objects.filter(is_default_employee_role=True).update(is_default_employee_role=False)
        employee_role = role('mig_employee', ['mig.self_service'], is_default_employee_role=True)
        hr_role = role('mig_hr', ['mig.hr_tool', 'mig.self_service'], can_manage_team=True)
        admin_role = role('mig_admin', ['mig.admin_tool'], is_full_access=True)
        payroll_exempt_role = role('mig_service', [], exclude_from_payroll=True)

        unit = OrgUnit.objects.create(name='Migration Unit')
        self.seat = Position.objects.create(org_unit=unit, title='HR Partner', grade='L3')
        self.seated_hr = user('seated-hr@mig.test', 'MIG1', hr_role)
        Placement.objects.create(position=self.seat, employee=self.seated_hr, effective_from=date(2020, 1, 1))

        self.unseated_hr = user('unseated-hr@mig.test', 'MIG2', hr_role)
        self.unseated_admin = user('unseated-admin@mig.test', 'MIG3', admin_role)
        self.plain = user('plain@mig.test', 'MIG4', employee_role)
        self.service = user('service@mig.test', 'MIG5', payroll_exempt_role)

    def test_baseline_comes_from_the_default_employee_role(self):
        Baseline = self.new.get_model('accounts', 'BaselinePermission')
        self.assertIn('mig.self_service', set(Baseline.objects.values_list('permission__codename', flat=True)))

    def test_seat_holders_seat_gets_their_roles_extra_permissions_and_flags(self):
        PositionPermission = self.new.get_model('accounts', 'PositionPermission')
        Position = self.new.get_model('accounts', 'Position')
        codenames = set(PositionPermission.objects.filter(position_id=self.seat.pk).values_list('permission__codename', flat=True))
        self.assertEqual(codenames, {'mig.hr_tool'})  # baseline permissions are not copied onto the seat
        self.assertTrue(Position.objects.get(pk=self.seat.pk).can_manage_team)

    def test_unseated_full_access_person_becomes_super_admin(self):
        User = self.new.get_model('accounts', 'User')
        self.assertTrue(User.objects.get(email='unseated-admin@mig.test').is_superuser)

    def test_unseated_person_with_extra_access_gets_a_visible_legacy_seat(self):
        User = self.new.get_model('accounts', 'User')
        PositionPermission = self.new.get_model('accounts', 'PositionPermission')
        Placement = self.new.get_model('accounts', 'Placement')
        person = User.objects.get(email='unseated-hr@mig.test')
        seat = Placement.objects.get(employee=person).position
        self.assertEqual(seat.org_unit.name, 'Legacy access (review)')
        self.assertTrue(seat.can_manage_team)
        self.assertEqual(
            set(PositionPermission.objects.filter(position=seat).values_list('permission__codename', flat=True)), {'mig.hr_tool'},
        )

    def test_unseated_service_account_keeps_its_payroll_exclusion(self):
        User = self.new.get_model('accounts', 'User')
        Placement = self.new.get_model('accounts', 'Placement')
        seat = Placement.objects.get(employee=User.objects.get(email='service@mig.test')).position
        self.assertTrue(seat.exclude_from_payroll)

    def test_plain_employee_needs_nothing_extra(self):
        User = self.new.get_model('accounts', 'User')
        Placement = self.new.get_model('accounts', 'Placement')
        person = User.objects.get(email='plain@mig.test')
        self.assertFalse(person.is_superuser)
        self.assertFalse(Placement.objects.filter(employee=person).exists())

    def test_the_role_tables_and_columns_are_gone(self):
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            columns = [column.name for column in connection.introspection.get_table_description(cursor, 'hrms_users')]
        self.assertNotIn('hrms_roles', tables)
        self.assertNotIn('hrms_role_permissions', tables)
        self.assertNotIn('role_id', columns)
