"""
Hire draft autosave: a draft saves every valid field, and only completing the hire enforces the final rules.

Background. The wizard autosaves the WHOLE form on every edit. The server used to refuse the entire request when any one
field failed a check, including "another open draft already uses this email". Two drafts sharing an email therefore locked
each other out permanently: nothing on any step could be saved, the wizard showed only "Autosave failed", and "Hire" then
failed with "company code required" because the company code had never been stored.

Now: valid fields are always saved; a field that cannot be saved comes back with its own message (and is left out of the
draft); a duplicate email/mobile is a warning on the draft. Completing the hire still blocks duplicates and missing fields.
"""
from __future__ import annotations

from apps.accounts.factories import make_user
from apps.accounts.models import HireAction, User
from apps.accounts.tests_hire_wizard import HireWizardTestCase

SHARED_EMAIL = 'shared.person@test.com'
DUPLICATE_DRAFT = 'Another open hire draft already uses this email.'
COMPANY_CODE_MESSAGE = 'First name, last name, email and company code are required before hiring.'


class TwoDraftsSharingAnEmailTests(HireWizardTestCase):
    def test_two_open_drafts_with_the_same_email_can_both_autosave_everything(self):
        first, second = self._create_draft(), self._create_draft()
        wizard_snapshot = {'email': SHARED_EMAIL, 'first_name': 'Sam', 'last_name': 'Rao', 'branch': 'Kondapur Office'}

        saved_first = self._patch(first, wizard_snapshot)
        saved_second = self._patch(second, wizard_snapshot)  # the wizard re-sends the email with every autosave
        self.assertEqual((saved_first.status_code, saved_second.status_code), (200, 200), saved_second.json())

        for draft in (first, second):
            draft.refresh_from_db()
            self.assertEqual(draft.draft_data, wizard_snapshot)
        self.assertIn(DUPLICATE_DRAFT, [w['message'] for w in saved_second.json()['data']['warnings']])

        # Later steps keep saving on BOTH drafts, even though each now sees the other.
        for draft in (first, second):
            later = self._patch(draft, {**wizard_snapshot, 'date_of_birth': '1991-03-04', 'pan_number': 'ABCDE1234F'})
            self.assertEqual(later.status_code, 200, later.json())
            draft.refresh_from_db()
            self.assertEqual(draft.draft_data['pan_number'], 'ABCDE1234F')

    def test_a_duplicate_email_still_blocks_completing_the_hire(self):
        first, second = self._create_draft(), self._create_draft()
        for draft in (first, second):
            self._set_employment_type(draft)
            self.assertEqual(self._patch(draft, {**self._valid_full_draft(), 'email': SHARED_EMAIL}).status_code, 200)

        refused = self._complete(first)
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()['message'], DUPLICATE_DRAFT)
        self.assertEqual(refused.json()['data']['email'], DUPLICATE_DRAFT)
        first.refresh_from_db()
        self.assertEqual(first.status, HireAction.STATUS_DRAFT)
        self.assertFalse(User.objects.filter(email=SHARED_EMAIL).exists())

    def test_an_existing_employees_email_is_saved_with_a_warning_but_blocks_completion(self):
        make_user('already.employed@test.com', employee_id='EMPAUTO01', onboarding_status='complete')
        draft = self._set_employment_type(self._create_draft())

        saved = self._patch(draft, {**self._valid_full_draft(), 'email': 'already.employed@test.com'})
        self.assertEqual(saved.status_code, 200, saved.json())
        self.assertEqual(saved.json()['data']['warnings'][0]['severity'], 'error')
        draft.refresh_from_db()
        self.assertEqual(draft.draft_data['email'], 'already.employed@test.com')

        refused = self._complete(draft)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('EMPAUTO01', refused.json()['message'])


