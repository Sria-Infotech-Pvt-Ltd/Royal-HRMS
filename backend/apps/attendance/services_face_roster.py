"""Who has, and has not, completed Face ID registration: each employee's state, the filter on it, and the overall counts.

An employee's state, for this list:
  approved  they have a usable Face ID (an approved registration that is also the active reference)
  pending   no usable Face ID, and a registration is waiting for approval
  rejected  no usable Face ID, nothing waiting, and a registration was rejected
  none      no registration at all
"Not completed" means any state other than approved.
"""
from django.db.models import Case, CharField, Count, Exists, OuterRef, Q, Value, When

from apps.attendance.models import FaceRegistrationRequest

STATES = ('approved', 'pending', 'rejected', 'none')
# Filter words the page may send: a state, or "incomplete" for everyone who has not completed registration.
FILTERS = STATES + ('incomplete',)


def _has(employee_ref: str, **conditions) -> Exists:
    return Exists(FaceRegistrationRequest.objects.filter(employee_id=OuterRef(employee_ref), **conditions))


def annotate_face_state(employees):
    """Adds `_face_state` to each employee, worked out in the database (no query per person)."""
    return employees.annotate(_face_state=Case(
        When(_has('pk', status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True), then=Value('approved')),
        When(_has('pk', status=FaceRegistrationRequest.STATUS_PENDING), then=Value('pending')),
        When(_has('pk', status=FaceRegistrationRequest.STATUS_REJECTED), then=Value('rejected')),
        default=Value('none'), output_field=CharField(),
    ))


def apply_face_filter(annotated, face_filter: str):
    """Narrow an annotated list by a filter word; an unknown or empty word leaves it unchanged."""
    face_filter = (face_filter or '').strip().lower()
    if face_filter == 'incomplete':
        return annotated.exclude(_face_state='approved')
    if face_filter in STATES:
        return annotated.filter(_face_state=face_filter)
    return annotated


def face_counts(annotated) -> dict:
    """How many employees are in each state, and how many have not completed registration."""
    totals = annotated.aggregate(
        total=Count('pk'),
        **{state: Count('pk', filter=Q(_face_state=state)) for state in STATES},
    )
    totals['incomplete'] = totals['total'] - totals['approved']
    return totals
