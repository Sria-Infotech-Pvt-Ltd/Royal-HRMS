"""Company-wide allowance catalogue behavior and access control."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import PayComponent, SalaryComponent, SalaryStructure


ALLOWANCE_URL = '/api/payroll/allowances/'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class CompanyAllowanceCatalogueTests(TestCase):
    def setUp(self):
        cache.clear()
        editor_role = make_role(
            'allowance_catalogue_editor',
            permission_codenames=['payroll.view', 'payroll.create', 'payroll.edit'],
        )
        viewer_role = make_role('allowance_catalogue_viewer', permission_codenames=['payroll.view'])
        self.editor = make_user('allowance-editor@test.com', role=editor_role)
        self.viewer = make_user('allowance-viewer@test.com', role=viewer_role)

    def test_default_allowances_are_listed_for_payroll_configuration(self):
        response = _api(self.editor).get(ALLOWANCE_URL)
        self.assertEqual(response.status_code, 200, response.data)
        names = {item['name'] for item in response.data['data']}
        self.assertIn('Dearness Allowance', names)
        self.assertIn('Special Allowance', names)

    def test_editor_can_add_and_deactivate_an_allowance(self):
        client = _api(self.editor)
        create_response = client.post(
            ALLOWANCE_URL,
            {'name': 'Internet Allowance', 'is_taxable': False},
            format='json',
        )
        self.assertEqual(create_response.status_code, 201, create_response.data)
        allowance_data = create_response.data['data']
        allowance = PayComponent.objects.get(pk=allowance_data['id'])
        self.assertTrue(allowance.is_company_allowance)
        self.assertEqual(allowance.category, PayComponent.CATEGORY_EARNING)
        self.assertFalse(allowance.is_taxable)
        self.assertTrue(allowance.code.startswith('ALW_INTERNET_ALLOWANCE'))

        structure = SalaryStructure.objects.create(name='Allowance catalogue test')
        structure_component = SalaryComponent.objects.create(
            structure=structure,
            name=allowance.name,
            component_type=SalaryComponent.TYPE_ALLOWANCE,
            calculation_type=SalaryComponent.CALC_FIXED,
            value=500,
        )

        update_response = client.put(
            f'{ALLOWANCE_URL}{allowance.pk}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200, update_response.data)
        allowance.refresh_from_db()
        structure_component.refresh_from_db()
        self.assertFalse(allowance.is_active)
        self.assertTrue(structure_component.is_active)

    def test_duplicate_allowance_name_is_rejected_case_insensitively(self):
        client = _api(self.editor)
        first = client.post(ALLOWANCE_URL, {'name': 'Meal Allowance'}, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        duplicate = client.post(ALLOWANCE_URL, {'name': 'meal allowance'}, format='json')
        self.assertEqual(duplicate.status_code, 400, duplicate.data)

    def test_viewer_can_read_but_cannot_change_allowance_catalogue(self):
        client = _api(self.viewer)
        self.assertEqual(client.get(ALLOWANCE_URL).status_code, 200)
        self.assertEqual(
            client.post(ALLOWANCE_URL, {'name': 'Restricted Allowance'}, format='json').status_code,
            403,
        )

    def test_user_without_payroll_access_is_denied(self):
        no_access = make_user('allowance-no-access@test.com')
        self.assertEqual(_api(no_access).get(ALLOWANCE_URL).status_code, 403)