class InvalidFieldDoesNotBlockTheRestTests(HireWizardTestCase):
    def test_invalid_fields_are_reported_one_by_one_and_every_valid_field_is_still_saved(self):
        draft = self._create_draft()
        response = self._patch(draft, {
            'first_name': 'Priya', 'last_name': 'Nair', 'branch': 'Kondapur Office', 'date_of_birth': '1992-02-02',
            'email': 'not-an-email', 'uan_number': '123', 'phone': '12',
        })
        self.assertEqual(response.status_code, 400)
        body = response.json()['data']
        self.assertEqual(body['email'], 'Enter a valid email address.')
        self.assertEqual(body['uan_number'], 'UAN must be 12 digits')
        self.assertTrue(body['phone'])  # the mobile rule's own message
        self.assertEqual(body['saved_fields'], ['branch', 'date_of_birth', 'first_name', 'last_name'])

        draft.refresh_from_db()
        self.assertEqual(draft.draft_data, {
            'first_name': 'Priya', 'last_name': 'Nair', 'branch': 'Kondapur Office', 'date_of_birth': '1992-02-02',
        })  # the three bad values were NOT stored

    def test_a_later_bad_value_never_overwrites_an_earlier_good_one(self):
        draft = self._create_draft()
        self.assertEqual(self._patch(draft, {'email': 'good.person@test.com', 'uan_number': '123456789012'}).status_code, 200)
        self.assertEqual(self._patch(draft, {'email': 'half-typed@', 'uan_number': '12345', 'first_name': 'Kept'}).status_code, 400)
        draft.refresh_from_db()
        self.assertEqual(draft.draft_data, {'email': 'good.person@test.com', 'uan_number': '123456789012', 'first_name': 'Kept'})

    def test_an_invalid_employment_type_does_not_stop_other_fields_saving(self):
        draft = self._create_draft()
        response = self._patch(draft, {'employment_type': 'Astronaut', 'first_name': 'Meera'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['data']['employment_type'], 'Select a valid employment type.')
        draft.refresh_from_db()
        self.assertEqual((draft.employment_type, draft.draft_data), ('', {'first_name': 'Meera'}))

    def test_the_rejected_field_names_are_logged_but_never_their_values(self):
        draft = self._create_draft()
        with self.assertLogs('apps.accounts.views_hire', level='WARNING') as logged:
            self._patch(draft, {'email': 'private.value@', 'first_name': 'Ok'})
        text = '\n'.join(logged.output)
        self.assertIn('email', text)
        self.assertNotIn('private.value', text)


class CompletionStillEnforcesTheRulesTests(HireWizardTestCase):
    def test_each_required_identity_field_is_still_enforced_at_completion(self):
        for missing in ('first_name', 'last_name', 'email', 'branch'):
            with self.subTest(missing=missing):
                draft = self._set_employment_type(self._create_draft())
                fields = {**self._valid_full_draft(), 'email': f'req.{missing}@test.com'}
                fields.pop(missing)
                self.assertEqual(self._patch(draft, fields).status_code, 200)
                refused = self._complete(draft)
                self.assertEqual(refused.status_code, 400)
                self.assertEqual(refused.json()['message'], COMPANY_CODE_MESSAGE)
                draft.refresh_from_db()
                self.assertEqual(draft.status, HireAction.STATUS_DRAFT)

    def test_a_draft_that_saved_cleanly_is_still_held_back_by_the_other_hire_requirements(self):
        draft = self._set_employment_type(self._create_draft())
        self.assertEqual(self._patch(draft, self._valid_full_draft()).status_code, 200)
        refused = self._complete(draft)  # no documents uploaded
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Complete these before hiring', refused.json()['message'])

    def test_an_employment_type_is_still_required_before_hiring(self):
        draft = self._create_draft()
        self.assertEqual(self._patch(draft, self._valid_full_draft()).status_code, 200)
        refused = self._complete(draft)
        self.assertEqual(refused.status_code, 400)
        self.assertIn('Employment type', refused.json()['message'])
