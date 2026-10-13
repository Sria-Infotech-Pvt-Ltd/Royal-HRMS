"""
Phase 8B Task E — policy document versions and acknowledgement campaigns.
`Document` is untouched; every existing row becomes a `PolicyDocumentVersion
.version_number=1` with its real `version` text preserved in
`legacy_version_label` — see services_policy_document_v2.migrate_document_to_version().

Scoped down: no new-joiner-checklist wiring (Task E.3's last sentence), no
compliance-report export — `acknowledgement_compliance()` returns the real
counts a report would use, formatting/export is a view-layer concern.
"""
import uuid

from django.db import models


class PolicyDocumentVersion(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey('accounts.Document', on_delete=models.CASCADE, related_name='versions_v2')
    version_number = models.PositiveSmallIntegerField()
    legacy_version_label = models.CharField(max_length=20, blank=True)
    summary_of_changes = models.TextField(blank=True)
    requires_reacknowledgement = models.BooleanField(default=False)
    acknowledgement_due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    published_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='policy_versions_published')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_policy_document_versions_v2'
        unique_together = [('document', 'version_number')]
        ordering = ['document', '-version_number']

    def __str__(self):
        return f'{self.document_id} v{self.version_number}'


class PolicyAcknowledgement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(PolicyDocumentVersion, on_delete=models.CASCADE, related_name='acknowledgements')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='policy_acknowledgements')
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    channel = models.CharField(max_length=20, default='web')

    class Meta:
        db_table = 'accounts_policy_acknowledgements_v2'
        unique_together = [('version', 'employee')]

    def __str__(self):
        return f'{self.employee_id} ack {self.version_id}'
