"""
Late-arrival justification (AttendanceCorrection, kind=late_justification).

An employee explains a day marked late — Medical, Transport, Personal or
Other — within LATE_JUSTIFICATION_WINDOW_DAYS calendar days. Medical needs
proof (PDF / JPG / PNG, at most 5 MB, checked by content). It goes through
the same Manager (L1) → HR (L2) chain as punch corrections
(apps.attendance.services_hr_corrections). Reviewers approve, reject (reason
required) or ask for a resubmission (reason required); the employee then
resubmits the same request, optionally with replacement proof.

Full approval marks the AttendanceRecord late_excused: the punches and the
"late" status stay as they were, the day is shown "Late (Excused)", and
payroll does not count it as a late mark (apps.payroll.views.cycles).

Medical proof is visible only to the employee who uploaded it and to users
holding attendance.medical_proof_view (or settings.edit) who can reach the
request — never to a reviewer just because they are its manager.
"""
from __future__ import annotations

import datetime
import io
import os

from django.db import transaction
from django.utils import timezone

from core.permissions import has_perm

from apps.attendance.models import AttendanceAuditLog, AttendanceCorrection, AttendanceRecord

LATE_JUSTIFICATION_WINDOW_DAYS = 3
PROOF_MAX_BYTES = 5 * 1024 * 1024
MEDICAL_PROOF_PERMISSION = 'attendance.medical_proof_view'
EXPLANATION_MIN, EXPLANATION_MAX = 10, 1000

_PROOF_TYPES = {
    # extension → (format, content type)
    '.pdf':  ('PDF', 'application/pdf'),
    '.jpg':  ('JPEG', 'image/jpeg'),
    '.jpeg': ('JPEG', 'image/jpeg'),
    '.png':  ('PNG', 'image/png'),
}
CONTENT_TYPES = {fmt: ct for fmt, ct in _PROOF_TYPES.values()}


class LateJustificationError(Exception):
    """A caller-fixable problem; `field` names the request field when there is one."""

    def __init__(self, message: str, field: str = ''):
        super().__init__(message)
        self.field = field


# ── Proof validation ──────────────────────────────────────────────────────────

def detect_format(head: bytes) -> str | None:
    if head.startswith(b'%PDF-'):
        return 'PDF'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'PNG'
    if head.startswith(b'\xff\xd8\xff'):
        return 'JPEG'
    return None


def validate_proof(upload) -> None:
    """Size, extension and the file's actual content (not its name or declared type)."""
    if upload is None:
        return
    size = getattr(upload, 'size', None) or 0
    if size <= 0:
        raise LateJustificationError('The proof file is empty.', 'document')
    if size > PROOF_MAX_BYTES:
        raise LateJustificationError('The proof file must be 5 MB or smaller.', 'document')
    ext = os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()
    if ext not in _PROOF_TYPES:
        raise LateJustificationError('Upload a PDF, JPG or PNG file.', 'document')
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    fmt = detect_format(data[:16])
    if fmt is None or fmt != _PROOF_TYPES[ext][0]:
        raise LateJustificationError('The file is not a valid PDF, JPG or PNG (its content does not match).',
                                     'document')
    if fmt == 'PDF':
        if b'%%EOF' not in data[-2048:]:
            raise LateJustificationError('The PDF file is incomplete or damaged.', 'document')
        return
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            if img.format != fmt:
                raise ValueError
            img.verify()
    except Exception:
        raise LateJustificationError('The image file is damaged or not a real JPG / PNG.', 'document') from None


# ── Eligibility ───────────────────────────────────────────────────────────────

def _today() -> datetime.date:
    return timezone.localdate()


def deadline_for(day: datetime.date) -> datetime.date:
    return day + datetime.timedelta(days=LATE_JUSTIFICATION_WINDOW_DAYS)


def late_record(employee, day: datetime.date) -> AttendanceRecord:
    record = AttendanceRecord.objects.filter(employee=employee, date=day).first()
    if record is None or not record.is_late:
        raise LateJustificationError('You can only explain a day on which you were marked late.', 'date')
    return record


def open_or_approved(employee, day: datetime.date):
    return (AttendanceCorrection.objects
            .filter(employee=employee, date=day, kind=AttendanceCorrection.KIND_LATE,
                    status__in=(*AttendanceCorrection.OPEN_STATUSES, AttendanceCorrection.STATUS_APPROVED))
            .order_by('-created_at').first())


