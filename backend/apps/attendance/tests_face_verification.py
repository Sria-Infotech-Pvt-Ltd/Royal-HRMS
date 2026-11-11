"""
Tests for face verification at punch time (PunchService.record_punch calling
FaceVerificationService) and the employee's own status endpoint.

Split out of tests_face_registration.py (that file covers the enrollment/
approval workflow only) — see services_face_matching.py for the service
under test here.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.attendance.services_geofencing import (
    GPS_REQUIRED_MESSAGE,
    WFH_NO_APPROVED_REQUEST_MESSAGE,
)
from apps.hrms.models import REQ_APPROVED, WorkFromHomeRequest
from apps.attendance.models import (
    AttendanceFaceVerificationRules,
    AttendancePunch,
    AttendanceSettings,
    FaceRegistrationRequest,
    FaceVerificationAttempt,
)
from config.test_runner import TEST_COMPANY_CODE

# Every punch in this module uses a mode that has NO location rule. These
# tests are about face verification, not geofencing, and the geofence/WFH gate
# runs BEFORE the face check (see services_attendance.record_punch). 'wfh' used
# to be that "no location rule" mode, but it now requires an approved
# WorkFromHomeRequest plus a GPS point (commit 20909b3), so every 'wfh' punch
# here was rejected before reaching the face code. 'field' is validated by
# services_geofencing._validate_no_geofence ("never validated"), so a punch in
# this mode reaches face verification exactly as the tests intend.
PUNCH_MODE = 'field'


def _assert_reached_face_check(test_case, resp) -> None:
    """A rejection asserted as a FACE rejection must not actually be the
    geofence / work-from-home gate (which runs first) in disguise — that gap is
    what let these tests pass for the wrong reason."""
    message = str(resp.data.get('message', '')).lower()
    test_case.assertNotIn('work-from-home', message, resp.data)
    test_case.assertNotIn('work from home', message, resp.data)
    test_case.assertNotIn('outside', message, resp.data)
    test_case.assertNotIn('location', message, resp.data)


def _login(client: APIClient, email: str, password: str = 'TestPass123!'):
    resp = client.post(
        reverse('login'),
        {'company_code': TEST_COMPANY_CODE, 'email': email, 'password': password},
        format='json',
    )
    assert resp.status_code == 200, resp.data
    return resp


def _set_face_verification_mandatory(is_mandatory: bool) -> None:
    """Flips the org-wide toggle (Attendance Settings -> Face ID Verification)
    that FaceVerificationService.verify_for_punch and the HR register endpoint
    now gate on."""
    settings, _ = AttendanceSettings.objects.get_or_create(is_active=True)
    AttendanceFaceVerificationRules.objects.update_or_create(
        settings=settings, defaults={'is_mandatory': is_mandatory},
    )


# A 128-length vector (matching a real face-api.js descriptor's dimension),
# and a second vector far enough away to fail the FACE_MATCH_MAX_DISTANCE
# threshold — used to test both the match and mismatch paths.
REGISTERED_EMBEDDING = [0.01 * i for i in range(128)]
MATCHING_EMBEDDING   = [v + 0.001 for v in REGISTERED_EMBEDDING]   # tiny distance, well under 0.6
MISMATCHED_EMBEDDING = [v + 1.0 for v in REGISTERED_EMBEDDING]     # euclidean distance ~11.3, well over 0.6
# Both land inside the low-confidence band (distance within
# FACE_MATCH_LOW_CONFIDENCE_MARGIN of FACE_MATCH_MAX_DISTANCE=0.6) but are
# distinct vectors — a different embedding_fingerprint each, so submitting
# both in sequence exercises the step-up corroboration path without ever
# tripping anti-replay (that check only fires on a byte-identical embedding).
BORDERLINE_EMBEDDING_A = [v + 0.0503 for v in REGISTERED_EMBEDDING]  # distance ~0.569
BORDERLINE_EMBEDDING_B = [v + 0.0507 for v in REGISTERED_EMBEDDING]  # distance ~0.574


def _make_approved_request(employee) -> FaceRegistrationRequest:
    return FaceRegistrationRequest.objects.create(
        employee=employee,
        face_embedding=REGISTERED_EMBEDDING,
        liveness_passed=True,
        liveness_score=0.9,
        status=FaceRegistrationRequest.STATUS_APPROVED,
        is_active=True,
    )


class FaceVerificationPunchTests(TestCase):
    """
    Default (no explicit _set_face_verification_mandatory call): the org-wide
    toggle is unconfigured, which is_face_verification_mandatory() treats as
    off — matching the pre-toggle behaviour these "unaffected" tests exercise.
    Tests that verify the mandatory-enforcement path turn the toggle on
    explicitly, since that's now a precondition, not the default.
    """

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        role          = make_role('employee')
        self.employee = make_user('faceverify@test.com', role=role, password='TestPass123!')
        _login(self.client, 'faceverify@test.com')

    def tearDown(self):
        # Several tests here call _set_face_verification_mandatory(True),
        # which caches a real AttendanceSettings row — the DB write rolls
        # back with the test transaction, but the cache entry doesn't, so
        # without this it leaks a stale is_mandatory=True into whichever
        # test (in this file or, worse, an entirely unrelated module in the
        # same test run) reads AttendanceSettingsCacheService next.
        cache.clear()

    def _punch(self, **overrides):
        payload = {'punch_type': 'IN', 'attendance_mode': PUNCH_MODE}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def test_punch_without_registration_is_unaffected(self):
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertFalse(punch.face_verified)
        self.assertIsNone(punch.face_match_distance)

    def test_no_registration_is_rejected_when_mandatory(self):
        # Toggle on, no registration at all — the whole point of "mandatory":
        # you must register before you can punch, not just skip verification.
        _set_face_verification_mandatory(True)
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('mandatory', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_approved_registration_without_embedding_is_rejected(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_approved_registration_with_matching_embedding_succeeds(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(face_embedding=MATCHING_EMBEDDING)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertTrue(punch.face_verified)
        self.assertIsNotNone(punch.face_match_distance)
        self.assertLess(punch.face_match_distance, 0.6)

    def test_approved_registration_with_mismatched_embedding_is_rejected(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(face_embedding=MISMATCHED_EMBEDDING)
        self.assertEqual(resp.status_code, 403, resp.data)
        # FR-2: a clean mismatch message, not the old lighting-flavored
        # wording — see services_face_matching.py's _EMBEDDING_MISMATCH_MESSAGE.
        self.assertIn("couldn't match your face", resp.data['message'].lower())
        self.assertNotIn('lighting', resp.data['message'].lower())
        _assert_reached_face_check(self, resp)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())
        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        self.assertFalse(attempt.is_match)
        self.assertEqual(attempt.rejection_reason, FaceVerificationAttempt.REJECTION_MISMATCH)

    def test_pending_registration_does_not_require_verification_when_toggle_off(self):
        # Only an APPROVED request gates the punch — pending/rejected don't —
        # and here the org toggle is off anyway, so nobody is gated regardless.
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(AttendancePunch.objects.get(employee=self.employee).face_verified)

    def test_pending_registration_is_rejected_when_mandatory(self):
        # Toggle on: a pending (not yet approved) request doesn't satisfy
        # "mandatory" — same as having no registration at all.
        _set_face_verification_mandatory(True)
        FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING, liveness_passed=True,
        )
        resp = self._punch()
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('mandatory', resp.data['message'].lower())

    def test_voice_source_is_gated_the_same_as_web_when_mandatory(self):
        # Voice runs through the same browser tab as web (see AttendancePunch's
        # own docstring) — the voice-initiated clock-in conversation opens the
        # camera for its own "taking facial proof" turn (see apps.voice_commands.
        # conversation_clock_in_face) before ever reaching this endpoint with an
        # embedding attached, same as web. No embedding yet -> same rejection.
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(source='voice')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('face verification is required', resp.data['message'].lower())
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

    def test_voice_source_with_matching_embedding_succeeds(self):
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)
        resp = self._punch(source='voice', face_embedding=MATCHING_EMBEDDING)
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertTrue(punch.face_verified)

    def test_toggle_off_skips_verification_even_with_approved_registration(self):
        # The org toggle is the single source of truth: off means nobody is
        # asked to verify, even an employee approved while it was previously on.
        _set_face_verification_mandatory(False)
        _make_approved_request(self.employee)
        resp = self._punch()
        self.assertEqual(resp.status_code, 200, resp.data)
        punch = AttendancePunch.objects.get(employee=self.employee)
        self.assertFalse(punch.face_verified)


class FaceVerificationLowConfidenceFailClosedTests(TestCase):
    """A borderline-distance match (within FACE_MATCH_LOW_CONFIDENCE_MARGIN of
    FACE_MATCH_MAX_DISTANCE) is rejected outright, every time, with no way to
    turn it into an accept by retrying — see FACE_MATCH_LOW_CONFIDENCE_MARGIN's
    own docstring in services_face_matching.py for why an earlier version that
    accepted on a second corroborating capture didn't hold up against a real
    retest: the same impostor reproduced a borderline distance on 4 of 5
    captures, so a second draw barely changed the odds."""

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        role          = make_role('employee_low_conf')
        self.employee = make_user('lowconf@test.com', role=role, password='TestPass123!')
        _login(self.client, 'lowconf@test.com')
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)

    def tearDown(self):
        cache.clear()

    def _punch(self, **overrides):
        payload = {'punch_type': 'IN', 'attendance_mode': PUNCH_MODE}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def test_borderline_capture_is_rejected(self):
        resp = self._punch(face_embedding=BORDERLINE_EMBEDDING_A, capture_session_id='session-a')
        self.assertEqual(resp.status_code, 403, resp.data)
        _assert_reached_face_check(self, resp)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        # is_match=False on the row itself — this is a genuine rejection now,
        # not a "pending" match, so it counts toward the failed-attempt cap
        # like any other mismatch.
        self.assertFalse(attempt.is_match)
        self.assertEqual(attempt.rejection_reason, FaceVerificationAttempt.REJECTION_LOW_CONFIDENCE_PENDING)

    def test_second_independent_borderline_capture_is_also_rejected(self):
        # A second, different-session borderline capture used to corroborate
        # the first into an accept — it no longer does. Both are rejected.
        first = self._punch(face_embedding=BORDERLINE_EMBEDDING_A, capture_session_id='session-a')
        self.assertEqual(first.status_code, 403, first.data)

        second = self._punch(face_embedding=BORDERLINE_EMBEDDING_B, capture_session_id='session-b')
        self.assertEqual(second.status_code, 403, second.data)
        _assert_reached_face_check(self, first)
        _assert_reached_face_check(self, second)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())

        # Proof both rejections came from the FACE check, not some other 403:
        # two audit rows, both the low-confidence rejection, neither a match.
        attempts = list(FaceVerificationAttempt.objects.filter(employee=self.employee))
        self.assertEqual(len(attempts), 2)
        for attempt in attempts:
            self.assertFalse(attempt.is_match)
            self.assertEqual(attempt.rejection_reason, FaceVerificationAttempt.REJECTION_LOW_CONFIDENCE_PENDING)

    def test_confident_match_is_unaffected(self):
        resp = self._punch(face_embedding=MATCHING_EMBEDDING, capture_session_id='session-a')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(AttendancePunch.objects.get(employee=self.employee).face_verified)
        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        self.assertTrue(attempt.is_match)
        self.assertEqual(attempt.rejection_reason, '')


class WfhGateRunsBeforeFaceVerificationTests(TestCase):
    """The geofence / work-from-home gate must reject an invalid WFH punch
    BEFORE face verification is reached (services_attendance.record_punch
    validates the location first, then calls verify_for_punch).

    Why the ordering matters, and how it's proven here: face verification
    always writes a FaceVerificationAttempt audit row, and failed attempts
    count toward the 5-failures-in-15-minutes lockout. So if the face check ran
    first, an employee punching from the wrong place would (a) leave an audit
    row and (b) burn lockout attempts. Every rejection below therefore asserts
    ZERO FaceVerificationAttempt rows — the face service was never invoked —
    plus no AttendancePunch. Each case is paired with a positive control (the
    same employee, face and embedding succeeding once the WFH requirement is
    met), so the rejections can't be an artefact of broken setup.
    """

    HOME_LAT = Decimal('17.000000')
    HOME_LON = Decimal('78.000000')

    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.employee = make_user('wfhgate@test.com', role=make_role('employee_wfh_gate'),
                                  password='TestPass123!')
        _login(self.client, 'wfhgate@test.com')
        # Face verification is mandatory and this employee has a valid,
        # approved registration — so IF the face check were reached, a
        # matching embedding would succeed and a mismatched one would fail.
        _set_face_verification_mandatory(True)
        _make_approved_request(self.employee)

    def tearDown(self):
        cache.clear()

    def _wfh_punch(self, **overrides):
        payload = {'punch_type': 'IN', 'attendance_mode': 'wfh'}
        payload.update(overrides)
        return self.client.post(reverse('attendance-punch'), payload, format='json')

    def _approve_wfh_today(self):
        today = timezone.localdate()
        return WorkFromHomeRequest.objects.create(
            employee=self.employee, start_date=today, end_date=today,
            latitude=self.HOME_LAT, longitude=self.HOME_LON, status=REQ_APPROVED,
        )

    def _assert_rejected_before_face_check(self, resp, expected_message):
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data['message'], expected_message)
        self.assertFalse(AttendancePunch.objects.filter(employee=self.employee).exists())
        # The decisive assertion: the face service never ran.
        self.assertEqual(
            FaceVerificationAttempt.objects.filter(employee=self.employee).count(), 0,
            'face verification was reached even though the WFH gate should have rejected first',
        )

    def test_wfh_punch_without_an_approved_request_is_rejected_before_face_check(self):
        resp = self._wfh_punch(face_embedding=MATCHING_EMBEDDING, latitude=17.0, longitude=78.0)
        self._assert_rejected_before_face_check(resp, WFH_NO_APPROVED_REQUEST_MESSAGE)

    def test_a_non_matching_face_does_not_leave_an_attempt_when_wfh_is_not_approved(self):
        # A bad face must not even be evaluated (so it can't count toward the
        # lockout) when the location gate has already refused the punch.
        resp = self._wfh_punch(face_embedding=MISMATCHED_EMBEDDING, latitude=17.0, longitude=78.0)
        self._assert_rejected_before_face_check(resp, WFH_NO_APPROVED_REQUEST_MESSAGE)

    def test_wfh_punch_without_gps_is_rejected_before_face_check(self):
        self._approve_wfh_today()
        resp = self._wfh_punch(face_embedding=MATCHING_EMBEDDING)
        self._assert_rejected_before_face_check(resp, GPS_REQUIRED_MESSAGE)

    def test_wfh_punch_outside_the_declared_location_is_rejected_before_face_check(self):
        self._approve_wfh_today()
        # ~140 km from the approved point — far outside the 200 m radius.
        resp = self._wfh_punch(face_embedding=MATCHING_EMBEDDING, latitude=18.0, longitude=79.0)
        self._assert_rejected_before_face_check(
            resp, 'You are outside your declared work-from-home location. Punch In is not permitted.',
        )

    def test_control_valid_wfh_punch_reaches_face_verification_and_succeeds(self):
        # Same employee, same registered face, same embedding as the cases
        # above — only the WFH requirement differs. Proves the rejections
        # above came from the WFH gate, and that the face check does run once
        # the gate passes (an attempt row now exists, and it matched).
        self._approve_wfh_today()
        resp = self._wfh_punch(face_embedding=MATCHING_EMBEDDING, latitude=17.0, longitude=78.0)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(AttendancePunch.objects.get(employee=self.employee).face_verified)
        attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        self.assertTrue(attempt.is_match)
        self.assertEqual(attempt.rejection_reason, '')


class FaceRegistrationMyStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client   = APIClient()
        self.employee = make_user('facestatus@test.com', role=make_role('employee'))
        _login(self.client, 'facestatus@test.com')

    def tearDown(self):
        cache.clear()

    def test_no_registration_returns_empty_data(self):
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.status_code, 200, resp.data)
        # success() (core/responses.py) normalises a None data payload to {} —
        # shared helper behavior, not something this endpoint overrides.
        self.assertEqual(resp.data['data'], {})

    def test_approved_registration_status_is_returned(self):
        _make_approved_request(self.employee)
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['status'], 'approved')

    def test_returns_latest_request_when_several_exist(self):
        older = FaceRegistrationRequest.objects.create(
            employee=self.employee, face_embedding=REGISTERED_EMBEDDING,
            liveness_passed=True, status=FaceRegistrationRequest.STATUS_REJECTED,
        )
        newer = _make_approved_request(self.employee)
        resp = self.client.get(reverse('face-registration-me'))
        self.assertEqual(resp.data['data']['id'], str(newer.pk))
        self.assertNotEqual(resp.data['data']['id'], str(older.pk))


class FaceRegistrationHRRegisterTests(TestCase):
    """HR captures a face in person and registers/updates it directly,
    auto-approved — see views/face_registration_hr.py."""

    def setUp(self):
        cache.clear()
        _set_face_verification_mandatory(True)
        self.client = APIClient()
        self.hr_role = make_role('hr', permission_codenames=['facial_recognition.approve'])
        self.hr_user = make_user('hrregister-hr@test.com', role=self.hr_role, branch='Head Office')
        # Deliberately a different branch than the HR user's own, to prove
        # the picker/register endpoints are NOT branch-scoped.
        self.employee = make_user(
            'hrregister-employee@test.com', role=make_role('employee_hr_target'),
            branch='Remote Branch',
        )
        _login(self.client, 'hrregister-hr@test.com')

    def tearDown(self):
        cache.clear()

    def _register(self, **overrides):
        payload = {
            'employee_uuid': str(self.employee.pk),
            'face_embedding': REGISTERED_EMBEDDING,
            'liveness_passed': True,
            'liveness_score': 0.95,
            'consent_acknowledged': True,
        }
        payload.update(overrides)
        return self.client.post(reverse('face-registration-hr-register'), payload, format='json')

    def test_register_is_refused_when_toggle_is_off(self):
        _set_face_verification_mandatory(False)
        resp = self._register()
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertIn('contact your administrator', resp.data['message'].lower())
        self.assertFalse(FaceRegistrationRequest.objects.filter(employee=self.employee).exists())

    def test_non_approver_is_forbidden_on_all_three_endpoints(self):
        make_user('hrregister-noperm@test.com', role=make_role('employee_no_facial_perm_hr'))
        client = APIClient()
        _login(client, 'hrregister-noperm@test.com')

        self.assertEqual(
            client.get(reverse('face-registration-employee-picker')).status_code, 403,
        )
        self.assertEqual(
            client.get(reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})).status_code,
            403,
        )
        self.assertEqual(
            client.post(reverse('face-registration-hr-register'), {
                'employee_uuid': str(self.employee.pk), 'face_embedding': REGISTERED_EMBEDDING,
                'liveness_passed': True, 'consent_acknowledged': True,
            }, format='json').status_code,
            403,
        )

    def test_register_new_face_is_auto_approved(self):
        resp = self._register()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['status'], 'approved')

        face_request = FaceRegistrationRequest.objects.get(employee=self.employee)
        self.assertEqual(face_request.status, FaceRegistrationRequest.STATUS_APPROVED)
        self.assertEqual(face_request.approved_by_id, self.hr_user.id)
        self.assertIsNotNone(face_request.approved_at)

    def test_updating_an_already_registered_employee_supersedes_the_old_face(self):
        self._register(face_embedding=REGISTERED_EMBEDDING)
        new_embedding = [v + 2.0 for v in REGISTERED_EMBEDDING]  # a visibly different face
        resp = self._register(face_embedding=new_embedding)
        self.assertEqual(resp.status_code, 201, resp.data)

        # Punching with the OLD face now fails; the NEW one succeeds — proves
        # the update actually took effect for the punch flow, not just the DB row.
        # A fresh client, not self.client (still authenticated as HR) — cookie
        # auth doesn't reset with Django's session-oriented .logout().
        employee_client = APIClient()
        _login(employee_client, 'hrregister-employee@test.com')

        old_face_resp = employee_client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': PUNCH_MODE, 'face_embedding': REGISTERED_EMBEDDING,
        }, format='json')
        self.assertEqual(old_face_resp.status_code, 403, old_face_resp.data)
        # The 403 must be the FACE mismatch, proven by the audit row — not the
        # geofence/WFH gate, which would leave no FaceVerificationAttempt behind.
        _assert_reached_face_check(self, old_face_resp)
        old_attempt = FaceVerificationAttempt.objects.get(employee=self.employee)
        self.assertFalse(old_attempt.is_match)
        self.assertEqual(old_attempt.rejection_reason, FaceVerificationAttempt.REJECTION_MISMATCH)

        new_face_resp = employee_client.post(reverse('attendance-punch'), {
            'punch_type': 'IN', 'attendance_mode': PUNCH_MODE, 'face_embedding': new_embedding,
        }, format='json')
        self.assertEqual(new_face_resp.status_code, 200, new_face_resp.data)
        self.assertTrue(AttendancePunch.objects.get(employee=self.employee).face_verified)

    def test_employee_picker_is_not_branch_scoped(self):
        resp = self.client.get(reverse('face-registration-employee-picker'))
        self.assertEqual(resp.status_code, 200, resp.data)
        emails = {row['email'] for row in resp.data['data']['results']}
        # employee is on 'Remote Branch', hr_user is on 'Head Office' — visible
        # anyway proves this isn't scoped like accounts.EmployeeListCreateView.
        self.assertIn('hrregister-employee@test.com', emails)

    def test_employee_picker_search_filters_by_name(self):
        resp = self.client.get(reverse('face-registration-employee-picker'), {'search': 'hrregister-employee'})
        emails = {row['email'] for row in resp.data['data']['results']}
        self.assertEqual(emails, {'hrregister-employee@test.com'})

    def test_employee_status_endpoint_reflects_registration(self):
        no_reg_resp = self.client.get(
            reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})
        )
        self.assertEqual(no_reg_resp.data['data'], {})

        self._register()
        resp = self.client.get(
            reverse('face-registration-employee-status', kwargs={'employee_uuid': self.employee.pk})
        )
        self.assertEqual(resp.data['data']['status'], 'approved')

    def test_register_for_unknown_employee_is_not_found(self):
        resp = self._register(employee_uuid='00000000-0000-0000-0000-000000000000')
        self.assertEqual(resp.status_code, 404, resp.data)
