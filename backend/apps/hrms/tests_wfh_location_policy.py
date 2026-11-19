"""Allow (or stop allowing) punching from any location on a work-from-home request."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog, User
from apps.attendance.services_geofencing import GeofencingService
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, REQ_REJECTED, WorkFromHomeRequest

HOME = (Decimal('17.385044'), Decimal('78.486671'))        # the declared spot
NEAR = (17.3855, 78.4870)                                   # a few dozen metres away
FAR = (17.5500, 78.6000)                                    # many kilometres away: another village


def make_approver(email, code, **flags):
    return make_user(email, make_role(f'r_{code}', permission_codenames=['wfh.approve'], **flags), full_name=code, employee_id=code, branch='Hyderabad',
                     onboarding_status=User.ONBOARDING_COMPLETE)


class WfhLocationPolicyTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.manager = make_approver('wp-mgr@test.com', 'WPM1', can_manage_team=True)
        self.hr = make_approver('wp-hr@test.com', 'WPH1')
        self.employee = make_user('wp-emp@test.com', full_name='Guru Emp', employee_id='WPE1', branch='Hyderabad',
                                  reporting_manager=self.manager, onboarding_status=User.ONBOARDING_COMPLETE)
        self.request_obj = WorkFromHomeRequest.objects.create(
            employee=self.employee, start_date=today - timedelta(days=1), end_date=today + timedelta(days=3), reason='r',
            location_label='Home', latitude=HOME[0], longitude=HOME[1], status=REQ_APPROVED, l1_approver=self.manager, l2_approver=self.hr,
        )

    def _check(self, point, accuracy=None):
        return GeofencingService.validate(employee=self.employee, attendance_mode='wfh', employee_lat=point[0], employee_lon=point[1], employee_accuracy=accuracy)

    def _post(self, user, allow, request_id=None):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.post(reverse('wfh-request-location-policy', args=[request_id or self.request_obj.id]), {'allow_any_location': allow}, format='json')

    # ── the punch check ──────────────────────────────────────────────────────────────────────────
    def test_by_default_a_punch_must_be_near_the_declared_location(self):
        self.assertTrue(self.request_obj.enforce_location)
        self.assertTrue(self._check(NEAR).is_allowed)
        far = self._check(FAR)
        self.assertFalse(far.is_allowed)
        self.assertIn('ask your manager or HR', far.rejection_message)

    def test_once_allowed_a_punch_from_another_village_is_accepted_and_the_distance_is_still_recorded(self):
        self.request_obj.enforce_location = False
        self.request_obj.save()
        result = self._check(FAR)
        self.assertTrue(result.is_allowed)
        self.assertIsNone(result.is_inside_geofence)         # recorded, not judged
        self.assertGreater(result.calculated_distance, 10_000)
        self.assertEqual(result.wfh_request.pk, self.request_obj.pk)

    def test_once_allowed_a_missing_gps_reading_does_not_block_the_punch(self):
        self.request_obj.enforce_location = False
        self.request_obj.save()
        result = GeofencingService.validate(employee=self.employee, attendance_mode='wfh', employee_lat=None, employee_lon=None)
        self.assertTrue(result.is_allowed)
        self.assertIsNone(result.calculated_distance)

    def test_the_approved_dates_still_apply(self):
        self.request_obj.enforce_location = False
        self.request_obj.end_date = timezone.localdate() - timedelta(days=1)
        self.request_obj.save()
        result = self._check(FAR)
        self.assertFalse(result.is_allowed)                    # no approved request covers today any more

    # ── who may change it ────────────────────────────────────────────────────────────────────────
    def test_the_reporting_manager_can_allow_and_then_stop_it(self):
        allowed = self._post(self.manager, True)
        self.assertEqual(allowed.status_code, 200, allowed.data)
        data = allowed.data['data']
        self.assertFalse(data['enforce_location'])
        self.assertEqual(data['location_unlocked_by_name'], 'WPM1')
        self.assertTrue(data['can_set_location_policy'])
        self.request_obj.refresh_from_db()
        self.assertFalse(self.request_obj.enforce_location)
        self.assertEqual(self.request_obj.location_unlocked_by_id, self.manager.id)
        self.assertTrue(self._check(FAR).is_allowed)

        stopped = self._post(self.manager, False)
        self.assertEqual(stopped.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertTrue(self.request_obj.enforce_location)
        self.assertIsNone(self.request_obj.location_unlocked_by_id)
        self.assertFalse(self._check(FAR).is_allowed)

    def test_the_hr_approver_can_too_and_every_change_is_audited(self):
        self.assertEqual(self._post(self.hr, True).status_code, 200)
        self.assertEqual(self._post(self.hr, False).status_code, 200)
        actions = list(AuditLog.objects.filter(object_id=str(self.request_obj.id), module='wfh').order_by('created_at').values_list('action', flat=True))
        self.assertEqual(actions, ['wfh_location_unlocked', 'wfh_location_locked'])
        entry = AuditLog.objects.filter(action='wfh_location_unlocked').first()
        self.assertEqual(entry.changes['allow_any_location'], True)
        self.assertEqual(entry.changes['employee_id'], 'WPE1')

    def test_a_full_admin_can(self):
        admin = make_user('wp-admin@test.com', make_role('r_wpadmin', permission_codenames=['wfh.approve', 'settings.edit']),
                          full_name='Admin', employee_id='WPA1', onboarding_status=User.ONBOARDING_COMPLETE)
        self.assertEqual(self._post(admin, True).status_code, 200)

    def test_nobody_else_can(self):
        other_manager = make_approver('wp-other@test.com', 'WPM2', can_manage_team=True)
        self.assertEqual(self._post(other_manager, True).status_code, 403)       # an approver, but not this request's
        no_permission = make_user('wp-plain@test.com', make_role('r_wpplain'), full_name='Plain', employee_id='WPP1', onboarding_status=User.ONBOARDING_COMPLETE)
        self.assertEqual(self._post(no_permission, True).status_code, 403)
        self.assertEqual(self._post(self.employee, True).status_code, 403)       # the employee cannot lift their own check
        self.request_obj.refresh_from_db()
        self.assertTrue(self.request_obj.enforce_location)
        self.assertEqual(AuditLog.objects.filter(module='wfh', action__startswith='wfh_location').count(), 0)

    def test_an_approver_cannot_change_their_own_request(self):
        own = WorkFromHomeRequest.objects.create(
            employee=self.manager, start_date=timezone.localdate(), end_date=timezone.localdate(), reason='r', latitude=HOME[0], longitude=HOME[1],
            status=REQ_APPROVED, l2_approver=self.hr,
        )
        self.assertEqual(self._post(self.manager, True, own.id).status_code, 403)

    def test_only_open_or_approved_requests_can_change(self):
        self.request_obj.status = REQ_REJECTED
        self.request_obj.save()
        self.assertEqual(self._post(self.manager, True).status_code, 400)
        self.request_obj.status = REQ_PENDING
        self.request_obj.save()
        self.assertEqual(self._post(self.manager, True).status_code, 200)

    def test_bad_requests(self):
        client = APIClient()
        client.force_authenticate(user=self.manager)
        url = reverse('wfh-request-location-policy', args=[self.request_obj.id])
        for body in ({}, {'allow_any_location': 'yes'}, {'allow_any_location': 1}, {'allow_any_location': None}):
            self.assertEqual(client.post(url, body, format='json').status_code, 400, body)
        self.assertEqual(self._post(self.manager, True, 'not-a-uuid').status_code, 404)
        self.assertEqual(self._post(self.manager, True, '00000000-0000-0000-0000-000000000000').status_code, 404)

    def test_the_employee_sees_the_setting_but_cannot_change_it(self):
        self._post(self.manager, True)
        client = APIClient()
        client.force_authenticate(user=self.employee)
        rows = client.get(reverse('wfh-request-list')).data['data']['results']
        row = next(entry for entry in rows if entry['id'] == str(self.request_obj.id))
        self.assertFalse(row['enforce_location'])
        self.assertFalse(row['can_set_location_policy'])
