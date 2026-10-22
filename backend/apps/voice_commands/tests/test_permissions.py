from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import BaselinePermission
from apps.accounts.factories import make_permission
from apps.voice_commands.permissions import has_required_permission


class NoUserTests(SimpleTestCase):
    def test_none_user_returns_false(self):
        self.assertFalse(has_required_permission(None, 'leave.approve'))


class HasRequiredPermissionTests(TestCase):
    """The voice permission gate against real users: the codename itself must be held through the seat or the
    company baseline, and full access does NOT stand in for it."""

    def setUp(self):
        cache.clear()

    def test_user_without_the_codename_returns_false(self):
        user = make_user('voice-plain@test.com')
        self.assertFalse(has_required_permission(user, 'leave.approve'))

    def test_user_whose_seat_has_the_codename_returns_true(self):
        user = make_user('voice-seat@test.com', role=make_role('voice_approver', permission_codenames=['leave.approve']))
        self.assertTrue(has_required_permission(user, 'leave.approve'))

    def test_a_baseline_permission_counts(self):
        BaselinePermission.objects.create(permission=make_permission('leave.approve'))
        self.assertTrue(has_required_permission(make_user('voice-base@test.com'), 'leave.approve'))

    def test_no_full_access_bypass(self):
        admin = make_user('voice-admin@test.com', role=make_role('voice_full_access', permission_codenames=['settings.edit']))
        self.assertFalse(has_required_permission(admin, 'leave.approve'))
        superuser = make_user('voice-super@test.com', is_superuser=True)
        self.assertFalse(has_required_permission(superuser, 'leave.approve'))