def check_eligible(employee, day: datetime.date) -> AttendanceRecord:
    today = _today()
    if day > today:
        raise LateJustificationError('The date cannot be in the future.', 'date')
    if today > deadline_for(day):
        raise LateJustificationError(
            f'Late arrivals can be explained within {LATE_JUSTIFICATION_WINDOW_DAYS} calendar days '
            f'(by {deadline_for(day):%d %b %Y}).', 'date')
    record = late_record(employee, day)
    existing = open_or_approved(employee, day)
    if existing is not None:
        if existing.status == AttendanceCorrection.STATUS_APPROVED:
            raise LateJustificationError('This late arrival is already excused.', 'date')
        raise LateJustificationError('You already have an open justification for this date.', 'date')
    return record


def can_explain(employee, record: AttendanceRecord, open_dates: set) -> bool:
    """For the calendar / history: a late day still inside the window without an open or approved request."""
    return (record.is_late and not record.late_excused and record.date not in open_dates
            and record.date <= _today() <= deadline_for(record.date))


def _clean(reason: str, explanation: str) -> str:
    if reason not in AttendanceCorrection.LATE_REASONS:
        raise LateJustificationError('Choose Medical, Transport, Personal or Other.', 'reason')
    explanation = (explanation or '').strip()
    if len(explanation) < EXPLANATION_MIN:
        raise LateJustificationError(f'Explain what happened (at least {EXPLANATION_MIN} characters).',
                                     'explanation')
    if len(explanation) > EXPLANATION_MAX:
        raise LateJustificationError(f'Keep the explanation under {EXPLANATION_MAX} characters.', 'explanation')
    return explanation


# ── Submit / resubmit ─────────────────────────────────────────────────────────

def _audit(correction, event, user, action, new_value='', remarks=''):
    from apps.attendance.services_audit_log import write_audit_log
    write_audit_log(employee=correction.employee, date=correction.date, event=event, performed_by=user,
                    record=correction.attendance_record, new_value=new_value[:200], action=action[:300],
                    remarks=remarks)


def _proof_note(upload) -> str:
    # The original file name can contain a patient's name — never logged.
    if upload is None:
        return 'no proof attached'
    ext = os.path.splitext(upload.name or '')[1].lower().lstrip('.').upper()
    return f'proof attached ({ext}, {max(1, round(upload.size / 1024))} KB)'


def _safe_name(upload) -> str:
    return os.path.basename(upload.name or 'proof')[:255]


def submit(*, employee, day: datetime.date, reason: str, explanation: str, document=None) -> AttendanceCorrection:
    from apps.attendance.services_hr_corrections import _resolve_approval_chain
    explanation = _clean(reason, explanation)
    if reason == AttendanceCorrection.REASON_MEDICAL and document is None:
        raise LateJustificationError('Medical reasons need proof — upload a PDF, JPG or PNG.', 'document')
    validate_proof(document)
    with transaction.atomic():
        record = check_eligible(employee, day)
        # Lock the employee's rows for the date so two submissions cannot both pass.
        list(AttendanceCorrection.objects.select_for_update()
             .filter(employee=employee, date=day, kind=AttendanceCorrection.KIND_LATE))
        if open_or_approved(employee, day) is not None:
            raise LateJustificationError('You already have an open justification for this date.', 'date')
        l1, l2 = _resolve_approval_chain(employee)
        skip_l1 = bool(employee.role and employee.role.can_manage_team) or l1 is None
        correction = AttendanceCorrection(
            employee=employee, kind=AttendanceCorrection.KIND_LATE, date=day, punch_type='',
            reason=reason, notes=explanation, attendance_record=record, created_by=employee,
            status=AttendanceCorrection.STATUS_L2_PENDING if skip_l1 else AttendanceCorrection.STATUS_PENDING,
            l1_approver=None if skip_l1 else l1, l2_approver=l2,
        )
        if document is not None:
            correction.document_name = _safe_name(document)
            correction.supporting_document = document
        correction.save()
        _audit(correction, AttendanceAuditLog.EVENT_LATE_SUBMITTED, employee,
               f'Late arrival justification submitted ({correction.get_reason_display()})', _proof_note(document))
    return correction


