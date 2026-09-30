"""
End-to-end HTTP-level tests for the Asset Management feature — real
authenticated requests through the actual URL/view/permission stack (login
via the real LoginView, same pattern apps.notifications.tests_role_change
already uses), not direct model/serializer calls.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.assets.models import Asset, AssetAssignment
from config.test_runner import TEST_COMPANY_CODE


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _make_branch(name: str) -> Branch:
    state, _ = State.objects.get_or_create(
        name=f'{name}State', defaults={'code': str(abs(hash(name)) % 10_000_000)},
    )
    city, _ = City.objects.get_or_create(name=f'{name}City', state=state)
    return Branch.objects.create(
        branch_code=f'{name.upper()}BR', branch_name=name, status=Branch.STATUS_ACTIVE,
        state=state, city=city,
    )


class AssetApiTests(TestCase):

    def setUp(self):
        # Each test method makes its own fresh login request against the
        # real (intentionally strict — 20/hour, config/settings.py) login
        # throttle. That throttle is keyed off the shared LocMemCache used
        # in this environment (no REDIS_URL set), which — like every
        # LocMemCache — persists across the whole test PROCESS, not per
        # TestCase/test method. Clearing it here isolates each test's own
        # login from every other test's, matching how independent real
        # clients would never share one rate-limit window in the first
        # place; it does not weaken or bypass the throttle logic itself.
        cache.clear()

        self.branch_a = _make_branch('AssetBranchA')
        self.branch_b = _make_branch('AssetBranchB')

        self.hr_role = make_role(
            'hr_assets_test', permission_codenames=[
                'assets.view', 'assets.create', 'assets.edit', 'assets.delete', 'settings.edit',
            ],
        )
        self.hr = make_user(
            'hr.assets@test.com', role=self.hr_role, employee_id='ASSETHR1',
            full_name='HR Admin', branch=self.branch_a.branch_name,
        )

        # Branch-scoped user — no settings.edit, so branch restriction
        # applies; has assets.create so the branch-restriction-on-create
        # test exercises branch scoping specifically, not permission denial.
        self.branch_role = make_role(
            'branch_assets_test', permission_codenames=['assets.view', 'assets.create', 'assets.edit'],
        )
        self.branch_user = make_user(
            'branch.assets@test.com', role=self.branch_role, employee_id='ASSETBR1',
            full_name='Branch User', branch=self.branch_a.branch_name,
        )

        # View/edit but deliberately NOT assets.create — isolates the
        # permission-denial case from the branch-scoping case above.
        self.view_only_role = make_role(
            'view_only_assets_test', permission_codenames=['assets.view', 'assets.edit'],
        )
        self.view_only_user = make_user(
            'viewonly.assets@test.com', role=self.view_only_role, employee_id='ASSETVO1',
            full_name='View Only User', branch=self.branch_a.branch_name,
        )

        # No assets.* permission at all.
        self.no_perm_role = make_role('no_perm_assets_test', permission_codenames=[])
        self.no_perm_user = make_user(
            'noperm.assets@test.com', role=self.no_perm_role, employee_id='ASSETNP1',
            full_name='No Perm User', branch=self.branch_a.branch_name,
        )

        self.employee_role = make_role('employee_assets_test', permission_codenames=[])
        self.employee = make_user(
            'employee.assets@test.com', role=self.employee_role, employee_id='ASSETEMP1',
            full_name='Test Employee', branch=self.branch_a.branch_name,
        )

        self.asset_a1 = Asset.objects.create(
            asset_tag='HTTP-A1', asset_name='Laptop A1', category='Laptop',
            asset_type='Electronics', branch=self.branch_a,
        )
        self.asset_a2 = Asset.objects.create(
            asset_tag='HTTP-A2', asset_name='Monitor A2', category='Monitor',
            asset_type='Electronics', branch=self.branch_a,
        )
        self.asset_b1 = Asset.objects.create(
            asset_tag='HTTP-B1', asset_name='Laptop B1', category='Laptop',
            asset_type='Electronics', branch=self.branch_b,
        )

        self.api = APIClient()

    # ── 1. List ──────────────────────────────────────────────────────────
    def test_list_as_admin_sees_all_branches(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-list-create'))
        self.assertEqual(resp.status_code, 200)
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertIn('HTTP-A1', tags)
        self.assertIn('HTTP-B1', tags)

    # ── 2. Create ────────────────────────────────────────────────────────
    def test_create_asset_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-NEW1', 'asset_name': 'New Laptop', 'category': 'Laptop',
            'asset_type': 'Electronics', 'branch': self.branch_a.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Asset.objects.filter(asset_tag='HTTP-NEW1').exists())

    def test_create_duplicate_asset_tag_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-A1', 'asset_name': 'Dup', 'category': 'Laptop',
            'asset_type': 'Electronics', 'branch': self.branch_a.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_negative_price_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-NEG1', 'asset_name': 'X', 'category': 'Laptop',
            'asset_type': 'Electronics', 'branch': self.branch_a.pk, 'purchase_price': '-50.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── 3. Update ────────────────────────────────────────────────────────
    def test_update_asset_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.put(
            reverse('asset-detail', kwargs={'pk': self.asset_a1.pk}),
            {
                'asset_tag': 'HTTP-A1', 'asset_name': 'Renamed Laptop', 'category': 'Laptop',
                'asset_type': 'Electronics', 'branch': self.branch_a.pk,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.asset_a1.refresh_from_db()
        self.assertEqual(self.asset_a1.asset_name, 'Renamed Laptop')

    # ── 4. Delete ────────────────────────────────────────────────────────
    def test_delete_asset_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.delete(reverse('asset-detail', kwargs={'pk': self.asset_a2.pk}))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(Asset.objects.filter(pk=self.asset_a2.pk).exists())

    def test_delete_assigned_asset_rejected(self):
        _login(self.api, self.hr.email)
        self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        resp = self.api.delete(reverse('asset-detail', kwargs={'pk': self.asset_a1.pk}))
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(Asset.objects.filter(pk=self.asset_a1.pk).exists())

    # ── 5. Assign ────────────────────────────────────────────────────────
    def test_assign_asset_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.asset_a1.refresh_from_db()
        self.assertEqual(self.asset_a1.status, Asset.STATUS_ASSIGNED)

    # ── 6. Return ────────────────────────────────────────────────────────
    def test_return_asset_success(self):
        _login(self.api, self.hr.email)
        assign_resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        assignment_id = assign_resp.data['data']['id']
        resp = self.api.post(reverse('asset-return', kwargs={'assignment_id': assignment_id}), {
            'return_date': '2026-02-01', 'return_condition': 'good', 'return_reason': 'Offboarding',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.asset_a1.refresh_from_db()
        self.assertEqual(self.asset_a1.status, Asset.STATUS_AVAILABLE)
        self.assertEqual(
            AssetAssignment.objects.get(pk=assignment_id).status, AssetAssignment.STATUS_RETURNED,
        )

    def test_return_damaged_routes_asset_to_damaged_status(self):
        _login(self.api, self.hr.email)
        assign_resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        assignment_id = assign_resp.data['data']['id']
        self.api.post(reverse('asset-return', kwargs={'assignment_id': assignment_id}), {
            'return_date': '2026-02-01', 'return_condition': 'damaged', 'return_reason': 'Screen cracked',
        }, format='json')
        self.asset_a1.refresh_from_db()
        self.assertEqual(self.asset_a1.status, Asset.STATUS_DAMAGED)

    # ── 7. Already-assigned rejection ───────────────────────────────────
    def test_assign_already_assigned_asset_rejected(self):
        _login(self.api, self.hr.email)
        self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': self.hr.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-16', 'condition_at_assignment': 'good',
        }, format='json')
        self.assertEqual(resp.status_code, 400)  # rejected by AssignAssetSerializer.validate_asset

    # ── 8. Permission denial ────────────────────────────────────────────
    def test_list_denied_without_assets_view_permission(self):
        _login(self.api, self.no_perm_user.email)
        resp = self.api.get(reverse('asset-list-create'))
        self.assertEqual(resp.status_code, 403)

    def test_create_denied_without_assets_create_permission(self):
        _login(self.api, self.view_only_user.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-DENY1', 'asset_name': 'X', 'category': 'Laptop',
            'asset_type': 'Electronics', 'branch': self.branch_a.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_request_rejected(self):
        anon = APIClient()
        resp = anon.get(reverse('asset-list-create'))
        self.assertIn(resp.status_code, (401, 403))

    # ── 9. Branch restriction ───────────────────────────────────────────
    def test_branch_scoped_user_only_sees_own_branch(self):
        _login(self.api, self.branch_user.email)
        resp = self.api.get(reverse('asset-list-create'))
        self.assertEqual(resp.status_code, 200)
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertIn('HTTP-A1', tags)
        self.assertNotIn('HTTP-B1', tags)  # branch B asset must not leak through

    def test_branch_scoped_user_cannot_access_other_branch_asset_detail(self):
        _login(self.api, self.branch_user.email)
        resp = self.api.get(reverse('asset-detail', kwargs={'pk': self.asset_b1.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_branch_scoped_user_cannot_create_asset_for_other_branch(self):
        _login(self.api, self.branch_user.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-CROSSBR1', 'asset_name': 'X', 'category': 'Laptop',
            'asset_type': 'Electronics', 'branch': self.branch_b.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    # ── 10. Search / filter / pagination ────────────────────────────────
    def test_search_by_asset_tag(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-list-create'), {'search': 'HTTP-A1'})
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertEqual(tags, {'HTTP-A1'})

    def test_filter_by_status(self):
        _login(self.api, self.hr.email)
        self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        resp = self.api.get(reverse('asset-list-create'), {'status': 'assigned'})
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertEqual(tags, {'HTTP-A1'})

    def test_filter_by_category(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-list-create'), {'category': 'Monitor'})
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertEqual(tags, {'HTTP-A2'})

    def test_filter_by_branch(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-list-create'), {'branch': str(self.branch_b.pk)})
        tags = {a['asset_tag'] for a in resp.data['data']['results']}
        self.assertEqual(tags, {'HTTP-B1'})

    def test_pagination_envelope_shape(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-list-create'), {'page_size': 2, 'page': 1})
        data = resp.data['data']
        self.assertIn('count', data)
        self.assertIn('page', data)
        self.assertIn('page_size', data)
        self.assertIn('total_pages', data)
        self.assertLessEqual(len(data['results']), 2)

    # ── Employee Assets tab endpoint ─────────────────────────────────────
    def test_employee_assets_endpoint_returns_current_and_history(self):
        _login(self.api, self.hr.email)
        assign_resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': self.employee.pk}), {
            'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new',
        }, format='json')
        assignment_id = assign_resp.data['data']['id']

        resp = self.api.get(reverse('employee-assets', kwargs={'employee_id': self.employee.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['data']['current']), 1)
        self.assertEqual(resp.data['data']['current'][0]['asset_tag'], 'HTTP-A1')

        self.api.post(reverse('asset-return', kwargs={'assignment_id': assignment_id}), {
            'return_date': '2026-02-01', 'return_condition': 'good', 'return_reason': 'Offboarding',
        }, format='json')
        resp2 = self.api.get(reverse('employee-assets', kwargs={'employee_id': self.employee.pk}))
        self.assertEqual(len(resp2.data['data']['current']), 0)
        self.assertEqual(len(resp2.data['data']['history']), 1)

    def test_employee_can_view_own_assets_without_assets_permission(self):
        # self.employee has NO assets.* permission at all — self-view must
        # still work (matches every other Employee Profile tab's own-data rule).
        self_client = APIClient()
        _login(self_client, self.employee.email)
        resp = self_client.get(reverse('employee-assets', kwargs={'employee_id': self.employee.pk}))
        self.assertEqual(resp.status_code, 200)
