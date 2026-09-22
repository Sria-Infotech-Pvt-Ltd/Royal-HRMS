"""Tests for BranchReassignAdminView (apps/branch/views.py) — this endpoint
and every other apps.branch view had zero test coverage before this file.

Written while reviewing a merged commit that added this endpoint: found and
fixed one real data-integrity gap along the way (no guard against
reassigning someone who is already Branch Admin of a DIFFERENT active
branch — see test_target_already_admin_of_another_branch_is_rejected, the
regression test for that fix)."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, PromotionRecord, Role
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_branch(code: str, name: str, hr=None) -> Branch:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=code, branch_name=name, address='Test Address', state=state, city=city, hr=hr,
    )


def _make_branch_admin_role():
    """Use the REAL seeded Branch Admin role (accounts.0052_seed_branch_admin_role,
    name='branch_admin', can_manage_branch=True) rather than fabricating a
    second role that also satisfies can_manage_branch=True — the view's own
    _branch_admin_role() resolves via Role.objects.filter(can_manage_branch=True)
    .first() with no explicit ordering, so a second qualifying role makes
    which one gets assigned ambiguous (confirmed directly: a locally-created
    competing role occasionally lost to the seeded one)."""
    return Role.objects.get(name='branch_admin')


def _onboarded_user(email, **kwargs):
    """make_user(), but with must_change_password explicitly False — the
    User model defaults it to True (still-onboarding), which the view under
    test correctly rejects; every fixture representing an ALREADY-eligible
    employee needs this, or every "should succeed" test fails for the wrong
    reason (onboarding-incomplete, not whatever the test actually means to
    check)."""
    kwargs.setdefault('must_change_password', False)
    return make_user(email, **kwargs)


class BranchReassignAdminViewTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid cross-test-class login-throttle pollution
        self.client = APIClient()

        self.branch_admin_role = _make_branch_admin_role()
        self.employee_role = make_role('employee')
        self.org_admin_role = make_role('org_admin', permission_codenames=['settings.edit', 'branches.edit', 'branches.view'])

        self.branch_a = _make_branch('BRA', 'Branch A')
        self.branch_b = _make_branch('BRB', 'Branch B')

        self.caller = make_user(
            'caller@test.com', role=self.org_admin_role, full_name='Org Admin', employee_id='EMPCALLER',
        )
        self.old_admin = _onboarded_user(
            'oldadmin@test.com', role=self.branch_admin_role, full_name='Old Admin',
            employee_id='EMPOLD', branch='Branch A',
        )
        self.branch_a.hr = self.old_admin
        self.branch_a.save(update_fields=['hr'])

        self.candidate = _onboarded_user(
            'candidate@test.com', role=self.employee_role, full_name='New Candidate',
            employee_id='EMPNEW', branch='Branch A',
        )

    def _reassign_url(self, branch: Branch):
        return reverse('branch-reassign-admin', kwargs={'pk': branch.pk})

    def test_permission_denied_without_branches_edit(self):
        no_perm_role = make_role('no_perm', permission_codenames=['branches.view'])
        make_user('noperm@test.com', role=no_perm_role, employee_id='EMPNOPERM')
        _login(self.client, 'noperm@test.com')

        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPNEW'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.branch_a.refresh_from_db()
        self.assertEqual(self.branch_a.hr_id, self.old_admin.id)

    def test_missing_employee_id_returns_400(self):
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unknown_employee_id_returns_404(self):
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'NOSUCHID'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_inactive_employee_is_rejected(self):
        make_user(
            'inactive@test.com', role=self.employee_role, full_name='Inactive Guy',
            employee_id='EMPINACT', branch='Branch A', is_active=False,
        )
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPINACT'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('inactive', resp.data['message'].lower())

    def test_employee_still_onboarding_is_rejected(self):
        make_user(
            'onboarding@test.com', role=self.employee_role, full_name='Onboarding Guy',
            employee_id='EMPONB', branch='Branch A', must_change_password=True,
        )
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPONB'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('onboarding', resp.data['message'].lower())

    def test_company_admin_is_rejected(self):
        make_user(
            'compadmin@test.com', role=self.org_admin_role, full_name='Company Admin',
            employee_id='EMPCOMP', branch='Branch A',
        )
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPCOMP'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('company admin', resp.data['message'].lower())

    def test_already_admin_here_is_rejected(self):
        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPOLD'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already the branch admin', resp.data['message'].lower())

    def test_target_already_admin_of_another_branch_is_rejected(self):
        """Regression test: without this guard, reassigning someone who is
        already Branch Admin of a DIFFERENT active branch would silently
        move their `branch` field to the new branch while leaving the OLD
        branch's `hr` FK still pointing at them — a dangling reference to
        someone no longer actually assigned there."""
        other_admin = _onboarded_user(
            'otheradmin@test.com', role=self.branch_admin_role, full_name='Other Branch Admin',
            employee_id='EMPOTHER', branch='Branch B',
        )
        self.branch_b.hr = other_admin
        self.branch_b.save(update_fields=['hr'])

        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPOTHER'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('branch b', resp.data['message'].lower())
        # Nothing must have changed on either side.
        self.branch_a.refresh_from_db()
        self.branch_b.refresh_from_db()
        other_admin.refresh_from_db()
        self.assertEqual(self.branch_a.hr_id, self.old_admin.id)
        self.assertEqual(self.branch_b.hr_id, other_admin.id)
        self.assertEqual(other_admin.branch, 'Branch B')

    def test_inactive_branch_admin_elsewhere_does_not_block_reassignment(self):
        """The cross-branch guard is scoped to ACTIVE branches only — a
        stale hr pointer on a long-inactive branch shouldn't block an
        otherwise-legitimate reassignment."""
        other_admin = _onboarded_user(
            'inactivebranchadmin@test.com', role=self.branch_admin_role, full_name='Stale Admin',
            employee_id='EMPSTALE', branch='Branch B',
        )
        self.branch_b.hr = other_admin
        self.branch_b.status = Branch.STATUS_INACTIVE
        self.branch_b.save(update_fields=['hr', 'status'])

        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPSTALE'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)

    def test_happy_path_reassigns_demotes_old_admin_and_cascades_hr(self):
        # A rank-and-file employee whose `hr` pointed at the OLD admin —
        # must cascade to the new admin once the swap completes.
        report = make_user(
            'report@test.com', role=self.employee_role, full_name='Reports To Old Admin',
            employee_id='EMPREPORT', branch='Branch A', hr=self.old_admin,
        )

        _login(self.client, 'caller@test.com')
        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPNEW'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['hr_name'], 'New Candidate')

        self.branch_a.refresh_from_db()
        self.assertEqual(self.branch_a.hr_id, self.candidate.id)

        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.role_id, self.branch_admin_role.id)
        self.assertEqual(self.candidate.branch, 'Branch A')

        self.old_admin.refresh_from_db()
        self.assertEqual(self.old_admin.role_id, self.employee_role.id)
        # Demotion only ever changes role — the old admin stays assigned to
        # the same branch as a regular employee, not relocated.
        self.assertEqual(self.old_admin.branch, 'Branch A')

        report.refresh_from_db()
        self.assertEqual(report.hr_id, self.candidate.id)

        self.assertTrue(
            AuditLog.objects.filter(action='branch_admin_removed', object_id=str(self.old_admin.id)).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(action='branch_admin_assigned', object_id=str(self.candidate.id)).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(action='branch_admin_reassigned', object_id=str(self.branch_a.pk)).exists()
        )
        self.assertTrue(PromotionRecord.objects.filter(employee=self.old_admin, new_role='employee').exists())
        self.assertTrue(
            PromotionRecord.objects.filter(employee=self.candidate, new_role=self.branch_admin_role.name).exists()
        )

    def test_assigning_admin_to_a_branch_with_none_previously(self):
        self.branch_b.hr = None
        self.branch_b.save(update_fields=['hr'])
        target = _onboarded_user(
            'newforb@test.com', role=self.employee_role, full_name='New For B',
            employee_id='EMPNEWB', branch='Branch B',
        )
        _login(self.client, 'caller@test.com')

        resp = self.client.post(self._reassign_url(self.branch_b), {'employee_id': 'EMPNEWB'}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.branch_b.refresh_from_db()
        self.assertEqual(self.branch_b.hr_id, target.id)
        # No previous admin to demote — no branch_admin_removed audit entry.
        self.assertFalse(AuditLog.objects.filter(action='branch_admin_removed').exists())

    def test_branch_scoped_caller_cannot_reassign_a_different_branch(self):
        branch_scoped_role = make_role('branch_scoped_caller', permission_codenames=['branches.edit', 'branches.view'])
        make_user(
            'scoped@test.com', role=branch_scoped_role, full_name='Scoped Caller',
            employee_id='EMPSCOPED', branch='Branch B',
        )
        _login(self.client, 'scoped@test.com')

        resp = self.client.post(self._reassign_url(self.branch_a), {'employee_id': 'EMPNEW'}, format='json')

        self.assertEqual(resp.status_code, 403)

    def test_unknown_branch_returns_404(self):
        _login(self.client, 'caller@test.com')
        resp = self.client.post(
            reverse('branch-reassign-admin', kwargs={'pk': 999999}), {'employee_id': 'EMPNEW'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)