def resubmit(*, employee, correction_id, explanation: str, reason: str | None = None,
             document=None) -> AttendanceCorrection:
    from apps.attendance.services_hr_corrections import _resolve_approval_chain
    with transaction.atomic():
        correction = (AttendanceCorrection.objects.select_for_update()
                      .filter(pk=correction_id, employee=employee, kind=AttendanceCorrection.KIND_LATE).first())
        if correction is None:
            raise LateJustificationError('Request not found.', 'not_found')
        if correction.status != AttendanceCorrection.STATUS_RESUBMIT:
            raise LateJustificationError('Only a request marked "Resubmission Required" can be resubmitted.')
        asked = timezone.localtime(correction.resubmission_requested_at).date() \
            if correction.resubmission_requested_at else correction.date
        if _today() > deadline_for(asked):
            raise LateJustificationError(
                f'Resubmit within {LATE_JUSTIFICATION_WINDOW_DAYS} calendar days of the request '
                f'(by {deadline_for(asked):%d %b %Y}).')
        reason = reason or correction.reason
        explanation = _clean(reason, explanation)
        validate_proof(document)
        if reason == AttendanceCorrection.REASON_MEDICAL and document is None and not correction.supporting_document:
            raise LateJustificationError('Medical reasons need proof — upload a PDF, JPG or PNG.', 'document')

        l1, l2 = _resolve_approval_chain(employee)
        skip_l1 = bool(employee.role and employee.role.can_manage_team) or l1 is None
        correction.reason, correction.notes = reason, explanation
        if document is not None:
            correction.document_name = _safe_name(document)
            correction.supporting_document = document       # the previous file stays in storage
        correction.status = AttendanceCorrection.STATUS_L2_PENDING if skip_l1 else AttendanceCorrection.STATUS_PENDING
        correction.l1_approver = None if skip_l1 else l1
        correction.l2_approver = l2
        # The previous decision and its reason stay in the audit log.
        correction.l1_status = correction.l2_status = None
        correction.l1_remarks = correction.l2_remarks = ''
        correction.l1_actioned_at = correction.l2_actioned_at = None
        correction.reviewed_by, correction.reviewed_at = None, None
        correction.resubmission_count += 1
        correction.resubmission_requested_at = None
        correction.save()
        _audit(correction, AttendanceAuditLog.EVENT_LATE_RESUBMITTED, employee,
               f'Late arrival justification resubmitted (#{correction.resubmission_count}, '
               f'{correction.get_reason_display()})',
               _proof_note(document) if document is not None else 'previous proof kept'
               if correction.supporting_document else 'no proof attached')
    return correction


# ── Review side effects (called from services_hr_corrections) ────────────────

def mark_excused(correction, actioning_user) -> None:
    """Final approval: excuse the late day. Punches and status are not touched."""
    record = (AttendanceRecord.objects.select_for_update()
              .filter(pk=correction.attendance_record_id).first()
              or AttendanceRecord.objects.select_for_update()
              .filter(employee=correction.employee, date=correction.date).first())
    if record is None:
        return
    AttendanceRecord.objects.filter(pk=record.pk).update(late_excused=True, updated_at=timezone.now())
    correction.attendance_record = record
    _audit(correction, AttendanceAuditLog.EVENT_LATE_EXCUSED, actioning_user,
           'Late arrival excused — excluded from late-mark deductions',
           f'punch-in {record.first_punch_in:%H:%M} kept' if record.first_punch_in else '')


def audit_review(correction, actioning_user, *, stage: str, decision: str, remarks: str) -> None:
    who = 'Manager' if stage == 'l1' else 'HR'
    event, verb = {
        'approve': (AttendanceAuditLog.EVENT_LATE_APPROVED, 'approved'),
        'reject': (AttendanceAuditLog.EVENT_LATE_REJECTED, 'rejected'),
        'resubmit': (AttendanceAuditLog.EVENT_LATE_RESUBMIT_ASKED, 'sent back for resubmission'),
    }[decision]
    _audit(correction, event, actioning_user, f'Late arrival justification {verb} by {who}', remarks=remarks)


# ── Medical proof access ──────────────────────────────────────────────────────

def can_view_document(user, correction) -> bool:
    """The uploader, or a user explicitly granted medical-proof access who can
    reach this request (branch / assignment rules of the review queue)."""
    if user is None or not correction.supporting_document:
        return False
    if correction.employee_id == user.id:
        return True
    if not has_perm(user, MEDICAL_PROOF_PERMISSION):
        return False
    if has_perm(user, 'settings.edit'):
        return True
    from apps.attendance.services_hr_corrections import _is_branch_admin, _branch_admin_covers, _user_branch
    if _is_branch_admin(user):
        return _branch_admin_covers(user, correction.employee)
    branch = _user_branch(user)
    return not branch or (correction.employee.branch or '').strip() == branch


def read_document(correction) -> tuple[bytes, str]:
    field = correction.supporting_document
    reader = getattr(field.storage, 'read_via_download_api', None)
    if reader:
        content = reader(field.name)
    else:
        with field.open('rb') as fh:
            content = fh.read()
    fmt = detect_format(content[:16])
    if fmt is None:
        raise ValueError('unrecognised stored proof')
    return content, CONTENT_TYPES[fmt]
