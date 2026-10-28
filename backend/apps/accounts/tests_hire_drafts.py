"""UAT-037: Discard really discards, gives the reserved employee number back when safe, stale drafts expire, and leftovers are reported for a person to approve."""
import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, EmployeeCodeSeries, HireAction, OrgUnit, Position
from apps.accounts.services_hire_drafts import existing_employee_match, expire_stale_drafts


class HireDraftTests(TestCase):
    def setUp(self):
        role = make_role('hr_drafts_test', permission_codenames=['employees.create'])
        self.hr_user = make_user('hr-drafts@test.com', role=role)
        unit = OrgUnit.objects.create(name='Engineering')
        self.position = Position.objects.create(org_unit=unit, title='Software Engineer', grade='L2')
        self.client = APIClient()
        self.client.force_authenticate(user=self.hr_user)

    def _draft(self, employment_type='Permanent', **draft_data):
        action = HireAction.objects.create(
            reason=HireAction.REASON_NEW_POSITION, effective_from=datetime.date.today(), position=self.position,
            created_by=self.hr_user, draft_data=draft_data,
        )
        if employment_type:
            response = self.client.patch(reverse('hire-action-detail', args=[action.pk]), {'employment_type': employment_type}, format='json')
            self.assertEqual(response.status_code, 200, response.json())
            action.refresh_from_db()
        return action

    def _listing(self):
        return self.client.get(reverse('hire-action-list')).json()['data']

    # ---- Discard ----
    def test_discard_removes_the_draft_from_the_list_and_is_audited(self):
        action = self._draft()
        self.assertEqual([row['id'] for row in self._listing()], [str(action.pk)])
        response = self.client.delete(reverse('hire-action-detail', args=[action.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._listing(), [])
        action.refresh_from_db()
        self.assertEqual(action.status, HireAction.STATUS_DISCARDED)
        self.assertEqual(AuditLog.objects.filter(action='hire_draft_discarded', object_id=str(action.pk)).count(), 1)

    def test_discarding_the_newest_reserved_number_releases_it(self):
        action = self._draft()
        reserved = action.reserved_employee_id
        self.assertTrue(reserved)
        series = EmployeeCodeSeries.objects.get(employment_type='Permanent')
        before = series.next_sequence
        self.assertTrue(self.client.delete(reverse('hire-action-detail', args=[action.pk])).json()['data']['number_released'])
        series.refresh_from_db()
        self.assertEqual(series.next_sequence, before - 1)
        action.refresh_from_db()
        self.assertEqual(action.reserved_employee_id, '')
        # ...so the next draft is offered the same number again, not a gap.
        self.assertEqual(self._draft().reserved_employee_id, reserved)

    def test_an_older_number_is_left_as_a_gap_not_reused(self):
        first = self._draft()
        second = self._draft()
        series = EmployeeCodeSeries.objects.get(employment_type='Permanent')
        before = series.next_sequence
        self.assertFalse(self.client.delete(reverse('hire-action-detail', args=[first.pk])).json()['data']['number_released'])
        series.refresh_from_db()
        self.assertEqual(series.next_sequence, before)
        second.refresh_from_db()
        self.assertTrue(second.reserved_employee_id)  # the other draft keeps its own number

    def test_list_shows_exactly_the_number_the_draft_holds(self):
        with_number = self._draft()
        without_number = self._draft(employment_type='')
        rows = {row['id']: row for row in self._listing()}
        self.assertEqual(rows[str(with_number.pk)]['reserved_employee_id'], with_number.reserved_employee_id)
        self.assertEqual(rows[str(without_number.pk)]['reserved_employee_id'], '')

    # ---- Expiry ----
    def test_stale_drafts_expire_and_fresh_ones_stay(self):
        stale, fresh = self._draft(), self._draft()
        HireAction.objects.filter(pk=stale.pk).update(updated_at=timezone.now() - datetime.timedelta(days=45))
        self.assertEqual(expire_stale_drafts(), 1)
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale.status, HireAction.STATUS_DISCARDED)
        self.assertEqual(fresh.status, HireAction.STATUS_DRAFT)
        self.assertTrue(AuditLog.objects.filter(action='hire_draft_expired', object_id=str(stale.pk)).exists())

    # ---- Leftovers that match an existing employee ----
    def test_a_draft_for_an_existing_employee_is_flagged_by_email_or_mobile(self):
        make_user('already.here@test.com', employee_id='EMPEXIST01', phone='+91 98765 43210')
        by_email = self._draft(employment_type='', email='Already.Here@test.com')
        by_mobile = self._draft(employment_type='', phone='9876543210')
        clean = self._draft(employment_type='', email='someone.new@test.com', phone='9123456789')
        self.assertEqual(existing_employee_match(by_email), 'email matches an existing employee')
        self.assertEqual(existing_employee_match(by_mobile), 'mobile matches an existing employee')
        self.assertEqual(existing_employee_match(clean), '')
        flagged = {row['id']: row['existing_employee_match'] for row in self._listing()}
        self.assertTrue(flagged[str(by_email.pk)])
        self.assertEqual(flagged[str(clean.pk)], '')

    def test_cleanup_command_dry_run_changes_nothing_and_apply_needs_approved_ids(self):
        make_user('already.here@test.com', employee_id='EMPEXIST01')
        leftover = self._draft(employment_type='', email='already.here@test.com')
        out = StringIO()
        call_command('cleanup_hire_drafts', stdout=out)
        self.assertIn(str(leftover.pk), out.getvalue())
        self.assertIn('DRY RUN', out.getvalue())
        leftover.refresh_from_db()
        self.assertEqual(leftover.status, HireAction.STATUS_DRAFT)

        with self.assertRaises(CommandError):
            call_command('cleanup_hire_drafts', apply=True, stdout=StringIO())

        call_command('cleanup_hire_drafts', apply=True, ids=str(leftover.pk), stdout=StringIO())
        leftover.refresh_from_db()
        self.assertEqual(leftover.status, HireAction.STATUS_DISCARDED)
