"""The default L1 / L2 approver permission templates: what they hold, and how they are synced (no database needed)."""
import re
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts import permissions_registry
from apps.accounts.models import Permission, PermissionTemplate
from apps.accounts.permissions_registry import DEFAULT_PERMISSION_TEMPLATES, sync_default_permission_templates

L1 = next(spec for spec in DEFAULT_PERMISSION_TEMPLATES if spec['name'] == 'L1 Approver')
L2 = next(spec for spec in DEFAULT_PERMISSION_TEMPLATES if spec['name'] == 'L2 Approver (HR)')
# Acting as an approver must never need any of these (edit / delete, pay, other people's sensitive data, settings).
FORBIDDEN = {
    'settings.edit', 'settings.view', 'payroll.view', 'payroll.edit', 'payroll.create', 'payroll.delete',
    'employees.edit', 'employees.create', 'employees.delete', 'employees.view_sensitive', 'employees.reset_password',
    'leave.edit', 'leave.delete', 'attendance.edit', 'attendance.delete', 'expenses.edit', 'expenses.delete',
}


class TemplateDefinitionTests(SimpleTestCase):
    def test_both_templates_exist_with_unique_names(self):
        names = [spec['name'] for spec in DEFAULT_PERMISSION_TEMPLATES]
        self.assertEqual(sorted(names), ['L1 Approver', 'L2 Approver (HR)'])
        self.assertEqual(len(names), len(set(names)))

    def test_every_codename_is_module_dot_action_and_listed_once(self):
        for spec in DEFAULT_PERMISSION_TEMPLATES:
            self.assertEqual(len(spec['permissions']), len(set(spec['permissions'])), spec['name'])
            for codename in spec['permissions']:
                self.assertRegex(codename, r'^[a-z_]+\.[a-z_]+$')

    def test_both_levels_can_approve_every_request_type(self):
        for spec in (L1, L2):
            for codename in ('leave.approve', 'expenses.approve', 'wfh.approve', 'attendance.create'):
                self.assertIn(codename, spec['permissions'], spec['name'])

    def test_only_l2_gets_the_timesheet_hr_fallback_permission(self):
        self.assertNotIn('timesheet.approve', L1['permissions'])
        self.assertIn('timesheet.approve', L2['permissions'])

    def test_l1_is_a_team_manager_and_l2_is_not(self):
        self.assertTrue(L1['can_manage_team'])
        self.assertFalse(L2['can_manage_team'])

    def test_neither_template_grants_more_than_an_approver_needs(self):
        for spec in DEFAULT_PERMISSION_TEMPLATES:
            self.assertEqual(set(spec['permissions']) & FORBIDDEN, set(), spec['name'])

    def test_l2_holds_everything_l1_does(self):
        self.assertTrue(set(L1['permissions']) <= set(L2['permissions']))

    def test_every_codename_is_a_permission_the_app_defines(self):
        # Either created by a migration / entity generator (the baseline set below) or defined in code.
        code_defined = {codename for codename, *_rest in permissions_registry.CODE_DEFINED_PERMISSIONS}
        seeded_by_migrations = {
            'employees.view', 'attendance.view', 'attendance.create', 'leave.approve', 'expenses.approve', 'wfh.approve',
        }
        for spec in DEFAULT_PERMISSION_TEMPLATES:
            self.assertTrue(set(spec['permissions']) <= code_defined | seeded_by_migrations, spec['name'])


class SyncTests(SimpleTestCase):
    def run_sync(self, existing: bool):
        template = mock.MagicMock()
        permissions = [mock.MagicMock(codename=codename) for codename in L1['permissions']]
        with mock.patch.object(PermissionTemplate, 'objects') as templates, mock.patch.object(Permission, 'objects') as perms:
            templates.get_or_create.return_value = (template, not existing)
            perms.filter.return_value = permissions
            result = sync_default_permission_templates()
        return result, template, templates

    def test_a_missing_template_is_created_and_gets_its_permissions(self):
        result, template, templates = self.run_sync(existing=False)
        self.assertEqual(result, {'created': 2, 'unchanged': 0})
        self.assertEqual(template.permissions.set.call_count, 2)
        names = [call.kwargs['name'] for call in templates.get_or_create.call_args_list]
        self.assertEqual(names, ['L1 Approver', 'L2 Approver (HR)'])

    def test_an_existing_template_is_never_changed(self):
        result, template, _templates = self.run_sync(existing=True)
        self.assertEqual(result, {'created': 0, 'unchanged': 2})
        template.permissions.set.assert_not_called()

    def test_a_template_is_created_with_its_scope_flag_and_never_branch_wide(self):
        _result, _template, templates = self.run_sync(existing=False)
        defaults = {call.kwargs['name']: call.kwargs['defaults'] for call in templates.get_or_create.call_args_list}
        self.assertTrue(defaults['L1 Approver']['can_manage_team'])
        self.assertFalse(defaults['L2 Approver (HR)']['can_manage_team'])
        self.assertTrue(all(value['can_manage_branch'] is False for value in defaults.values()))

    def test_a_codename_that_does_not_exist_yet_is_reported_not_fatal(self):
        template = mock.MagicMock()
        with mock.patch.object(PermissionTemplate, 'objects') as templates, mock.patch.object(Permission, 'objects') as perms, \
                self.assertLogs('apps.accounts.permissions_registry', level='WARNING') as logs:
            templates.get_or_create.return_value = (template, True)
            perms.filter.return_value = [mock.MagicMock(codename='leave.approve')]
            result = sync_default_permission_templates()
        self.assertEqual(result['created'], 2)
        self.assertIn('missing permission', logs.output[0])
