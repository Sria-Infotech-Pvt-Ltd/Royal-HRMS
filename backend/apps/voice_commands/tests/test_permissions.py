from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.voice_commands.permissions import has_required_permission


def _user_with_permission(has_it: bool):
    role_permissions = MagicMock()
    role_permissions.filter.return_value.exists.return_value = has_it
    role = SimpleNamespace(role_permissions=role_permissions)
    return SimpleNamespace(role=role)


class HasRequiredPermissionTests(SimpleTestCase):
    """
    Unit tests for the standalone voice_commands permission check — the
    Variant-A pattern (see hrms/views/leave.py, expenses.py,
    branch/views_access.py), copied on purpose rather than imported, since
    none of the 19 existing _has_perm functions are exported.
    """

    def test_none_user_returns_false(self):
        self.assertFalse(has_required_permission(None, 'leave.approve'))

    def test_user_with_no_role_returns_false(self):
        user = SimpleNamespace(role=None)
        self.assertFalse(has_required_permission(user, 'leave.approve'))

    def test_user_whose_role_lacks_the_codename_returns_false(self):
        user = _user_with_permission(has_it=False)
        self.assertFalse(has_required_permission(user, 'leave.approve'))

    def test_user_whose_role_has_the_codename_returns_true(self):
        user = _user_with_permission(has_it=True)
        self.assertTrue(has_required_permission(user, 'leave.approve'))

    def test_no_system_admin_bypass(self):
        """
        Unlike accounts/views.py's variant, this one never short-circuits for
        system_admin — a codename either exists on the role's RolePermission
        rows or the check fails, full stop.
        """
        role_permissions = MagicMock()
        role_permissions.filter.return_value.exists.return_value = False
        role = SimpleNamespace(name='system_admin', role_permissions=role_permissions)
        user = SimpleNamespace(role=role)

        self.assertFalse(has_required_permission(user, 'leave.approve'))
