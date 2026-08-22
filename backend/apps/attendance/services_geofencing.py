"""
Geofencing service for attendance punch validation.

Uses the Haversine formula to compute the great-circle distance between
two GPS coordinates.  No external library required — pure Python math.

Multi-branch support:
  Most employees have a single branch (User.branch CharField).  For employees
  who work across multiple locations (HR, IT, Management, Regional Managers),
  add rows to EmployeeBranchAccess.  When such rows exist the geofencing service
  validates against ALL listed branches and allows the punch if the employee is
  within any one of them.

Extensibility:
  Attendance modes are validated through a strategy map.
  To add a new mode (e.g. 'client_location'), register it in
  _MODE_VALIDATORS with its validation function.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Earth's mean radius in metres (WGS-84)
_EARTH_RADIUS_M = 6_371_000

# Cap on how much of the device's self-reported GPS accuracy (margin of
# error) we'll forgive against the geofence radius. Without a cap, a
# low-precision reading (e.g. Wi-Fi/IP-based location on a laptop, often
# accurate to only 1-2km) would make the geofence meaningless.
_MAX_ACCURACY_TOLERANCE_M = 100

# Named so callers (e.g. voice_commands.conversation_clarification, which
# needs to recognize this specific, client-retryable rejection to keep a
# "did you mean" clarification alive across the browser's silent
# geolocation-retry resubmit) can compare against it without duplicating the
# literal string — see that module's own usage.
GPS_REQUIRED_MESSAGE = (
    'Your location is required to clock in at this branch. '
    'Please allow location access in your browser and try again.'
)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GpsCoordinate:
    latitude:  float
    longitude: float


@dataclass
class GeofenceResult:
    """
    Returned by GeofencingService.validate().

    is_allowed         — whether the punch should be permitted
    is_inside_geofence — True/False/None (None = not evaluated)
    calculated_distance — metres to the matched branch (None if not calculated)
    branch              — resolved Branch object (None if not found)
    rejection_message   — human-readable reason if is_allowed is False
    """
    is_allowed:           bool
    is_inside_geofence:   Optional[bool]
    calculated_distance:  Optional[float]
    branch:               object          # Branch model instance or None
    rejection_message:    Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
#  Haversine formula
# ══════════════════════════════════════════════════════════════════════════════

def haversine_distance(coord1: GpsCoordinate, coord2: GpsCoordinate) -> float:
    """Returns the great-circle distance in metres between two GPS points."""
    lat1 = math.radians(coord1.latitude)
    lat2 = math.radians(coord2.latitude)
    d_lat = math.radians(coord2.latitude  - coord1.latitude)
    d_lon = math.radians(coord2.longitude - coord1.longitude)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_M * c


# ══════════════════════════════════════════════════════════════════════════════
#  Branch resolvers
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_employee_branch(employee):
    """
    Resolves the employee's Branch record from their branch string field.

    User.branch is a plain CharField — we match it against Branch.branch_name.
    Falls back to branch_code match so slightly mismatched names still resolve.
    Returns None if no match found.
    """
    from apps.branch.models import Branch

    branch_name = getattr(employee, 'branch', '') or ''
    if not branch_name:
        return None

    branch = (
        Branch.objects
        .filter(branch_name=branch_name, status=Branch.STATUS_ACTIVE)
        .first()
    )
    if branch is None:
        branch = (
            Branch.objects
            .filter(branch_code__iexact=branch_name, status=Branch.STATUS_ACTIVE)
            .first()
        )
    return branch


def _resolve_all_allowed_branches(employee) -> list:
    """
    Returns every Branch the employee is authorised to punch from.

    1. If the employee has EmployeeBranchAccess records, use those branches
       (covers HR / IT / Management / Regional Managers with multi-branch access).
    2. Otherwise fall back to the single branch resolved from User.branch.
    """
    from apps.branch.models import Branch, EmployeeBranchAccess

    access_qs = (
        EmployeeBranchAccess.objects
        .filter(employee=employee)
        .select_related('branch')
    )

    if access_qs.exists():
        return [
            r.branch for r in access_qs
            if r.branch.status == Branch.STATUS_ACTIVE
        ]

    primary = _resolve_employee_branch(employee)
    return [primary] if primary else []


# ══════════════════════════════════════════════════════════════════════════════
#  GeofencingService
# ══════════════════════════════════════════════════════════════════════════════

class GeofencingService:
    """
    Validates whether an employee punch is permitted given their location
    and attendance mode.

    Usage:
        result = GeofencingService.validate(
            employee=request.user,
            attendance_mode='office',
            employee_lat=17.385044,
            employee_lon=78.486671,
        )
        if not result.is_allowed:
            return error(result.rejection_message)
    """

    @classmethod
    def validate(
        cls,
        employee,
        attendance_mode: str,
        employee_lat: Optional[float] = None,
        employee_lon: Optional[float] = None,
        employee_accuracy: Optional[float] = None,
    ) -> GeofenceResult:
        validator = _MODE_VALIDATORS.get(attendance_mode, _validate_office)
        return validator(employee, employee_lat, employee_lon, employee_accuracy)


# ── Mode validators ────────────────────────────────────────────────────────────

def _validate_office(
    employee,
    employee_lat: Optional[float],
    employee_lon: Optional[float],
    employee_accuracy: Optional[float] = None,
) -> GeofenceResult:
    """
    Office mode: validate GPS against the employee's allowed branch geofences.

    Decision tree:
    1. Resolve allowed branches (EmployeeBranchAccess if present, else User.branch).
    2. No branches resolved → allow punch (unassigned, log warning).
    3. None of the branches have geofencing enabled + coordinates → allow.
    4. Employee sent no GPS → reject (coordinates required).
    5. Check Haversine distance against every geofenced branch, with the
       branch radius widened by the device's reported GPS accuracy (capped
       at _MAX_ACCURACY_TOLERANCE_M) so a genuinely uncertain-but-plausibly-
       inside reading isn't hard-rejected. Allow if within ANY one of them;
       reject if outside all.
    """
    tolerance_m = min(employee_accuracy, _MAX_ACCURACY_TOLERANCE_M) if employee_accuracy else 0
    allowed_branches = _resolve_all_allowed_branches(employee)

    if not allowed_branches:
        logger.warning(
            'Geofence: no branch resolved for employee %s ("%s") — punch allowed without validation.',
            employee.pk, getattr(employee, 'branch', ''),
        )
        return GeofenceResult(
            is_allowed=True, is_inside_geofence=None,
            calculated_distance=None, branch=None, rejection_message=None,
        )

    # Branches that require GPS validation
    validated_branches = [
        b for b in allowed_branches
        if b.has_coordinates and b.geofencing_enabled
    ]

    if not validated_branches:
        # No branch has geofencing on — allow at the primary/first branch
        return GeofenceResult(
            is_allowed=True, is_inside_geofence=None,
            calculated_distance=None, branch=allowed_branches[0], rejection_message=None,
        )

    # GPS is mandatory when at least one branch requires it
    if employee_lat is None or employee_lon is None:
        return GeofenceResult(
            is_allowed=False,
            is_inside_geofence=False,
            calculated_distance=None,
            branch=validated_branches[0],
            rejection_message=GPS_REQUIRED_MESSAGE,
        )

    employee_coord = GpsCoordinate(latitude=float(employee_lat), longitude=float(employee_lon))

    # Find the nearest allowed branch the employee is within
    best_branch:   object        = None
    best_distance: Optional[float] = None

    for branch in validated_branches:
        branch_coord = GpsCoordinate(
            latitude=float(branch.latitude),
            longitude=float(branch.longitude),
        )
        distance_m = haversine_distance(employee_coord, branch_coord)
        if distance_m <= branch.allowed_radius_meters + tolerance_m:
            if best_distance is None or distance_m < best_distance:
                best_branch   = branch
                best_distance = distance_m

    if best_branch is not None:
        return GeofenceResult(
            is_allowed=True,
            is_inside_geofence=True,
            calculated_distance=round(best_distance, 2),
            branch=best_branch,
            rejection_message=None,
        )

    # Outside every allowed branch — find the closest for context
    closest_branch = min(
        validated_branches,
        key=lambda b: haversine_distance(
            employee_coord,
            GpsCoordinate(float(b.latitude), float(b.longitude)),
        ),
    )
    closest_distance = haversine_distance(
        employee_coord,
        GpsCoordinate(float(closest_branch.latitude), float(closest_branch.longitude)),
    )

    logger.warning(
        'Geofence reject: employee %s at (%.6f, %.6f) is %.1fm from "%s" '
        '(radius %sm + accuracy tolerance %.1fm = effective %.1fm; device-reported accuracy %s).',
        employee.pk, employee_coord.latitude, employee_coord.longitude, closest_distance,
        closest_branch.branch_name, closest_branch.allowed_radius_meters, tolerance_m,
        closest_branch.allowed_radius_meters + tolerance_m, employee_accuracy,
    )
    return GeofenceResult(
        is_allowed=False,
        is_inside_geofence=False,
        calculated_distance=round(closest_distance, 2),
        branch=closest_branch,
        rejection_message=(
            'You are outside your assigned office location. Punch In is not permitted.'
        ),
    )


def _validate_no_geofence(
    employee,
    employee_lat: Optional[float],
    employee_lon: Optional[float],
    employee_accuracy: Optional[float] = None,
) -> GeofenceResult:
    """
    Field / Client Location / Remote Office modes:
    Record GPS coordinates for audit but do not validate against any office.
    Always allowed.
    """
    branch = _resolve_employee_branch(employee)
    return GeofenceResult(
        is_allowed=True, is_inside_geofence=None,
        calculated_distance=None, branch=branch, rejection_message=None,
    )


# WFH punches are validated against the location saved on that day's
# approved WorkFromHomeRequest — the radius mirrors a typical office's
# default (see BranchManagement.tsx's own 150m default), just not
# per-request configurable since nothing has asked for that yet.
_WFH_DEFAULT_RADIUS_M = 200

WFH_NO_APPROVED_REQUEST_MESSAGE = (
    'You need an approved work-from-home request covering today before you '
    'can clock in as WFH. Submit a request from the Work From Home page.'
)


def _validate_wfh(
    employee,
    employee_lat: Optional[float],
    employee_lon: Optional[float],
    employee_accuracy: Optional[float] = None,
) -> GeofenceResult:
    """
    WFH mode: unlike office (validated against a Branch) or field/client/
    remote (never validated), a WFH punch is gated on an approved
    WorkFromHomeRequest covering today, and validated against that
    request's saved GPS point — the same Haversine + accuracy-tolerance
    check _validate_office uses, just against a request instead of a
    Branch. No approved request at all → rejected outright, closing the
    gap where attendance_mode='wfh' used to be honored unconditionally.
    """
    from django.utils import timezone
    from apps.hrms.models import WorkFromHomeRequest

    today = timezone.localdate()
    wfh_request = WorkFromHomeRequest.approved_for(employee, today)
    if not wfh_request:
        return GeofenceResult(
            is_allowed=False, is_inside_geofence=False,
            calculated_distance=None, branch=None,
            rejection_message=WFH_NO_APPROVED_REQUEST_MESSAGE,
        )

    if employee_lat is None or employee_lon is None:
        return GeofenceResult(
            is_allowed=False, is_inside_geofence=False,
            calculated_distance=None, branch=None,
            rejection_message=GPS_REQUIRED_MESSAGE,
        )

    tolerance_m = min(employee_accuracy, _MAX_ACCURACY_TOLERANCE_M) if employee_accuracy else 0
    employee_coord = GpsCoordinate(latitude=float(employee_lat), longitude=float(employee_lon))
    request_coord = GpsCoordinate(
        latitude=float(wfh_request.latitude), longitude=float(wfh_request.longitude),
    )
    distance_m = haversine_distance(employee_coord, request_coord)
    effective_radius = _WFH_DEFAULT_RADIUS_M + tolerance_m

    if distance_m <= effective_radius:
        return GeofenceResult(
            is_allowed=True, is_inside_geofence=True,
            calculated_distance=round(distance_m, 2), branch=None, rejection_message=None,
        )

    logger.warning(
        'WFH geofence reject: employee %s at (%.6f, %.6f) is %.1fm from their '
        'approved WFH location "%s" (radius %sm + accuracy tolerance %.1fm = '
        'effective %.1fm; device-reported accuracy %s).',
        employee.pk, employee_coord.latitude, employee_coord.longitude, distance_m,
        wfh_request.location_label or 'unnamed', _WFH_DEFAULT_RADIUS_M, tolerance_m,
        effective_radius, employee_accuracy,
    )
    return GeofenceResult(
        is_allowed=False, is_inside_geofence=False,
        calculated_distance=round(distance_m, 2), branch=None,
        rejection_message=(
            'You are outside your declared work-from-home location. Punch In is not permitted.'
        ),
    )


# Strategy map — add a new mode here to support it
_MODE_VALIDATORS = {
    'office':          _validate_office,
    'wfh':             _validate_wfh,
    'field':           _validate_no_geofence,
    'client_location': _validate_no_geofence,
    'remote_office':   _validate_no_geofence,
}
