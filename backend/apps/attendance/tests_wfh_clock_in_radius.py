"""WFH clock-in radius: a point captured on the device (gps) uses WFH_GPS_RADIUS_M, a point looked up from an address uses the
larger WFH_ADDRESS_RADIUS_M. Both come from settings."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.factories import make_role, make_user
from apps.attendance.services_geofencing import _validate_wfh
from apps.hrms.models import REQ_APPROVED, WorkFromHomeRequest

HOME_LAT, HOME_LON = 17.385000, 78.486000
# 0.0036 degrees of latitude is about 400 m: outside 200 m, inside 500 m.
NEAR_LAT = HOME_LAT + 0.0036


class WfhClockInRadiusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = make_user('wfh-radius@test.com', role=make_role('wfh_radius_emp', permission_codenames=[]))

    def _approved(self, source: str) -> None:
        today = timezone.localdate()
        WorkFromHomeRequest.objects.create(
            employee=self.employee, start_date=today, end_date=today, latitude=HOME_LAT, longitude=HOME_LON,
            status=REQ_APPROVED, location_source=source,
        )

    def test_gps_location_uses_the_gps_radius(self):
        self._approved('gps')
        self.assertFalse(_validate_wfh(self.employee, NEAR_LAT, HOME_LON).is_allowed)

    def test_address_location_uses_the_larger_radius(self):
        self._approved('address')
        result = _validate_wfh(self.employee, NEAR_LAT, HOME_LON)
        self.assertTrue(result.is_allowed)
        self.assertGreater(result.calculated_distance, 200)

    def test_address_location_is_still_refused_beyond_its_radius(self):
        self._approved('address')
        self.assertFalse(_validate_wfh(self.employee, HOME_LAT + 0.009, HOME_LON).is_allowed)   # about 1 km

    def test_radii_come_from_settings(self):
        self._approved('gps')
        with override_settings(WFH_GPS_RADIUS_M=600):
            self.assertTrue(_validate_wfh(self.employee, NEAR_LAT, HOME_LON).is_allowed)
