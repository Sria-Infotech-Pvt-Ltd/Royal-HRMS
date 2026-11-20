"""The numbers in a leave policy's note follow the settings: change "Maximum consecutive days" to 5 and the note no longer says 3."""
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.hrms.models import LeavePolicy
from apps.hrms.services_leave_policy_note import CONSECUTIVE, NOTICE, sync_note_numbers


def sync(note, **settings):
    values = dict(maximum_consecutive_days=0, minimum_notice_period=0, can_carry_forward=False, max_carry_forward_days=0)
    values.update(settings)
    return sync_note_numbers(note, **values)


class SyncNoteNumbersTests(SimpleTestCase):
    def test_consecutive_days_follow_the_setting(self):
        self.assertEqual(sync('Max 3 consecutive days. Apply 1 day in advance.', maximum_consecutive_days=5, minimum_notice_period=1),
                         'Max 5 consecutive days. Apply 1 day in advance.')

    def test_notice_follows_the_setting_and_day_becomes_days(self):
        self.assertEqual(sync('Max 3 consecutive days. Apply 1 day in advance.', maximum_consecutive_days=3, minimum_notice_period=2),
                         'Max 3 consecutive days. Apply 2 days in advance.')
        self.assertEqual(sync('Min 3 days notice. Carry-forward up to 30 days.', minimum_notice_period=1, can_carry_forward=True, max_carry_forward_days=30),
                         'Min 1 day notice. Carry-forward up to 30 days.')

    def test_carry_forward_limit_follows_the_setting(self):
        self.assertEqual(sync('Min 3 days notice. Carry-forward up to 30 days.', minimum_notice_period=3, can_carry_forward=True, max_carry_forward_days=45),
                         'Min 3 days notice. Carry-forward up to 45 days.')

    def test_only_the_changed_setting_is_rewritten(self):
        note = 'Max 3 consecutive days. Apply 1 day in advance.'
        self.assertEqual(sync(note, maximum_consecutive_days=9, minimum_notice_period=7, only=frozenset({CONSECUTIVE})), 'Max 9 consecutive days. Apply 1 day in advance.')
        self.assertEqual(sync(note, maximum_consecutive_days=9, minimum_notice_period=7, only=frozenset({NOTICE})), 'Max 3 consecutive days. Apply 7 days in advance.')

    def test_other_numbers_and_text_are_never_touched(self):
        for note in ("Within 15 days of child's birth. Birth certificate required.", 'Medical certificate required for 3+ consecutive days.',
                     'For the loss of an immediate family member.', ''):
            self.assertEqual(sync(note, maximum_consecutive_days=5, minimum_notice_period=5, can_carry_forward=True, max_carry_forward_days=9), note)

    def test_a_zero_or_switched_off_setting_leaves_its_phrase_alone(self):
        self.assertEqual(sync('Max 3 consecutive days.', maximum_consecutive_days=0), 'Max 3 consecutive days.')
        self.assertEqual(sync('Carry-forward up to 30 days.', can_carry_forward=False, max_carry_forward_days=30), 'Carry-forward up to 30 days.')


class SavingAPolicyKeepsItsNoteInStepTests(TestCase):
    def setUp(self):
        cache.clear()
        admin = make_user('note-sync-admin@test.com', make_role('r_notesync', permission_codenames=['settings.edit']), full_name='Admin',
                          employee_id='NS1', onboarding_status=User.ONBOARDING_COMPLETE)
        self.client = APIClient()
        self.client.force_authenticate(user=admin)
        self.policy, _ = LeavePolicy.objects.update_or_create(
            leave_type='casual',
            defaults=dict(annual_days=12, maximum_consecutive_days=3, minimum_notice_period=1, policy_note='Max 3 consecutive days. Apply 1 day in advance.'),
        )

    def put(self, **payload):
        response = self.client.put('/api/leave/policy/casual/', payload, format='json')
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.policy.refresh_from_db()
        return response

    def test_changing_the_consecutive_limit_updates_the_note_the_list_shows(self):
        response = self.put(maximum_consecutive_days=5)
        self.assertEqual(self.policy.policy_note, 'Max 5 consecutive days. Apply 1 day in advance.')
        self.assertEqual(response.data['data']['policy_note'], 'Max 5 consecutive days. Apply 1 day in advance.')

    def test_saving_something_else_leaves_the_note_alone(self):
        self.put(annual_days=14)
        self.assertEqual(self.policy.policy_note, 'Max 3 consecutive days. Apply 1 day in advance.')

    def test_a_note_hr_just_typed_is_kept_when_no_limit_changed(self):
        self.put(policy_note='Max 3 consecutive days. Talk to your manager first.')
        self.assertEqual(self.policy.policy_note, 'Max 3 consecutive days. Talk to your manager first.')
