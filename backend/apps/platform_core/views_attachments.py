"""
Phase 2 Task H — generic attachment upload/download. Reuses
core.file_validation.validate_file_content (content-sniffing, not just
the client-supplied Content-Type header) exactly like every other
upload path in this codebase (apps/accounts/views/custom_field_files.py),
rather than inventing a second validation approach.

Permission model (documented limitation — see PHASE2_REPORT.md): for a
CUSTOM entity's record, access follows that entity's own
view/change permission (services_custom_objects.permission_codename).
For a CORE entity's record there is no generic per-entity permission in
this phase (Task F deliberately left core-entity write access to each
entity's own existing endpoints) — so core-entity attachments are gated
by `settings.edit` here until each core entity defines its own
attachment permission in a later phase. This is narrower than it will
eventually be, never broader.
"""
from __future__ import annotations

import hashlib

from django.contrib.contenttypes.models import ContentType
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.file_validation import validate_file_content
from core.permissions import has_perm
from core.responses import error, success

from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import AttachmentValue, CustomRecord, EntityDefinition, FieldDefinition

MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5MB — matches CLAUDE.md's project-wide file-upload cap.

_ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/msword', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


def _content_type_for_entity(entity: EntityDefinition) -> ContentType:
    if entity.kind == EntityDefinition.KIND_CUSTOM:
        return ContentType.objects.get_for_model(CustomRecord)
    from django.apps import apps as django_apps
    model = django_apps.get_model(entity.app_label, entity.model_name)
    return ContentType.objects.get_for_model(model)


def _can_access_record(entity: EntityDefinition, record_pk: str, user, *, write: bool) -> bool:
    if entity.kind == EntityDefinition.KIND_CUSTOM:
        action = 'change' if write else 'view'
        return has_perm(user, custom_objects.permission_codename(entity.code, action))
    return has_perm(user, 'settings.edit')


class AttachmentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, entity_code, record_id, field_code):
        entity = EntityDefinition.objects.filter(code=entity_code).first()
        if entity is None:
            return error('Unknown entity.', http_status=404)
        field = FieldDefinition.objects.filter(
            entity=entity, code=field_code, status=FieldDefinition.STATUS_PUBLISHED, data_type__in=['file', 'image'],
        ).first()
        if field is None:
            return error('Unknown or non-file field.', http_status=404)
        if not _can_access_record(entity, record_id, request.user, write=True):
            return error('You do not have permission to upload here.', http_status=403)

        uploaded = request.FILES.get('file')
        if uploaded is None:
            return error('No file provided.', http_status=400)
        if uploaded.size > MAX_ATTACHMENT_SIZE:
            return error('File exceeds the 5MB upload limit.', http_status=400)
        if uploaded.content_type not in _ALLOWED_CONTENT_TYPES:
            return error('This file type is not allowed.', http_status=400)

        mismatch = validate_file_content(uploaded, uploaded.content_type)
        if mismatch:
            return error(mismatch, http_status=400)

        digest = hashlib.sha256()
        for chunk in uploaded.chunks():
            digest.update(chunk)
        uploaded.seek(0)

        content_type_row = _content_type_for_entity(entity)
        attachment = AttachmentValue.objects.create(
            content_type=content_type_row, object_id=str(record_id), field=field,
            file=uploaded, original_name=uploaded.name[:255], size=uploaded.size,
            mime_type=uploaded.content_type, checksum=digest.hexdigest(), uploaded_by=request.user,
        )
        return success('File uploaded.', {
            'id': attachment.pk, 'original_name': attachment.original_name, 'size': attachment.size,
            'mime_type': attachment.mime_type, 'uploaded_at': attachment.uploaded_at.isoformat(),
        }, http_status=201)


class AttachmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code, record_id, field_code):
        entity = EntityDefinition.objects.filter(code=entity_code).first()
        if entity is None:
            return error('Unknown entity.', http_status=404)
        if not _can_access_record(entity, record_id, request.user, write=False):
            return error('You do not have permission to view this.', http_status=403)

        qs = AttachmentValue.objects.filter(
            object_id=str(record_id), field__entity=entity, field__code=field_code, is_deleted=False,
        )
        data = [{
            'id': a.pk, 'original_name': a.original_name, 'size': a.size,
            'mime_type': a.mime_type, 'uploaded_at': a.uploaded_at.isoformat(),
        } for a in qs]
        return success('Attachments retrieved.', data)


class AttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        attachment = AttachmentValue.objects.filter(pk=pk, is_deleted=False).select_related('field__entity').first()
        if attachment is None:
            return error('Not found.', http_status=404)
        entity = attachment.field.entity
        if not _can_access_record(entity, attachment.object_id, request.user, write=False):
            return error('You do not have permission to view this.', http_status=403)

        import requests as http_req
        from django.http import StreamingHttpResponse
        try:
            remote = http_req.get(attachment.file.url, stream=True, timeout=30)
            remote.raise_for_status()
        except Exception:
            return error('File temporarily unavailable.', http_status=502)
        response = StreamingHttpResponse(remote.iter_content(chunk_size=8192), content_type=attachment.mime_type or 'application/octet-stream')
        response['Content-Disposition'] = f'inline; filename="{attachment.original_name}"'
        response['Cache-Control'] = 'no-store'
        return response

    def delete(self, request, pk):
        attachment = AttachmentValue.objects.filter(pk=pk, is_deleted=False).select_related('field__entity').first()
        if attachment is None:
            return error('Not found.', http_status=404)
        if not _can_access_record(attachment.field.entity, attachment.object_id, request.user, write=True):
            return error('You do not have permission to delete this.', http_status=403)
        attachment.is_deleted = True
        attachment.save(update_fields=['is_deleted'])
        return success('Attachment deleted.')
