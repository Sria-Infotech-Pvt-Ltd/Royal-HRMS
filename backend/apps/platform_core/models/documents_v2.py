"""
Phase 9A Task E/F/G — document template engine, generated documents, and
e-signature placeholders.

Renderer choice, stated plainly (Task E.1's own "document the choice and
reason"): reuses the EXISTING reportlab stack (already proven in
services_employment_letter.py/services_payslip_pdf.py/services_form16_pdf.py)
rather than adding a new HTML-to-PDF dependency. A template's `body` is
plain text/simple markup with `{{variable}}` placeholders (NOT a general
HTML/CSS layout engine) — reportlab Paragraphs render basic `<b>`/`<br/>`
tags already, so this covers every existing letter's actual formatting
needs without a new rendering stack to sandbox and maintain. DOCX output
is NOT built (no DOCX generation existed anywhere in this codebase before
this phase — confirmed by direct search).

The variable substitution itself is NOT Python's str.format/Jinja2 on raw
user input — `services_document_engine.render_template()` only resolves
DECLARED variable names (TemplateVariable rows) via a flat context dict
the caller builds explicitly, through a `{{var}}`-only regex substitution,
never `eval()`/`exec()`/attribute-chain traversal. This is the same "no
attribute access beyond declared variables" sandbox boundary Task E.2
requires, just simpler than a templating engine since every variable is a
single resolved string by the time rendering happens.
"""
import uuid

from django.db import models


class DocumentTemplate(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=150)
    document_type = models.CharField(max_length=60, help_text='Lookup code, e.g. "offer_letter", "relieving_letter" — matches 5B action letter_template codes.')
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_templates')
    language_code = models.CharField(max_length=10, default='en')
    # Declared variables this template may reference — e.g.
    # ["employee_full_name", "employee_id", "designation", "department", "joining_date"].
    # render_template() raises if the body references anything not in this list.
    declared_variables = models.JSONField(default=list)
    body = models.TextField(help_text='{{variable}} placeholders only, plus <b>/<br/> for basic reportlab formatting.')
    header_text = models.CharField(max_length=300, blank=True)
    footer_text = models.CharField(max_length=300, blank=True)
    watermark_text = models.CharField(max_length=60, blank=True, help_text='e.g. "DRAFT", "CONFIDENTIAL" — blank = no watermark.')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    requires_sensitive_field_check = models.BooleanField(default=False, help_text='True if any declared variable is sourced from an is_sensitive FieldDefinition — enforced at generation time.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_document_templates_v2'
        unique_together = [('code', 'version')]
        ordering = ['code', '-version']

    def __str__(self):
        return f'{self.code} v{self.version}'


class GeneratedDocument(models.Model):
    STATUS_DRAFT   = 'draft'
    STATUS_ISSUED  = 'issued'
    STATUS_SIGNED  = 'signed'
    STATUS_REVOKED = 'revoked'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_ISSUED, 'Issued'), (STATUS_SIGNED, 'Signed'), (STATUS_REVOKED, 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, related_name='generated_documents')
    # Generic link to whatever record this document is about (employee,
    # HireAction, Offer, PayrollRun, Enrolment, CustomRecord...) — reuses
    # the same generic content_type/object_id pattern ChangeHistory
    # already uses, rather than a new FK per possible source model.
    record_content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    record_object_id = models.CharField(max_length=64, blank=True)
    rendered_text = models.TextField(help_text='The final substituted text — stored so a revoked/old version is still inspectable without re-rendering.')
    checksum_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    generated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='documents_generated')
    generated_at = models.DateTimeField(auto_now_add=True)
    visible_to_employee = models.BooleanField(default=True)
    revoked_reason = models.CharField(max_length=300, blank=True)
    revokes = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='revoked_by_documents')

    class Meta:
        db_table = 'platform_generated_documents_v2'
        ordering = ['-generated_at']

    def __str__(self):
        return f'{self.template.code} for {self.record_object_id} ({self.status})'


class ClickToAcceptSignature(models.Model):
    """Task G.2 — an internal 'click-to-accept' acceptance record (name,
    timestamp, IP, document checksum) for offer acceptance / policy
    acknowledgement / asset acknowledgement flows. Immutable — no update()
    path provided by services_document_engine for this model."""
    SIGNER_EMPLOYEE  = 'employee'
    SIGNER_MANAGER   = 'manager'
    SIGNER_HR        = 'hr'
    SIGNER_AUTHORISED = 'authorised_signatory'
    SIGNER_CHOICES = [
        (SIGNER_EMPLOYEE, 'Employee'), (SIGNER_MANAGER, 'Manager'),
        (SIGNER_HR, 'HR'), (SIGNER_AUTHORISED, 'Authorised signatory'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(GeneratedDocument, on_delete=models.CASCADE, related_name='click_to_accept_signatures')
    signer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='documents_signed')
    signer_role = models.CharField(max_length=30, choices=SIGNER_CHOICES)
    signed_name = models.CharField(max_length=200, help_text='Full name as typed/confirmed at signing time — captured even if the User record later changes.')
    document_checksum_at_signing = models.CharField(max_length=64)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_click_to_accept_signatures_v2'
        ordering = ['-signed_at']

    def __str__(self):
        return f'{self.signed_name} signed {self.document_id} as {self.signer_role}'


class ExternalSignatureRequest(models.Model):
    """Task G.3 — provider INTERFACE only, no provider implemented. A row
    here just tracks "we asked an external e-signature provider to get
    this signed" — services_document_engine never actually calls any real
    provider API."""
    STATUS_SENT      = 'sent'
    STATUS_SIGNED    = 'signed'
    STATUS_DECLINED  = 'declined'
    STATUS_EXPIRED   = 'expired'
    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'), (STATUS_SIGNED, 'Signed'), (STATUS_DECLINED, 'Declined'), (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(GeneratedDocument, on_delete=models.CASCADE, related_name='external_signature_request')
    provider_code = models.CharField(max_length=40, blank=True, help_text='No provider implemented — this names which one WOULD be called.')
    provider_reference_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_external_signature_requests_v2'

    def __str__(self):
        return f'{self.document_id}: {self.status} via {self.provider_code or "(no provider)"}'
