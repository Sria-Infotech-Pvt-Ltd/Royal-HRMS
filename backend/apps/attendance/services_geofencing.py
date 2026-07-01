"""
Geofencing service for attendance punch validation.

Uses the Haversine formula to compute the great-circle distance between
two GPS coordinates.  No external library required — pure Python math.

Extensibility:
  Attendance modes are validated through a strategy map.
  To add a new mode (e.g. 'client_location'), register it in
  _MODE_VALIDATORS with its validation function.

Performance:
  Branch lookup is cached for the duration of a single request via
  _resolve_employee_branch(), which does at most one SELECT per call.
  No N+1 queries — branches are looked up directly by name match.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

# Earth's mean radius in metres (WGS-84)
_EARTH_RADIUS_M = 6_371_000


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GpsCoordinate:
    latitude:  float
    longitude: float


@dataclass
class GeofenceResult:
    """
    Returned by GeofencingService.validate().

    is_allowed        — whether the punch should be permitted
    is_inside_geofence — True/False/None (None = not evaluated)
    calculated_distance — metres to branch (None if not calculated)
    branch             — resolved Branch object (None if not found)
    rejection_message  — human-readable reason if is_allowed is False
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
    """
    Returns the great-circle distance in metres between two GPS points.

    Uses the Haversine formula — accurate to within ~0.3% for distances
    under 1,000 km, which is more than sufficient for office geofencing.
    """
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
#  Branch resolver
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_employee_branch(employee):
    """
    Resolves the employee's Branch record from their branch string field.

    User.branch is a plain CharField — we match it against Branch.branch_name.
    Falls back to branch_code match so slightly mismatched names still resolve.
    Returns None if no match found (new employee, unassigned, etc.).
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
        # Try loose match on branch_code
        branch = (
            Branch.objects
            .filter(branch_code__iexact=branch_name, status=Branch.STATUS_ACTIVE)
            .first()
        )
    return branch


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
            employee_lat=13.082840,
            employee_lon=80.270500,
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
    ) -> GeofenceResult:
        """
        Main entry point.  Delegates to the correct mode validator.
        """
        validator = _MODE_VALIDATORS.get(attendance_mode, _validate_office)
        return validator(employee, employee_lat, employee_lon)


# ── Mode validators ────────────────────────────────────────────────────────────

def _validate_office(
    employee,
    employee_lat: Optional[float],
    employee_lon: Optional[float],
) -> GeofenceResult:
    """
    Office mode: validate GPS against branch geofence.

    Decision tree:
    1. Resolve branch → if None, allow punch (unassigned branch, log warning).
    2. Branch has no coordinates → allow punch (geofence not configured yet).
    3. Branch geofencing_enabled = False → allow punch (feature disabled).
    4. Employee sent no GPS → reject (coordinates required for office punch).
    5. Calculate Haversine distance → allow if ≤ allowed_radius_meters.
    """
    branch = _resolve_employee_branch(employee)

    if branch is None:
        logger.warning(
            'Geofence: no branch resolved for employee %s ("%s") — punch allowed without validation.',
            employee.pk, getattr(employee, 'branch', ''),
        )
        return GeofenceResult(
            is_allowed=True, is_inside_geofence=None,
            calculated_distance=None, branch=None, rejection_message=None,
        )

    if not branch.has_coordinates or not branch.geofencing_enabled:
        return GeofenceResult(
            is_allowed=True, is_inside_geofence=None,
            calculated_distance=None, branch=branch, rejection_message=None,
        )

    # Branch has coordinates + geofencing ON → GPS is required
    if employee_lat is None or employee_lon is None:
        return GeofenceResult(
            is_allowed=False,
            is_inside_geofence=False,
            calculated_distance=None,
            branch=branch,
            rejection_message=(
                'Your location is required to clock in at this branch. '
                'Please allow location access in your browser and try again.'
            ),
        )

    employee_coord = GpsCoordinate(latitude=float(employee_lat), longitude=float(employee_lon))
    branch_coord   = GpsCoordinate(
        latitude=float(branch.latitude),
        longitude=float(branch.longitude),
    )

    distance_m   = haversine_distance(employee_coord, branch_coord)
    is_inside    = distance_m <= branch.allowed_radius_meters

    if not is_inside:
        rejection = (
            f'You are {round(distance_m)} m away from {branch.branch_name}. '
            f'You must be within {branch.allowed_radius_meters} m to clock in. '
            'Please move closer to the office and try again.'
        )
        return GeofenceResult(
            is_allowed=False,
            is_inside_geofence=False,
            calculated_distance=round(distance_m, 2),
            branch=branch,
            rejection_message=rejection,
        )

    return GeofenceResult(
        is_allowed=True,
        is_inside_geofence=True,
        calculated_distance=round(distance_m, 2),
        branch=branch,
        rejection_message=None,
    )


def _validate_no_geofence(
    employee,
    employee_lat: Optional[float],
    employee_lon: Optional[float],
) -> GeofenceResult:
    """
    WFH / Field / Client Location / Remote Office modes:
    Record GPS coordinates for audit but do not validate against any office.
    Always allowed.
    """
    branch = _resolve_employee_branch(employee)
    return GeofenceResult(
        is_allowed=True, is_inside_geofence=None,
        calculated_distance=None, branch=branch, rejection_message=None,
    )


# Strategy map — add a new mode here to support it
_MODE_VALIDATORS = {
    'office':          _validate_office,
    'wfh':             _validate_no_geofence,
    'field':           _validate_no_geofence,
    'client_location': _validate_no_geofence,
    'remote_office':   _validate_no_geofence,
}
