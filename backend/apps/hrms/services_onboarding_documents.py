"""Onboarding documents shown in the employee's own "My Documents" list.

Onboarding uploads are stored in accounts.EmployeeDocument, while the ESS
"My Documents" module reads hrms.EmployeeDocumentSubmission. Rather than
duplicating files, the list endpoint merges the onboarding rows in, mapped to
the submission response shape and flagged read-only (source='onboarding').
"""
import logging

from rest_framework import serializers

from apps.accounts.models import DocumentTypeConfig, EmployeeDocument

from .models import (
    EMP_DOC_EDUCATION, EMP_DOC_EMPLOYMENT, EMP_DOC_IDENTITY, EMP_DOC_OTHER,
    EMP_DOC_PENDING, EMP_DOC_REJECTED, EMP_DOC_VERIFIED,
    EMPLOYEE_DOCUMENT_CATEGORY_CHOICES,
)

logger = logging.getLogger(__name__)

SOURCE_SUBMISSION = 'submission'
SOURCE_ONBOARDING = 'onboarding'

# Built-in onboarding document types -> My Documents category. HR-added custom types fall back to 'other'.
_CATEGORY_BY_TYPE = {
    EmployeeDocument.TYPE_PAN:              EMP_DOC_IDENTITY,
    EmployeeDocument.TYPE_AADHAAR:          EMP_DOC_IDENTITY,
    EmployeeDocument.TYPE_PASSPORT_PHOTO:   EMP_DOC_IDENTITY,
    EmployeeDocument.TYPE_CANCELLED_CHEQUE: EMP_DOC_OTHER,
    EmployeeDocument.TYPE_DEGREE:           EMP_DOC_EDUCATION,
    EmployeeDocument.TYPE_EXPERIENCE:       EMP_DOC_EMPLOYMENT,
}

_STATUS_BY_VERIFICATION = {
    EmployeeDocument.VERIFICATION_PENDING:          (EMP_DOC_PENDING, 'Pending'),
    EmployeeDocument.VERIFICATION_VERIFIED:         (EMP_DOC_VERIFIED, 'Verified'),
    EmployeeDocument.VERIFICATION_NEEDS_CORRECTION: (EMP_DOC_REJECTED, 'Rejected'),
}

_CATEGORY_LABELS = dict(EMPLOYEE_DOCUMENT_CATEGORY_CHOICES)


def _signed_file_url(document: EmployeeDocument):
    try:
        return document.file.url if document.file else None
    except Exception:
        logger.exception('Could not build file URL for onboarding document %s', document.pk)
        return None


def _type_labels() -> dict[str, str]:
    """type_key -> HR-configured label (e.g. 'pan_card' -> 'PAN Card'), shared by onboarding Step 5."""
    return dict(DocumentTypeConfig.objects.values_list('type_key', 'label'))


def _document_title(document: EmployeeDocument, labels: dict[str, str]) -> str:
    # A type HR has since deleted falls back to a readable form of its key rather than the raw upload name.
    return labels.get(document.document_type) or document.document_type.replace('_', ' ').title()


def onboarding_document_to_row(document: EmployeeDocument, labels: dict[str, str] | None = None) -> dict:
    if labels is None:
        labels = _type_labels()
    category = _CATEGORY_BY_TYPE.get(document.document_type, EMP_DOC_OTHER)
    status, status_display = _STATUS_BY_VERIFICATION.get(
        document.verification_status, (EMP_DOC_PENDING, 'Pending'),
    )
    return {
        'id': f'onb-{document.pk}',
        'source': SOURCE_ONBOARDING,
        'category': category,
        'category_display': _CATEGORY_LABELS[category],
        'title': _document_title(document, labels),
        'file_name': document.file_name,
        'file_url': _signed_file_url(document),
        'expiry_date': None,
        'tax_item': '',
        'reference_number': '',
        'status': status,
        'status_display': status_display,
        'submitted_at': document.uploaded_at,
        'reviewed_at': document.verified_at,
        'created_at': document.uploaded_at,
        'updated_at': document.updated_at,
    }


def _iso(value):
    # Same representation DRF's serializers use, so merged rows sort and render consistently.
    return serializers.DateTimeField().to_representation(value) if value else None


def onboarding_document_rows(user) -> list[dict]:
    rows = []
    labels = _type_labels()
    for doc in EmployeeDocument.objects.filter(user=user):
        row = onboarding_document_to_row(doc, labels)
        for key in ('submitted_at', 'reviewed_at', 'created_at', 'updated_at'):
            row[key] = _iso(row[key])
        rows.append(row)
    return rows


def merge_with_onboarding_documents(user, submission_rows: list) -> list:
    """Submissions plus the user's onboarding documents, newest first."""
    merged = list(submission_rows) + onboarding_document_rows(user)
    merged.sort(key=lambda row: row['submitted_at'] or '', reverse=True)
    return merged
