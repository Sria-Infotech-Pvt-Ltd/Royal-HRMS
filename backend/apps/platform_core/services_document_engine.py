"""
Phase 9A Task E — render a DocumentTemplate against a flat context dict of
DECLARED variables only (never attribute-chain traversal, never Python's
str.format/Jinja2 on raw template text), enforce field security at
generation time, and manage GeneratedDocument immutability/revocation.
"""
import hashlib
import re

from django.db import transaction
from django.utils import timezone

from apps.platform_core.models import ClickToAcceptSignature, DocumentTemplate, GeneratedDocument

_VARIABLE_RE = re.compile(r'\{\{(\w+)\}\}')


class UndeclaredVariableError(Exception):
    pass


class SensitiveFieldNotPermittedError(Exception):
    pass


class DocumentImmutableError(Exception):
    pass


def referenced_variables(template: DocumentTemplate) -> set:
    return set(_VARIABLE_RE.findall(template.body))


def render_template(template: DocumentTemplate, context: dict, *, sensitive_vars_permitted: set | None = None) -> str:
    """`context` must be a flat {variable_name: resolved_value} dict the
    CALLER builds (reading real model fields) — this function has no
    knowledge of User/Position/etc. models at all, matching the "no
    attribute access beyond declared variables" rule exactly: there is
    nothing here TO traverse beyond a plain dict lookup."""
    used = referenced_variables(template)
    undeclared = used - set(template.declared_variables)
    if undeclared:
        raise UndeclaredVariableError(f'Template {template.code} body references undeclared variable(s): {sorted(undeclared)}')

    if template.requires_sensitive_field_check:
        # Intentionally conservative: if the template is flagged as using
        # sensitive data at all, every referenced variable must be
        # explicitly permitted (passed in by the caller, who resolved it
        # against FieldDefinition.is_sensitive for THIS viewer) —
        # "generation fails with a clear message, no silent blanks" per
        # Task E.3.
        sensitive_vars_permitted = sensitive_vars_permitted or set()
        unpermitted = used - sensitive_vars_permitted
        if unpermitted:
            raise SensitiveFieldNotPermittedError(
                f'Not entitled to variable(s) {sorted(unpermitted)} required by template {template.code}.'
            )

    missing_context = used - set(context.keys())
    if missing_context:
        raise UndeclaredVariableError(f'Context is missing value(s) for declared variable(s): {sorted(missing_context)}')

    def _substitute(match):
        return str(context[match.group(1)])

    return _VARIABLE_RE.sub(_substitute, template.body)


@transaction.atomic
def generate_document(template: DocumentTemplate, context: dict, generated_by, *, record=None,
                       sensitive_vars_permitted: set | None = None, visible_to_employee: bool = True) -> GeneratedDocument:
    rendered_text = render_template(template, context, sensitive_vars_permitted=sensitive_vars_permitted)
    checksum = hashlib.sha256(rendered_text.encode('utf-8')).hexdigest()

    document = GeneratedDocument.objects.create(
        template=template, rendered_text=rendered_text, checksum_sha256=checksum,
        generated_by=generated_by, status=GeneratedDocument.STATUS_DRAFT, visible_to_employee=visible_to_employee,
    )
    if record is not None:
        from django.contrib.contenttypes.models import ContentType
        document.record_content_type = ContentType.objects.get_for_model(record)
        document.record_object_id = str(record.pk)
        document.save(update_fields=['record_content_type', 'record_object_id'])
    return document


def issue_document(document: GeneratedDocument) -> GeneratedDocument:
    if document.status != GeneratedDocument.STATUS_DRAFT:
        raise DocumentImmutableError(f'Document {document.id} is {document.status}, not draft — cannot re-issue.')
    document.status = GeneratedDocument.STATUS_ISSUED
    document.save(update_fields=['status'])
    return document


@transaction.atomic
def revoke_and_reissue(document: GeneratedDocument, new_context: dict, reason: str, generated_by,
                        *, sensitive_vars_permitted: set | None = None) -> GeneratedDocument:
    """Issued documents are immutable — a 'correction' is always a NEW
    GeneratedDocument linked via `revokes`, never an edit of the old one."""
    if document.status not in (GeneratedDocument.STATUS_ISSUED, GeneratedDocument.STATUS_SIGNED):
        raise DocumentImmutableError(f'Document {document.id} is {document.status} — only issued/signed documents can be revoked.')
    if not reason.strip():
        raise ValueError('A revocation reason is required.')

    document.status = GeneratedDocument.STATUS_REVOKED
    document.revoked_reason = reason
    document.save(update_fields=['status', 'revoked_reason'])

    new_document = generate_document(
        document.template, new_context, generated_by,
        sensitive_vars_permitted=sensitive_vars_permitted, visible_to_employee=document.visible_to_employee,
    )
    new_document.revokes = document
    new_document.save(update_fields=['revokes'])
    return new_document


def record_click_to_accept(document: GeneratedDocument, signer, signer_role: str, signed_name: str, ip_address=None) -> ClickToAcceptSignature:
    signature = ClickToAcceptSignature.objects.create(
        document=document, signer=signer, signer_role=signer_role, signed_name=signed_name,
        document_checksum_at_signing=document.checksum_sha256, ip_address=ip_address,
    )
    if document.status == GeneratedDocument.STATUS_ISSUED:
        document.status = GeneratedDocument.STATUS_SIGNED
        document.save(update_fields=['status'])
    return signature
