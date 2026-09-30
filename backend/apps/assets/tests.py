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
from apps.assets.models import Asset, AssetAssignment, AssetMaintenanceRecord
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
            asset_tag='HTTP-A1', asset_name='Laptop A1', category='IT Equipment',
            asset_type='Laptop', branch=self.branch_a,
        )
        self.asset_a2 = Asset.objects.create(
            asset_tag='HTTP-A2', asset_name='Office Chair A2', category='Furniture',
            asset_type='Office Chair', branch=self.branch_a,
        )
        self.asset_b1 = Asset.objects.create(
            asset_tag='HTTP-B1', asset_name='Laptop B1', category='IT Equipment',
            asset_type='Laptop', branch=self.branch_b,
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
            'asset_tag': 'HTTP-NEW1', 'asset_name': 'New Laptop', 'category': 'IT Equipment',
            'asset_type': 'Laptop', 'branch': self.branch_a.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(Asset.objects.filter(asset_tag='HTTP-NEW1').exists())

    def test_create_duplicate_asset_tag_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-A1', 'asset_name': 'Dup', 'category': 'IT Equipment',
            'asset_type': 'Laptop', 'branch': self.branch_a.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_negative_price_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'HTTP-NEG1', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Laptop', 'branch': self.branch_a.pk, 'purchase_price': '-50.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── 3. Update ────────────────────────────────────────────────────────
    def test_update_asset_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.put(
            reverse('asset-detail', kwargs={'pk': self.asset_a1.pk}),
            {
                'asset_tag': 'HTTP-A1', 'asset_name': 'Renamed Laptop', 'category': 'IT Equipment',
                'asset_type': 'Laptop', 'branch': self.branch_a.pk,
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
            'asset_tag': 'HTTP-DENY1', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Laptop', 'branch': self.branch_a.pk,
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
            'asset_tag': 'HTTP-CROSSBR1', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Laptop', 'branch': self.branch_b.pk,
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
        resp = self.api.get(reverse('asset-list-create'), {'category': 'Furniture'})
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

    # ── Production 404 bug: employee CODE vs UUID in the assign URL ──────
    # The bug was entirely in the frontend (employees/[id]/page.tsx passed
    # the raw route param — which can be an employee CODE when reached via
    # Org Chart/Payroll links — instead of the resolved employeeUuid state
    # already used by SalaryTab/PayrollTab). The backend's strict
    # <uuid:employee_id> route was always correct; this reproduces exactly
    # the reported BEFORE/AFTER behavior at the URL-routing level.
    def test_assign_url_rejects_non_uuid_employee_code(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(
            '/api/assets/employees/DEM00028/assign/',
            {'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)  # BEFORE: matches the reported production bug

    def test_assign_url_succeeds_with_real_employee_uuid(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(
            f'/api/assets/employees/{self.employee.pk}/assign/',
            {'asset': str(self.asset_a1.pk), 'assigned_date': '2026-01-15', 'condition_at_assignment': 'new'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)  # AFTER: the actual fix


class AssetCategoryTypeApiTests(TestCase):
    """Asset Category / Asset Type master data, cascading, and 'Other' handling."""

    def setUp(self):
        cache.clear()
        self.branch = _make_branch('CatTypeBranch')
        self.hr_role = make_role(
            'hr_cattype_test', permission_codenames=[
                'assets.view', 'assets.create', 'assets.edit', 'assets.delete', 'settings.edit',
            ],
        )
        self.hr = make_user(
            'hr.cattype@test.com', role=self.hr_role, employee_id='CATTYPEHR1',
            full_name='HR Admin', branch=self.branch.branch_name,
        )
        self.api = APIClient()

    def test_default_categories_seeded(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-category-list-create'))
        self.assertEqual(resp.status_code, 200)
        names = {c['name'] for c in resp.data['data']}
        self.assertEqual(
            names,
            {'IT Equipment', 'Mobile Devices', 'Office Equipment', 'Furniture', 'Access & Security', 'Other'},
        )

    def test_types_cascade_by_category(self):
        _login(self.api, self.hr.email)
        cat_resp = self.api.get(reverse('asset-category-list-create'))
        furniture_id = next(c['id'] for c in cat_resp.data['data'] if c['name'] == 'Furniture')

        resp = self.api.get(reverse('asset-type-list-create'), {'category': furniture_id})
        self.assertEqual(resp.status_code, 200)
        names = {t['name'] for t in resp.data['data']}
        self.assertEqual(names, {'Office Chair', 'Office Desk', 'Cabinet', 'Other'})
        # A type from a different category must never leak into this list.
        self.assertNotIn('Laptop', names)

    def test_create_category_and_type(self):
        _login(self.api, self.hr.email)
        cat_resp = self.api.post(reverse('asset-category-list-create'), {'name': 'Vehicles'}, format='json')
        self.assertEqual(cat_resp.status_code, 201, cat_resp.data)
        category_id = cat_resp.data['data']['id']

        type_resp = self.api.post(
            reverse('asset-type-list-create'), {'name': 'Company Car', 'category': category_id}, format='json',
        )
        self.assertEqual(type_resp.status_code, 201, type_resp.data)

    def test_duplicate_category_name_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-category-list-create'), {'name': 'Furniture'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_asset_rejects_invalid_category(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-BAD1', 'asset_name': 'X', 'category': 'Not A Real Category',
            'asset_type': 'Other', 'branch': self.branch.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('category', resp.data.get('data', {}))

    def test_create_asset_rejects_type_from_wrong_category(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-BAD2', 'asset_name': 'X', 'category': 'Furniture',
            'asset_type': 'Laptop', 'branch': self.branch.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('asset_type', resp.data.get('data', {}))

    # ── "Other" handling ─────────────────────────────────────────────────
    def test_other_asset_type_requires_custom_value(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-OTH1', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Other', 'branch': self.branch.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('asset_type_other', resp.data.get('data', {}))

    def test_other_asset_type_rejects_whitespace_only_value(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-OTH2', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Other', 'asset_type_other': '   ', 'branch': self.branch.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_other_asset_type_saved_and_editable(self):
        _login(self.api, self.hr.email)
        create_resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-OTH3', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Other', 'asset_type_other': '  MacBook Pro  ', 'branch': self.branch.pk,
        }, format='json')
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        self.assertEqual(create_resp.data['data']['asset_type'], 'Other')
        self.assertEqual(create_resp.data['data']['asset_type_other'], 'MacBook Pro')  # trimmed

        asset_id = create_resp.data['data']['id']
        get_resp = self.api.get(reverse('asset-detail', kwargs={'pk': asset_id}))
        self.assertEqual(get_resp.data['data']['asset_type_other'], 'MacBook Pro')

    def test_switching_away_from_other_clears_custom_value(self):
        _login(self.api, self.hr.email)
        create_resp = self.api.post(reverse('asset-list-create'), {
            'asset_tag': 'CATTYPE-OTH4', 'asset_name': 'X', 'category': 'IT Equipment',
            'asset_type': 'Other', 'asset_type_other': 'Custom Thing', 'branch': self.branch.pk,
        }, format='json')
        asset_id = create_resp.data['data']['id']

        update_resp = self.api.patch(
            reverse('asset-detail', kwargs={'pk': asset_id}),
            {'asset_type': 'Laptop', 'asset_type_other': 'Custom Thing'}, format='json',
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.data)
        self.assertEqual(update_resp.data['data']['asset_type_other'], '')

    def test_legacy_pre_master_data_value_editable_unchanged(self):
        # An asset created before this feature existed (arbitrary free-text
        # category/type) must remain editable without being forced onto the
        # new master list, as long as the value isn't being changed.
        legacy = Asset.objects.create(
            asset_tag='CATTYPE-LEGACY1', asset_name='Old thing', category='Gadgets',
            asset_type='Widget', branch=self.branch,
        )
        _login(self.api, self.hr.email)
        resp = self.api.patch(
            reverse('asset-detail', kwargs={'pk': legacy.pk}), {'asset_name': 'Renamed'}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['category'], 'Gadgets')


class AssetMaintenanceApiTests(TestCase):
    """Send to Maintenance / Complete Maintenance — real HTTP-level tests."""

    def setUp(self):
        cache.clear()
        self.branch = _make_branch('MaintBranch')
        self.hr_role = make_role(
            'hr_maint_test', permission_codenames=[
                'assets.view', 'assets.create', 'assets.edit', 'assets.delete', 'settings.edit',
            ],
        )
        self.hr = make_user(
            'hr.maint@test.com', role=self.hr_role, employee_id='MAINTHR1',
            full_name='HR Admin', branch=self.branch.branch_name,
        )
        self.no_perm_role = make_role('no_perm_maint_test', permission_codenames=['assets.view'])
        self.no_perm_user = make_user(
            'noperm.maint@test.com', role=self.no_perm_role, employee_id='MAINTNP1',
            full_name='No Edit Perm', branch=self.branch.branch_name,
        )
        self.api = APIClient()

        self.damaged_asset = Asset.objects.create(
            asset_tag='MAINT-D1', asset_name='Damaged Laptop', category='IT Equipment',
            asset_type='Laptop', branch=self.branch, status=Asset.STATUS_DAMAGED,
            condition=Asset.CONDITION_DAMAGED,
        )
        self.available_asset = Asset.objects.create(
            asset_tag='MAINT-A1', asset_name='Fine Laptop', category='IT Equipment',
            asset_type='Laptop', branch=self.branch, status=Asset.STATUS_AVAILABLE,
        )

    # ── Send to Maintenance ──────────────────────────────────────────────
    def test_send_damaged_asset_to_maintenance_success(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': 'Screen cracked'}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.damaged_asset.refresh_from_db()
        self.assertEqual(self.damaged_asset.status, Asset.STATUS_UNDER_REPAIR)
        record = AssetMaintenanceRecord.objects.get(pk=resp.data['data']['id'])
        self.assertEqual(record.status, AssetMaintenanceRecord.STATUS_IN_PROGRESS)
        self.assertEqual(record.sent_to_maintenance_by, self.hr)
        self.assertEqual(record.issue, 'Screen cracked')

    def test_send_non_damaged_asset_to_maintenance_rejected(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.available_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': 'X'}, format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.available_asset.refresh_from_db()
        self.assertEqual(self.available_asset.status, Asset.STATUS_AVAILABLE)

    def test_send_to_maintenance_requires_issue(self):
        _login(self.api, self.hr.email)
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': '   '}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_send_asset_already_under_maintenance_again(self):
        _login(self.api, self.hr.email)
        self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': 'Screen cracked'}, format='json',
        )
        # Asset is now under_repair, not damaged -> a second attempt is
        # rejected by the same status check (belt-and-suspenders with the
        # DB constraint, exercised directly at the model layer below).
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-26', 'issue': 'Again'}, format='json',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            AssetMaintenanceRecord.objects.filter(
                asset=self.damaged_asset, status=AssetMaintenanceRecord.STATUS_IN_PROGRESS,
            ).count(),
            1,
        )

    def test_db_constraint_blocks_duplicate_active_maintenance_record(self):
        from django.db import IntegrityError
        AssetMaintenanceRecord.objects.create(
            asset=self.damaged_asset, maintenance_start_date='2026-09-25', issue='First',
        )
        with self.assertRaises(IntegrityError):
            AssetMaintenanceRecord.objects.create(
                asset=self.damaged_asset, maintenance_start_date='2026-09-26', issue='Second',
            )

    def test_send_to_maintenance_denied_without_permission(self):
        _login(self.api, self.no_perm_user.email)
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': 'X'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

    # ── Complete Maintenance ─────────────────────────────────────────────
    def _send_to_maintenance(self) -> str:
        resp = self.api.post(
            reverse('asset-send-to-maintenance', kwargs={'pk': self.damaged_asset.pk}),
            {'maintenance_start_date': '2026-09-25', 'issue': 'Screen cracked'}, format='json',
        )
        return resp.data['data']['id']

    def test_complete_maintenance_repaired_returns_asset_to_available(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {
                'completed_date': '2026-09-28', 'outcome': 'repaired',
                'maintenance_notes': 'Screen replaced', 'resulting_condition': 'good',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.damaged_asset.refresh_from_db()
        self.assertEqual(self.damaged_asset.status, Asset.STATUS_AVAILABLE)
        self.assertEqual(self.damaged_asset.condition, Asset.CONDITION_GOOD)
        record = AssetMaintenanceRecord.objects.get(pk=record_id)
        self.assertEqual(record.status, AssetMaintenanceRecord.STATUS_COMPLETED)
        self.assertEqual(record.completed_by, self.hr)
        self.assertEqual(record.outcome, AssetMaintenanceRecord.OUTCOME_REPAIRED)

    def test_complete_maintenance_not_repairable_retires_asset(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-28', 'outcome': 'not_repairable', 'maintenance_notes': 'Beyond repair'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.damaged_asset.refresh_from_db()
        self.assertEqual(self.damaged_asset.status, Asset.STATUS_RETIRED)

    def test_complete_maintenance_requires_notes(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-28', 'outcome': 'repaired', 'maintenance_notes': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_complete_maintenance_rejects_invalid_outcome(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-28', 'outcome': 'fixed_by_magic', 'maintenance_notes': 'X'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_complete_maintenance_rejects_date_before_start(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-01', 'outcome': 'repaired', 'maintenance_notes': 'X'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_complete_maintenance_twice(self):
        _login(self.api, self.hr.email)
        record_id = self._send_to_maintenance()
        self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-28', 'outcome': 'repaired', 'maintenance_notes': 'Fixed'}, format='json',
        )
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': record_id}),
            {'completed_date': '2026-09-29', 'outcome': 'repaired', 'maintenance_notes': 'Again'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)  # no longer an in-progress record

    def test_cannot_complete_maintenance_for_available_asset(self):
        # No maintenance record exists at all for an available asset.
        _login(self.api, self.hr.email)
        import uuid
        resp = self.api.post(
            reverse('asset-maintenance-complete', kwargs={'pk': uuid.uuid4()}),
            {'completed_date': '2026-09-28', 'outcome': 'repaired', 'maintenance_notes': 'X'}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    # ── Full lifecycle + history preservation ────────────────────────────
    def test_full_lifecycle_available_to_damaged_to_repaired_to_available(self):
        _login(self.api, self.hr.email)
        employee = make_user(
            'lifecycle.emp@test.com', role=self.no_perm_role, employee_id='LIFECYCLE1',
            full_name='Lifecycle Employee', branch=self.branch.branch_name,
        )
        asset = Asset.objects.create(
            asset_tag='MAINT-LC1', asset_name='Lifecycle Laptop', category='IT Equipment',
            asset_type='Laptop', branch=self.branch, status=Asset.STATUS_AVAILABLE,
        )

        # Assign
        assign_resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': employee.pk}), {
            'asset': str(asset.pk), 'assigned_date': '2026-08-10', 'condition_at_assignment': 'good',
        }, format='json')
        self.assertEqual(assign_resp.status_code, 201, assign_resp.data)
        assignment_id = assign_resp.data['data']['id']

        # Return as damaged
        return_resp = self.api.post(reverse('asset-return', kwargs={'assignment_id': assignment_id}), {
            'return_date': '2026-09-25', 'return_condition': 'damaged', 'return_reason': 'Screen damaged',
        }, format='json')
        self.assertEqual(return_resp.status_code, 200, return_resp.data)
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_DAMAGED)

        # Send to maintenance
        maint_resp = self.api.post(reverse('asset-send-to-maintenance', kwargs={'pk': asset.pk}), {
            'maintenance_start_date': '2026-09-25', 'issue': 'Screen damaged',
        }, format='json')
        self.assertEqual(maint_resp.status_code, 201, maint_resp.data)
        record_id = maint_resp.data['data']['id']
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_UNDER_REPAIR)

        # Complete maintenance -> repaired
        complete_resp = self.api.post(reverse('asset-maintenance-complete', kwargs={'pk': record_id}), {
            'completed_date': '2026-09-28', 'outcome': 'repaired', 'maintenance_notes': 'Screen replaced',
        }, format='json')
        self.assertEqual(complete_resp.status_code, 200, complete_resp.data)
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_AVAILABLE)

        # Original AssetAssignment record is still fully intact — not
        # replaced, not duplicated, not deleted.
        assignment = AssetAssignment.objects.get(pk=assignment_id)
        self.assertEqual(assignment.status, AssetAssignment.STATUS_RETURNED)
        self.assertEqual(assignment.return_condition, 'damaged')
        self.assertEqual(assignment.return_reason, 'Screen damaged')
        self.assertEqual(AssetAssignment.objects.filter(asset=asset).count(), 1)

        # Asset can be assigned again now that it's available.
        reassign_resp = self.api.post(reverse('asset-assign', kwargs={'employee_id': employee.pk}), {
            'asset': str(asset.pk), 'assigned_date': '2026-09-30', 'condition_at_assignment': 'good',
        }, format='json')
        self.assertEqual(reassign_resp.status_code, 201, reassign_resp.data)

    # ── active_maintenance surfaced on the Asset serializer ──────────────
    def test_asset_list_includes_active_maintenance(self):
        _login(self.api, self.hr.email)
        self._send_to_maintenance()
        resp = self.api.get(reverse('asset-list-create'), {'search': 'MAINT-D1'})
        asset_data = resp.data['data']['results'][0]
        self.assertIsNotNone(asset_data['active_maintenance'])
        self.assertEqual(asset_data['active_maintenance']['issue'], 'Screen cracked')

    def test_asset_detail_active_maintenance_null_when_none(self):
        _login(self.api, self.hr.email)
        resp = self.api.get(reverse('asset-detail', kwargs={'pk': self.available_asset.pk}))
        self.assertIsNone(resp.data['data']['active_maintenance'])
