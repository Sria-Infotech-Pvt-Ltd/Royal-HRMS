"""
Voice approve/reject of attendance corrections (identify -> confirm), mirroring executor_approval.py's leave flow.

Aira data paths (not production's): the caller's review queue is HRCorrectionListView (attendance/views/
corrections_export.py) and the action is HRCorrectionReviewView, both dispatched directly so their permission checks and
the per-stage _can_approve_at_stage rule run unchanged - voice never re-implements or bypasses them.

Lookup is NOT limited to the first page: the whole queue is read page by page (page_size 100) so a correction beyond the
first 20 rows can still be found by name.
"""
from __future__ import annotations

from typing import Optional

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.attendance.models import AttendanceCorrection
from apps.attendance.views.corrections_export import HRCorrectionListView, HRCorrectionReviewView
from apps.voice_commands.approval_extractor import match_employee_name
from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import LANG_HI, get_current_language, text

_api_request_factory = APIRequestFactory()

_PAGE_SIZE = 100
_MAX_PAGES = 50  # safety bound: 5,000 queue rows is far beyond any real review queue

_ACTION_LABELS_HI = {'approve': 'स्वीकृत', 'reject': 'अस्वीकृत'}
_QUEUE_RETRIEVE_FAILED_MESSAGE = {
    'en': 'Could not retrieve the attendance correction review queue.',
    'hi': 'उपस्थिति सुधार समीक्षा सूची प्राप्त नहीं की जा सकी।',
}
_WHO_TO_ACTION_TEMPLATE = {
    'en': 'Whose attendance correction would you like to {action}?',
    'hi': 'आप किसका उपस्थिति सुधार {action} करना चाहेंगे?',
}
_NO_ACTIONABLE_FOR_NAME_TEMPLATE = {
    'en': 'No attendance correction awaiting your review was found for {name_query}.',
    'hi': '{name_query} के लिए आपकी समीक्षा हेतु कोई लंबित उपस्थिति सुधार नहीं मिला।',
}
_MULTIPLE_ACTIONABLE_TEMPLATE = {
    'en': (
        'More than one attendance correction awaiting your review matches "{name_query}" — '
        'could you be more specific, for example with a last name?'
    ),
    'hi': (
        '"{name_query}" से एक से अधिक लंबित उपस्थिति सुधार मेल खाते हैं — '
        'क्या आप अधिक स्पष्ट बता सकते हैं, जैसे उपनाम के साथ?'
    ),
}
# punch_type is IN/OUT/BOTH (AttendanceCorrection.PUNCH_*). Aira's button wording is Punch In / Punch Out.
_PUNCH_TYPE_LABELS = {'IN': 'punch-in', 'OUT': 'punch-out', 'BOTH': 'punch-in and punch-out'}
_PUNCH_TYPE_LABELS_HI = {'IN': 'पंच-इन', 'OUT': 'पंच-आउट', 'BOTH': 'पंच-इन और पंच-आउट'}
_CONFIRM_TEMPLATE = {
    'en': "{employee_name}'s {punch_type_display} correction for {date} — {action} this request? Please say yes or no.",
    'hi': '{employee_name} का {date} के लिए {punch_type_display} सुधार — क्या इसे {action} करें? कृपया हां या नहीं कहें।',
}
_LOST_TRACK_MESSAGE = {
    'en': 'I lost track of which attendance correction that was — please start over.',
    'hi': 'मैं भूल गया कि वह कौन सा उपस्थिति सुधार था — कृपया फिर से शुरू करें।',
}
_ACTION_FAILED_TEMPLATE = {
    'en': 'Could not {action} the attendance correction.',
    'hi': 'उपस्थिति सुधार को {action} नहीं किया जा सका।',
}
# A final approval creates the missing punch(es); an L1 approval that only escalates to L2 (HR) must not tell the
# manager the employee's attendance was already fixed.
_APPROVED_FINAL_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been approved.",
    'hi': '{employee_name} का उपस्थिति सुधार स्वीकृत कर दिया गया है।',
}
_APPROVED_ESCALATED_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been approved and sent to HR for final review.",
    'hi': '{employee_name} का उपस्थिति सुधार स्वीकृत कर दिया गया है और अंतिम समीक्षा के लिए एचआर को भेज दिया गया है।',
}
_REJECTED_TEMPLATE = {
    'en': "{employee_name}'s attendance correction has been rejected.",
    'hi': '{employee_name} का उपस्थिति सुधार अस्वीकृत कर दिया गया है।',
}


