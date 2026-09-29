"""
Permanent regression suite for the two-stage Hire flow (HireAction ->
HireActionCompleteView). Written after a manual QA pass this session found
4 real bugs in this flow (see git history around "Fix 4 bugs found in Hire
wizard QA pass") — this suite exists so none of those regress silently as
the wizard keeps changing, and so any *new* field/step added later has an
obvious place to add its own required-field test.

Run with: python manage.py test apps.accounts.tests_hire_wizard
"""
from __future__ import annotations

import datetime
import io

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import (
    DocumentTypeConfig, EmployeeCodeSeries, HireAction, HireActionDocument, OrgUnit, Position,
)

# A real, minimal, valid PNG — used everywhere a file upload needs to pass
# the format/content-sniffing check. Padded past the 2KB minimum-size floor
# with trailing zero bytes (harmless after the PNG's own IEND chunk).
_VALID_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108020000009077'
    '53de0000000c4944415478da6360000002000155a5d4a80000000049454e44ae426082'
) + b'\x00' * 3000


def _png_file(name: str, content: bytes = _VALID_PNG) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type='image/png')


def _tomorrow_iso() -> str:
    # Always a real future date relative to whenever the suite actually
    # runs — a hardcoded literal date here would silently become "the
    # past" (and start failing every create for an unrelated reason) the
    # moment the calendar caught up to it.
    return (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


class HireWizardTestCase(TestCase):
    """Shared fixtures: an HR user with employees.create, a Position to hire
    into, and the URL helpers every test below reuses."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.hr_role = make_role('hr_admin_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr@test.com', role=self.hr_role, password='TestPass123!')
        self.client.force_authenticate(user=self.hr_user)

        self.plain_role = make_role('employee_test')

        self.unit = OrgUnit.objects.create(name='Engineering')
        self.position = Position.objects.create(org_unit=self.unit, title='Software Engineer', grade='L2')

    def _create_draft(self, **overrides) -> HireAction:
        payload = {
            'reason': 'new_position',
            'effective_from': _tomorrow_iso(),
            'position': str(self.position.id),
        }
        payload.update(overrides)
        resp = self.client.post(reverse('hire-action-list'), payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return HireAction.objects.get(pk=resp.data['data']['id'])

    def _patch(self, action: HireAction, data: dict):
        return self.client.patch(reverse('hire-action-detail', args=[action.id]), data, format='json')

    def _set_employment_type(self, action: HireAction, employment_type: str = 'Permanent'):
        resp = self._patch(action, {'employment_type': employment_type})
        self.assertEqual(resp.status_code, 200, resp.data)
        action.refresh_from_db()
        return action

    def _complete(self, action: HireAction):
        return self.client.post(reverse('hire-action-complete', args=[action.id]))

    # A fully valid draft — the "everything correct" baseline every negative
    # test below starts from and breaks exactly one thing at a time.
    def _valid_full_draft(self) -> dict:
        return {
            'first_name': 'Arjun', 'last_name': 'Mehta', 'email': 'arjun.mehta@test.com',
            'date_of_birth': '1990-01-01', 'gender': 'male', 'nationality': 'Indian',
            'phone': '+91 9876543210',
            'role': str(self.plain_role.id), 'branch': 'Kondapur Office',
            'pan_number': 'ABCDE1234F', 'aadhaar_number': '123456789012',
            'account_holder_name': 'Arjun Mehta', 'account_number': '1234567890',
            'ifsc_code': 'HDFC0001234',
        }

    def _upload_all_required_docs(self, action: HireAction):
        required_keys = DocumentTypeConfig.objects.filter(required=True).values_list('type_key', flat=True)
        for key in required_keys:
            # Content must differ per key — the real upload endpoint rejects
            # byte-identical files reused across two document types (a
            # genuine anti-mistake check). len(key) alone isn't a safe way
            # to vary the bytes: two different keys can share the same
            # length (e.g. "signed_offer_letter" and "twelfth_certificate"
            # are both 19 chars), which collided here once a new required
            # type happened to land on the same length as an existing one.
            # The key's own bytes are unique per key by definition.
            resp = self.client.post(
                reverse('hire-action-document-list', args=[action.id]),
                {'document_type': key, 'file': _png_file(f'{key}.png', _VALID_PNG + key.encode() + b'\x00' * 10)},
                format='multipart',
            )
            self.assertEqual(resp.status_code, 201, resp.data)


class Stage1CreateTests(HireWizardTestCase):
    def test_create_draft_succeeds_with_valid_payload(self):
        action = self._create_draft()
        self.assertEqual(action.status, HireAction.STATUS_DRAFT)
        self.assertEqual(action.position_id, self.position.id)

    def test_create_rejects_missing_reason(self):
        resp = self.client.post(reverse('hire-action-list'), {
            'effective_from': _tomorrow_iso(), 'position': str(self.position.id),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_rejects_past_effective_date(self):
        resp = self.client.post(reverse('hire-action-list'), {
            'reason': 'new_position', 'effective_from': '2020-01-01', 'position': str(self.position.id),
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('past', resp.data['message'].lower())

    def test_create_rejects_unknown_position(self):
        resp = self.client.post(reverse('hire-action-list'), {
            'reason': 'new_position', 'effective_from': _tomorrow_iso(),
            'position': '00000000-0000-0000-0000-000000000000',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_denied_without_permission(self):
        no_perm_user = make_user('noperm@test.com', role=self.plain_role, password='TestPass123!')
        self.client.force_authenticate(user=no_perm_user)
        resp = self.client.post(reverse('hire-action-list'), {
            'reason': 'new_position', 'effective_from': _tomorrow_iso(), 'position': str(self.position.id),
        }, format='json')
        self.assertEqual(resp.status_code, 403)


class EmploymentTypeReservationTests(HireWizardTestCase):
    def test_setting_employment_type_reserves_employee_number(self):
        action = self._create_draft()
        action = self._set_employment_type(action, 'Permanent')
        self.assertTrue(action.reserved_employee_id)

    def test_employment_type_can_be_corrected_before_completion(self):
        # QA report #32 — employment type used to lock permanently after
        # the first selection, with no way to fix a typo/misclick short of
        # discarding the whole draft. Re-selecting now re-reserves a number
        # against the new type's own series (the old number is simply left
        # unused, not reused — see the PATCH handler's own comment).
        action = self._create_draft()
        action = self._set_employment_type(action, 'Permanent')
        first_id = action.reserved_employee_id

        resp = self._patch(action, {'employment_type': 'Contract'})
        self.assertEqual(resp.status_code, 200, resp.data)
        action.refresh_from_db()
        self.assertEqual(action.employment_type, 'Contract')
        self.assertTrue(action.reserved_employee_id)
        # Each employment type has its own independent number series, so a
        # freshly-reserved Contract number can coincidentally format the
        # same as the first Permanent number (both start their own
        # sequence at 1) — what actually matters is that it came from the
        # Contract series, not that the Permanent series was rolled back.
        contract_series = EmployeeCodeSeries.objects.get(employment_type='Contract')
        self.assertEqual(contract_series.next_sequence, 2)
        permanent_series = EmployeeCodeSeries.objects.get(employment_type='Permanent')
        self.assertEqual(permanent_series.next_sequence, 2)
        self.assertTrue(first_id)


class DocumentUploadTests(HireWizardTestCase):
    def setUp(self):
        super().setUp()
        self.action = self._create_draft()

    def test_valid_upload_succeeds(self):
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': _png_file('pan.png')},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(HireActionDocument.objects.filter(hire_action=self.action).count(), 1)

    def test_upload_rejects_file_below_minimum_size(self):
        tiny = SimpleUploadedFile('tiny.png', b'\x89PNG\r\n\x1a\n' + b'x' * 10, content_type='image/png')
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': tiny}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_oversized_file(self):
        big = SimpleUploadedFile('big.png', _VALID_PNG[:8] + b'\x00' * (6 * 1024 * 1024), content_type='image/png')
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': big}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_disguised_non_image_as_image(self):
        fake = SimpleUploadedFile('fake.png', b'not actually a png' * 200, content_type='image/png')
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': fake}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_unknown_document_type(self):
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'not_a_real_type', 'file': _png_file('x.png')}, format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_same_file_rejected_across_two_different_types(self):
        resp1 = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': _png_file('pan.png')}, format='multipart',
        )
        self.assertEqual(resp1.status_code, 201)
        resp2 = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'aadhaar_card', 'file': _png_file('aadhaar.png')}, format='multipart',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('already uploaded', resp2.data['message'].lower())

    def test_reupload_same_type_replaces_previous_file(self):
        first = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': _png_file('pan1.png', _VALID_PNG)},
            format='multipart',
        )
        second_bytes = _VALID_PNG + b'\x01'
        second = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': _png_file('pan2.png', second_bytes)},
            format='multipart',
        )
        self.assertEqual(second.status_code, 201, second.data)
        docs = HireActionDocument.objects.filter(hire_action=self.action, document_type='pan_card')
        self.assertEqual(docs.count(), 1)
        self.assertEqual(docs.first().file_name, 'pan2.png')

    def test_per_entry_certificates_are_independent(self):
        cert_a = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'degree_certificate', 'entry_ref': 'temp-1', 'file': _png_file('a.png', _VALID_PNG + b'\x01')},
            format='multipart',
        )
        cert_b = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'degree_certificate', 'entry_ref': 'temp-2', 'file': _png_file('b.png', _VALID_PNG + b'\x02')},
            format='multipart',
        )
        self.assertEqual(cert_a.status_code, 201, cert_a.data)
        self.assertEqual(cert_b.status_code, 201, cert_b.data)
        self.assertEqual(
            HireActionDocument.objects.filter(hire_action=self.action, document_type='degree_certificate').count(), 2,
        )
        # Replacing entry temp-1's certificate must not touch temp-2's.
        replace_a = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'degree_certificate', 'entry_ref': 'temp-1', 'file': _png_file('a2.png', _VALID_PNG + b'\x03')},
            format='multipart',
        )
        self.assertEqual(replace_a.status_code, 201, replace_a.data)
        remaining_refs = set(
            HireActionDocument.objects.filter(hire_action=self.action, document_type='degree_certificate')
            .values_list('entry_ref', flat=True),
        )
        self.assertEqual(remaining_refs, {'temp-1', 'temp-2'})

    def test_delete_removes_document(self):
        resp = self.client.post(
            reverse('hire-action-document-list', args=[self.action.id]),
            {'document_type': 'pan_card', 'file': _png_file('pan.png')}, format='multipart',
        )
        doc_id = resp.data['data']['id']
        del_resp = self.client.delete(reverse('hire-action-document-detail', args=[self.action.id, doc_id]))
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(HireActionDocument.objects.filter(pk=doc_id).exists())


class HireCompletionRequiredFieldTests(HireWizardTestCase):
    """Regression tests for the "fake completion gate" bug — every one of
    these must currently return 400, not create a User."""

    def setUp(self):
        super().setUp()
        self.action = self._create_draft()
        self._set_employment_type(self.action, 'Permanent')

    def _complete_with(self, draft_overrides: dict, upload_required_docs: bool = True):
        draft = self._valid_full_draft()
        draft.update(draft_overrides)
        self._patch(self.action, draft)
        if upload_required_docs:
            self._upload_all_required_docs(self.action)
        return self._complete(self.action)

    def test_fully_valid_draft_succeeds(self):
        resp = self._complete_with({})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, HireAction.STATUS_COMPLETED)
        self.assertIsNotNone(self.action.created_employee_id)

    def test_missing_first_name_blocks_hire(self):
        resp = self._complete_with({'first_name': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertIsNone(HireAction.objects.get(pk=self.action.id).created_employee_id)

    def test_missing_date_of_birth_blocks_hire(self):
        resp = self._complete_with({'date_of_birth': ''})
        self.assertEqual(resp.status_code, 400)

    def test_missing_gender_blocks_hire(self):
        resp = self._complete_with({'gender': ''})
        self.assertEqual(resp.status_code, 400)

    def test_missing_phone_blocks_hire(self):
        resp = self._complete_with({'phone': ''})
        self.assertEqual(resp.status_code, 400)

    def test_missing_pan_blocks_hire(self):
        resp = self._complete_with({'pan_number': ''})
        self.assertEqual(resp.status_code, 400)

    def test_malformed_pan_blocks_hire(self):
        resp = self._complete_with({'pan_number': 'NOTAPAN'})
        self.assertEqual(resp.status_code, 400)

    def test_short_aadhaar_blocks_hire(self):
        resp = self._complete_with({'aadhaar_number': '123'})
        self.assertEqual(resp.status_code, 400)

    def test_missing_bank_account_blocks_hire(self):
        resp = self._complete_with({'account_number': ''})
        self.assertEqual(resp.status_code, 400)

    def test_malformed_ifsc_blocks_hire(self):
        resp = self._complete_with({'ifsc_code': 'BADCODE'})
        self.assertEqual(resp.status_code, 400)

    def test_missing_required_documents_blocks_hire(self):
        resp = self._complete_with({}, upload_required_docs=False)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('pan card', resp.data['message'].lower())

    def test_negative_ctc_blocks_hire(self):
        resp = self._complete_with({'annual_ctc': '-50000'})
        self.assertEqual(resp.status_code, 400)

    def test_zero_ctc_blocks_hire(self):
        resp = self._complete_with({'annual_ctc': '0'})
        self.assertEqual(resp.status_code, 400)

    def test_blank_ctc_is_allowed(self):
        # CTC is genuinely optional at hire time — only rejected when
        # present and invalid, never required outright.
        resp = self._complete_with({'annual_ctc': ''})
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_positive_ctc_completes_and_creates_salary_config(self):
        # Regression: _assign_salary_and_tax() used to pass draft_data's
        # annual_ctc straight through as a plain str into
        # EmployeeSalaryConfig.objects.create() instead of casting it to
        # Decimal — the in-memory instance was still that str the moment
        # post_save fired, which crashed
        # notifications.signals._on_salary_config_created's f'{...:,.0f}'
        # format spec with "Unknown format code 'f' for object of type
        # 'str'", a 500 on every hire completion that actually set a CTC.
        # None of the other CTC tests above exercise this — they use
        # negative/zero/blank values, all of which skip the create() call
        # entirely.
        from apps.payroll.models import EmployeeSalaryConfig
        resp = self._complete_with({'annual_ctc': '600000'})
        self.assertEqual(resp.status_code, 201, resp.data)
        config = EmployeeSalaryConfig.objects.get(employee_id=resp.data['data']['created_employee'])
        self.assertEqual(config.annual_ctc, 600000)

    def test_nominee_shares_over_100_percent_blocks_hire(self):
        resp = self._complete_with({
            'nominee_entries': [
                {'scheme': 'epf_eps', 'share_percentage': 60},
                {'scheme': 'epf_eps', 'share_percentage': 60},
            ],
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn('100%', resp.data['message'])

    def test_nominee_shares_exactly_100_percent_allowed(self):
        resp = self._complete_with({
            'nominee_entries': [
                {'scheme': 'epf_eps', 'share_percentage': 60},
                {'scheme': 'epf_eps', 'share_percentage': 40},
            ],
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_completing_without_employment_type_blocks_hire(self):
        fresh = self._create_draft()  # employment_type never set
        draft = self._valid_full_draft()
        self._patch(fresh, draft)
        self._upload_all_required_docs(fresh)
        resp = self._complete(fresh)
        self.assertEqual(resp.status_code, 400)

    def test_already_completed_action_cannot_be_completed_again(self):
        first = self._complete_with({})
        self.assertEqual(first.status_code, 201)
        second = self._complete(self.action)
        self.assertEqual(second.status_code, 404)

    def test_duplicate_email_blocks_hire(self):
        make_user('arjun.mehta@test.com', role=self.plain_role, password='TestPass123!')
        resp = self._complete_with({})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', resp.data['message'].lower())

    def test_system_admin_role_cannot_be_assigned_via_hire(self):
        admin_role = make_role('system_admin_test', permission_codenames=['settings.edit'])
        resp = self._complete_with({'role': str(admin_role.id)})
        self.assertEqual(resp.status_code, 400)


class HireCompletionSideEffectTests(HireWizardTestCase):
    """Once a hire genuinely succeeds, confirm the follow-on effects the
    wizard promises actually happened — not just a 201 status code."""

    def setUp(self):
        super().setUp()
        self.action = self._create_draft()
        self._set_employment_type(self.action, 'Permanent')
        draft = self._valid_full_draft()
        self._patch(self.action, draft)
        self._upload_all_required_docs(self.action)

    def test_documents_are_copied_to_real_employee_and_cleaned_up(self):
        resp = self._complete(self.action)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.action.refresh_from_db()
        employee = self.action.created_employee
        from apps.accounts.models import EmployeeDocument
        self.assertTrue(EmployeeDocument.objects.filter(user=employee).exists())
        # Temporary hire-action-scoped rows are gone once copied.
        self.assertFalse(HireActionDocument.objects.filter(hire_action=self.action).exists())

    def test_created_employee_has_reserved_employee_id(self):
        resp = self._complete(self.action)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.action.refresh_from_db()
        self.assertEqual(self.action.created_employee.employee_id, self.action.reserved_employee_id)


class HireActionEmailValidationTests(HireWizardTestCase):
    """QA report #31 — 'bad-email' was accepted and saved via a direct PATCH
    to the draft, bypassing the wizard's own client-side EMAIL_RE check.
    Server-side format validation on every email-shaped draft_data field."""

    def setUp(self):
        super().setUp()
        self.action = self._create_draft()

    def test_invalid_work_email_rejected(self):
        resp = self._patch(self.action, {'work_email': 'bad-email'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.action.refresh_from_db()
        self.assertNotIn('work_email', self.action.draft_data)

    def test_invalid_personal_email_rejected(self):
        resp = self._patch(self.action, {'email': 'not-an-email'})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_valid_work_email_accepted(self):
        resp = self._patch(self.action, {'work_email': 'new.hire@company.example'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.action.refresh_from_db()
        self.assertEqual(self.action.draft_data['work_email'], 'new.hire@company.example')
