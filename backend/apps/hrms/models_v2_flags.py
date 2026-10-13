"""
Phase 8B Task H — one shared entitlement model for all 7 of this phase's
flags (expenses.v2/separation.v2/helpdesk.v2/announcements.v2/
documents.v2/assets.v2/voice.v2), parameterized by `module_code`, rather
than 7 near-identical model classes — same real on/off semantics as every
other *V2Entitlement this session has built, just consolidated since all
7 share the exact same shape (no per-module extra fields needed)."""
import uuid

from django.db import models


class ModuleV2Entitlement(models.Model):
    MODULE_EXPENSES      = 'expenses'
    MODULE_SEPARATION    = 'separation'
    MODULE_HELPDESK      = 'helpdesk'
    MODULE_ANNOUNCEMENTS = 'announcements'
    MODULE_DOCUMENTS     = 'documents'
    MODULE_ASSETS        = 'assets'
    MODULE_VOICE         = 'voice'
    # Phase 9A Task J — reuses MODULE_DOCUMENTS for the Task E document-
    # template-engine flag too (the master prompt names "documents.v2" in
    # both 8B's policy-document module and 9A's document-generation
    # module — one flag code, both meanings, rather than inventing a
    # second confusingly-similar name).
    MODULE_REPORTS       = 'reports'
    MODULE_CHOICES = [
        (MODULE_EXPENSES, 'Expenses'), (MODULE_SEPARATION, 'Separation'), (MODULE_HELPDESK, 'Help desk'),
        (MODULE_ANNOUNCEMENTS, 'Announcements'), (MODULE_DOCUMENTS, 'Documents'),
        (MODULE_ASSETS, 'Assets'), (MODULE_VOICE, 'Voice'), (MODULE_REPORTS, 'Reports'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module_code = models.CharField(max_length=20, choices=MODULE_CHOICES, unique=True)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hrms_module_v2_entitlements_v2'

    def __str__(self):
        return f'{self.module_code}.v2: {"ON" if self.is_enabled else "off"}'