def _fetch_queue_rows(user) -> tuple[Optional[list], Optional[ExecutionResult]]:
    """Every row of the caller's correction review queue, across all pages. (rows, None) or (None, failure)."""
    rows: list = []
    page = 1
    while page <= _MAX_PAGES:
        django_request = _api_request_factory.get(
            '/api/attendance/corrections/', {'page': page, 'page_size': _PAGE_SIZE},
        )
        force_authenticate(django_request, user=user)
        response = HRCorrectionListView.as_view()(django_request)

        if response.status_code >= 400:
            message = text(_QUEUE_RETRIEVE_FAILED_MESSAGE)
            if isinstance(response.data, dict) and response.data.get('message'):
                message = response.data['message']  # external, dynamic - see executor_leave's own note
            return None, ExecutionResult(success=False, message=message)

        data = response.data.get('data') if isinstance(response.data, dict) else None
        data = data if isinstance(data, dict) else {}
        rows.extend(data.get('results', []))
        if page >= int(data.get('total_pages', 1) or 1):
            break
        page += 1
    return rows, None


def execute_identify_attendance_correction_approval_target(
    request, action: str, name_query: Optional[str],
) -> ExecutionResult:
    """
    Turn 1 (or a "be more specific" retry). Fuzzy-matches name_query against employees whose corrections THIS caller can
    act on right now (_build_row's can_action flag - a manager who is only the L1 approver on a request that has since
    moved to L2/HR is not offered it). data['outcome'] is one of need_name / zero_match / multiple_match / single_match
    (data['matched'] on the last), exactly like execute_identify_leave_approval_target.
    """
    rows, failure = _fetch_queue_rows(request.user)
    if failure:
        return failure

    candidates = [
        {
            'correction_id': row['id'], 'employee_name': row['name'],
            'date': row['date'], 'punch_type': row['punch_type'],
        }
        for row in rows
        if row.get('can_action')
    ]
    localized_action = text({'en': action, 'hi': _ACTION_LABELS_HI[action]})

    if not name_query:
        return ExecutionResult(
            success=True, message=text(_WHO_TO_ACTION_TEMPLATE).format(action=localized_action),
            data={'outcome': 'need_name'},
        )

    matches = match_employee_name(name_query, candidates)
    if not matches:
        return ExecutionResult(
            success=False, message=text(_NO_ACTIONABLE_FOR_NAME_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'zero_match'},
        )
    if len(matches) > 1:
        return ExecutionResult(
            success=True, message=text(_MULTIPLE_ACTIONABLE_TEMPLATE).format(name_query=name_query),
            data={'outcome': 'multiple_match'},
        )

    matched = matches[0]
    punch_type_display = text({
        'en': _PUNCH_TYPE_LABELS.get(matched['punch_type'], matched['punch_type']),
        'hi': _PUNCH_TYPE_LABELS_HI.get(matched['punch_type'], matched['punch_type']),
    })
    # No TTS redaction: punch type and date carry no sensitive category, and the caller needs both to confirm by voice.
    message = text(_CONFIRM_TEMPLATE).format(
        employee_name=matched['employee_name'], punch_type_display=punch_type_display,
        date=matched['date'], action=localized_action,
    )
    return ExecutionResult(success=True, message=message, data={'outcome': 'single_match', 'matched': matched})


def execute_confirm_attendance_correction_approval(
    request, action: str, correction_id: Optional[str],
) -> ExecutionResult:
    """Confirmation turn ("yes"): HRCorrectionReviewView.patch() decides. If eligibility changed since the identify turn
    (already actioned, moved past this caller's stage), that view's real rejection is surfaced - never a stale success."""
    if not correction_id:
        return ExecutionResult(success=False, message=text(_LOST_TRACK_MESSAGE))

    django_request = _api_request_factory.patch(
        f'/api/attendance/corrections/{correction_id}/review/', {'action': action}, format='json',
    )
    force_authenticate(django_request, user=request.user)
    response = HRCorrectionReviewView.as_view()(django_request, pk=correction_id)

    if response.status_code >= 400:
        message = text(_ACTION_FAILED_TEMPLATE).format(action=text({'en': action, 'hi': _ACTION_LABELS_HI[action]}))
        if isinstance(response.data, dict) and response.data.get('message'):
            message = response.data['message']  # external, dynamic - see executor_leave's own note
        return ExecutionResult(success=False, message=message, data=response.data)

    data = response.data.get('data') if isinstance(response.data, dict) else None
    employee_name = data.get('name') if isinstance(data, dict) else None
    new_status = data.get('status') if isinstance(data, dict) else None

    if action == 'approve':
        template = (
            _APPROVED_ESCALATED_TEMPLATE if new_status == AttendanceCorrection.STATUS_L2_PENDING
            else _APPROVED_FINAL_TEMPLATE
        )
    else:
        template = _REJECTED_TEMPLATE

    subject_hi, subject_en = employee_name or 'कर्मचारी', employee_name or 'The employee'
    subject = subject_hi if get_current_language() == LANG_HI else subject_en
    return ExecutionResult(success=True, message=text(template).format(employee_name=subject), data=data)
