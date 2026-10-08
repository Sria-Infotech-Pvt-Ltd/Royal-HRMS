"""
Phase 6B Task E.3 — the device punch push ingestion logic: idempotency
(device + device_punch_id), clock-skew recording (device_time vs
received_at), and unknown-employee handling. Creates real
`AttendancePunch` rows with `source='biometric'` (or the device's own
type) exactly like any other punch — no second punch pipeline.

Unknown-employee rows are recorded as `rejected` `DevicePunchLog` entries
with a clear reason, NOT routed into `InvalidPunch` — Explore confirmed
`InvalidPunch` is created lazily by HR acting on an already-flagged
`AttendancePunch` (`get_invalid_punches()`), not at ingestion time for a
punch that was never created because the employee code didn't resolve.
Wiring unknown-device-employee rows into that existing review queue is
left as a documented follow-up (see PHASE6B_REPORT.md) rather than
reshaping `InvalidPunch`'s own contract to fit a use case it wasn't built
for.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.attendance.models_device import DevicePunchLog


class DevicePushResult:
    __slots__ = ('device_punch_id', 'status', 'reason')

    def __init__(self, device_punch_id, status, reason=''):
        self.device_punch_id = device_punch_id
        self.status = status
        self.reason = reason

    def as_dict(self):
        return {'device_punch_id': self.device_punch_id, 'status': self.status, 'reason': self.reason}


def push_punches(device, rows: list[dict]) -> list[DevicePushResult]:
    """`rows`: [{'device_punch_id', 'employee_code', 'punch_type', 'device_time'}, ...].
    Returns one DevicePushResult per row, in order."""
    from apps.accounts.models import User
    from apps.attendance.models import AttendancePunch

    results = []
    for row in rows:
        device_punch_id = row['device_punch_id']
        if DevicePunchLog.objects.filter(device=device, device_punch_id=device_punch_id).exists():
            results.append(DevicePushResult(device_punch_id, 'duplicate', 'Already pushed by this device.'))
            continue

        employee = User.objects.filter(employee_id=row['employee_code']).first()
        received_at = timezone.now()
        device_time = row['device_time']
        skew_seconds = int((received_at - device_time).total_seconds())

        if employee is None:
            DevicePunchLog.objects.create(
                device=device, device_punch_id=device_punch_id, employee_code_raw=row['employee_code'],
                status='rejected', reject_reason=f"Unknown employee code '{row['employee_code']}'.",
                device_time=device_time, clock_skew_seconds=skew_seconds,
            )
            results.append(DevicePushResult(device_punch_id, 'rejected', f"Unknown employee code '{row['employee_code']}'."))
            continue

        with transaction.atomic():
            punch = AttendancePunch.objects.create(
                employee=employee, branch=device.branch, punch_type=row['punch_type'],
                punched_at=received_at, device_time=device_time, source='biometric',
                device_id=device.code, device_name=device.name,
            )
            DevicePunchLog.objects.create(
                device=device, device_punch_id=device_punch_id, employee_code_raw=row['employee_code'],
                punch=punch, status='accepted', device_time=device_time, clock_skew_seconds=skew_seconds,
            )
        device.last_seen_at = received_at
        device.save(update_fields=['last_seen_at'])
        results.append(DevicePushResult(device_punch_id, 'accepted'))

    return results
