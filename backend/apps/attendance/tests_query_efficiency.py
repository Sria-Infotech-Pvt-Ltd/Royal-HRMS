"""
Scale-1 (2026-08-25 scalability-audit fixes) — Risk 4: three duplicate/
redundant DB round-trips found in the punch path (services_geofencing.py's
_resolve_all_allowed_branches, services_attendance.py's _is_holiday, and
process_day()'s double WorkFromHomeRequest.approved_for() lookup).

SimpleTestCase + mocking throughout, same pattern apps/voice_commands/tests/
test_mode_geofencing.py already uses for this exact service layer — this
shared test DB has no provisioned tenant schema (the ~141 known
"relation does not exist" errors elsewhere in this suite), so a real
TestCase/APIClient round trip through PunchService.record_punch() can't
run here at all. These tests isolate each fix at the function/service
boundary instead, mocking out everything the fix itself doesn't touch.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.attendance.services_attendance import AttendanceProcessorService
from apps.attendance.services_geofencing import _resolve_all_allowed_branches
from apps.branch.models import Branch


class ResolveAllAllowedBranchesQueryEfficiencyTests(SimpleTestCase):
    """_resolve_all_allowed_branches() used to call .exists() and then
    separately iterate the same queryset — two DB round trips where one
    (list()) suffices. Confirms the fix: the queryset is materialized
    exactly once, .exists() is never called."""

    @patch('apps.branch.models.EmployeeBranchAccess.objects')
    def test_does_not_call_exists_before_iterating(self, mock_manager):
        active_branch = MagicMock()
        active_branch.status = Branch.STATUS_ACTIVE
        row = MagicMock()
        row.branch = active_branch
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.__iter__.return_value = iter([row])
        mock_manager.filter.return_value = mock_qs

        result = _resolve_all_allowed_branches(employee=MagicMock())

        mock_qs.exists.assert_not_called()
        self.assertEqual(result, [active_branch])

    @patch('apps.attendance.services_geofencing._resolve_employee_branch')
    @patch('apps.branch.models.EmployeeBranchAccess.objects')
    def test_falls_back_to_primary_branch_when_no_access_rows(self, mock_manager, mock_resolve_primary):
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.__iter__.return_value = iter([])
        mock_manager.filter.return_value = mock_qs
        primary = MagicMock()
        mock_resolve_primary.return_value = primary

        result = _resolve_all_allowed_branches(employee=MagicMock())

        mock_qs.exists.assert_not_called()
        self.assertEqual(result, [primary])

    @patch('apps.branch.models.EmployeeBranchAccess.objects')
    def test_filters_out_inactive_branches(self, mock_manager):
        inactive_branch = MagicMock()
        inactive_branch.status = 'inactive'
        row = MagicMock()
        row.branch = inactive_branch
        mock_qs = MagicMock()
        mock_qs.select_related.return_value = mock_qs
        mock_qs.__iter__.return_value = iter([row])
        mock_manager.filter.return_value = mock_qs

        result = _resolve_all_allowed_branches(employee=MagicMock())

        self.assertEqual(result, [])


class IsHolidayUsesCacheServiceTests(SimpleTestCase):
    """_is_holiday() used to query Holiday directly on every punch, bypassing
    HolidayCacheService that its sibling _holiday_name() already uses.
    Confirms the fix: it now delegates to the same cache service."""

    @patch('core.cache_service.HolidayCacheService.get_holiday_dates')
    def test_delegates_to_holiday_cache_service_with_a_single_day_range(self, mock_get_dates):
        mock_get_dates.return_value = {date(2026, 8, 25)}

        result = AttendanceProcessorService._is_holiday(date(2026, 8, 25), 'Head Office')

        mock_get_dates.assert_called_once_with(date(2026, 8, 25), date(2026, 8, 25), 'Head Office')
        self.assertTrue(result)

    @patch('core.cache_service.HolidayCacheService.get_holiday_dates')
    def test_returns_false_when_date_not_in_cached_set(self, mock_get_dates):
        mock_get_dates.return_value = set()

        result = AttendanceProcessorService._is_holiday(date(2026, 8, 25))

        self.assertFalse(result)

    @patch('core.cache_service.HolidayCacheService.get_holiday_dates')
    def test_default_branch_name_is_forwarded_as_empty_string(self, mock_get_dates):
        mock_get_dates.return_value = set()

        AttendanceProcessorService._is_holiday(date(2026, 8, 25))

        mock_get_dates.assert_called_once_with(date(2026, 8, 25), date(2026, 8, 25), '')


class ProcessDayWfhRequestMemoizationTests(SimpleTestCase):
    """process_day() used to always call WorkFromHomeRequest.approved_for()
    itself, even when PunchService.record_punch() had already resolved the
    exact same (employee, date) lookup one call earlier via
    GeofencingService._validate_wfh(). Confirms the fix: passing an
    already-resolved wfh_request (including an explicit None — "already
    checked, nothing approved") skips the second query; omitting it
    preserves the original self-resolving behaviour for every other caller
    (e.g. batch/backfill management commands)."""

    def _patch_process_day_internals(self):
        """Isolates the wfh_request handling from the rest of process_day()'s
        DB/cache work, none of which this test cares about — same reasoning
        as this module's own docstring for why SimpleTestCase + mocks."""
        return [
            patch('apps.attendance.services_attendance._get_settings', return_value=None),
            patch(
                'apps.attendance.services_attendance.AttendancePunch.objects.filter',
                return_value=MagicMock(order_by=MagicMock(return_value=[])),
            ),
            patch.object(AttendanceProcessorService, '_is_holiday', return_value=False),
            patch.object(AttendanceProcessorService, '_is_weekly_off', return_value=False),
            patch.object(AttendanceProcessorService, '_no_punch_record', return_value={
                'status': 'absent', 'first_punch_in': None, 'last_punch_out': None,
                'total_working_minutes': 0, 'overtime_minutes': 0,
                'is_late': False, 'is_early_exit': False, 'note': 'No punch recorded',
            }),
            patch(
                'apps.attendance.services_attendance.AttendanceRecord.objects.update_or_create',
                return_value=(MagicMock(), True),
            ),
        ]

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_uses_the_provided_wfh_request_without_requerying(self, mock_approved_for):
        patchers = self._patch_process_day_internals()
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])
        pre_resolved = MagicMock()

        AttendanceProcessorService.process_day(MagicMock(), date(2026, 8, 25), wfh_request=pre_resolved)

        mock_approved_for.assert_not_called()

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_a_provided_none_is_also_honoured_without_requerying(self, mock_approved_for):
        """None is a valid resolved answer ("checked, nothing approved") —
        must be distinguished from "not provided at all" via the sentinel,
        not treated as falsy-and-therefore-unresolved."""
        patchers = self._patch_process_day_internals()
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])

        AttendanceProcessorService.process_day(MagicMock(), date(2026, 8, 25), wfh_request=None)

        mock_approved_for.assert_not_called()

    @patch('apps.hrms.models.WorkFromHomeRequest.approved_for')
    def test_resolves_wfh_request_itself_when_not_provided(self, mock_approved_for):
        patchers = self._patch_process_day_internals()
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])
        mock_approved_for.return_value = None

        AttendanceProcessorService.process_day(MagicMock(), date(2026, 8, 25))

        mock_approved_for.assert_called_once()
