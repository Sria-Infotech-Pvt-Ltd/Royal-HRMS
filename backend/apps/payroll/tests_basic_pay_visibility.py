"""Payroll Settings visibility options for the employee Basic Pay editor."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import BASIC_PAY_EDITOR_LINE_CODES, PayrollSettings


PAYROLL_SETTINGS_URL = '/api/payroll/settings/'


def _api(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class BasicPayEditorVisibilityTests(TestCase):
    def setUp(self):
        editor_role = make_role('basic_pay_visibility_editor', permission_codenames=['payroll.edit'])
        viewer_role = make_role('basic_pay_visibility_viewer', permission_codenames=['payroll.view'])
        self.editor = make_user('basic-pay-editor@test.com', role=editor_role)
        self.viewer = make_user('basic-pay-viewer@test.com', role=viewer_role)

    def test_all_pay_rows_are_visible_by_default(self):
        response = _api(self.viewer).get(PAYROLL_SETTINGS_URL)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data['data']['basic_pay_visible_lines'],
            list(BASIC_PAY_EDITOR_LINE_CODES),
        )

    def test_payroll_editor_can_hide_a_line_without_changing_pay_records(self):
        visible_lines = [code for code in BASIC_PAY_EDITOR_LINE_CODES if code != '1100']
        response = _api(self.editor).put(
            PAYROLL_SETTINGS_URL,
            {'basic_pay_visible_lines': visible_lines},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            PayrollSettings.objects.get().basic_pay_visible_lines,
            visible_lines,
        )

    def test_viewer_cannot_change_pay_line_visibility(self):
        response = _api(self.viewer).put(
            PAYROLL_SETTINGS_URL,
            {'basic_pay_visible_lines': ['1000']},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_unknown_pay_line_code_is_rejected(self):
        response = _api(self.editor).put(
            PAYROLL_SETTINGS_URL,
            {'basic_pay_visible_lines': ['not-a-pay-line']},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

    def test_duplicate_pay_line_codes_are_rejected(self):
        response = _api(self.editor).put(
            PAYROLL_SETTINGS_URL,
            {'basic_pay_visible_lines': ['1000', '1000']},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
