"""Phase 8B Task E — migrate each Document to a v1 PolicyDocumentVersion, acknowledgement campaigns, compliance counts."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Document, PolicyAcknowledgement, PolicyDocumentVersion


@transaction.atomic
def migrate_document_to_version(document: Document) -> PolicyDocumentVersion:
    """Idempotent — one PolicyDocumentVersion(version_number=1) per
    Document, with the old free-text `version` preserved verbatim."""
    existing = document.versions_v2.filter(version_number=1).first()
    if existing is not None:
        return existing
    return PolicyDocumentVersion.objects.create(
        document=document, version_number=1, legacy_version_label=document.version,
        status=PolicyDocumentVersion.STATUS_PUBLISHED if document.is_active else PolicyDocumentVersion.STATUS_DRAFT,
    )


@transaction.atomic
def publish_new_version(document: Document, summary_of_changes: str, published_by, requires_reacknowledgement: bool = False, acknowledgement_due_at=None) -> PolicyDocumentVersion:
    latest = document.versions_v2.order_by('-version_number').first()
    next_number = (latest.version_number if latest else 0) + 1
    return PolicyDocumentVersion.objects.create(
        document=document, version_number=next_number, summary_of_changes=summary_of_changes,
        requires_reacknowledgement=requires_reacknowledgement, acknowledgement_due_at=acknowledgement_due_at,
        published_by=published_by, status=PolicyDocumentVersion.STATUS_PUBLISHED,
    )


def record_acknowledgement(version: PolicyDocumentVersion, employee, ip_address=None, channel='web') -> PolicyAcknowledgement:
    acknowledgement, _ = PolicyAcknowledgement.objects.get_or_create(
        version=version, employee=employee, defaults={'ip_address': ip_address, 'channel': channel},
    )
    return acknowledgement


def compliance_counts(version: PolicyDocumentVersion, audience_employee_ids) -> dict:
    audience_employee_ids = set(audience_employee_ids)
    acknowledged = set(version.acknowledgements.values_list('employee_id', flat=True))
    pending = audience_employee_ids - acknowledged
    is_overdue = version.acknowledgement_due_at is not None and timezone.now() > version.acknowledgement_due_at
    return {
        'acknowledged_count': len(acknowledged & audience_employee_ids),
        'pending_count': len(pending),
        'pending_employee_ids': pending,
        'is_overdue': is_overdue,
    }
