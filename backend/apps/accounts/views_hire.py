"""
Two-stage Hire flow — Stage 1 (HireActionListCreateView.post) reserves a
position + reason + effective date before any User exists; the wizard then
PATCHes HireActionDetailView as each step is filled in (employment_type
reserves the employee number via EmployeeCodeSeries, everything else lands
in draft_data — see HireAction's own docstring for why); Stage 2
(HireActionCompleteView.post) is what actually creates the User, mirroring
the sequence EmployeeListCreateView.post already runs today.
"""
import hashlib
import logging
from datetime import datetime

import requests as http_req
from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success, get_client_ip
from apps.accounts.models import (
    AuditLog, EmployeeCodeSeries, EmployeeIdSeriesExhausted, HireAction, HireActionDocument, Position, User,
)
from apps.accounts.serializers import HireActionDocumentSerializer
from apps.accounts.serializers_profile_photo import ProfilePhotoUploadSerializer
from apps.accounts.services_hire_drafts import discard_draft, existing_employee_match
from apps.accounts.services_hire_draft_fields import validate_draft_fields
from apps.accounts.services_hire_duplicates import check_hire_duplicates
from apps.accounts.services_placement import assign_position
from apps.accounts.views.shared import _get_document_type_config

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to perform this action.'

# first_error() prefixes every message with its field name so callers know
# which field is invalid (e.g. "employee_id: ..."), which is genuinely
# useful for named business fields. For a raw file upload the field is
# always literally called "file"/"photo" — a name the end user never typed
# and that means nothing to them (QA report #44: "file: Only PDF, JPG, and
# PNG files are allowed." read as a stray broken prefix, not a field label).
_FILE_FIELD_NAMES = {'file', 'photo'}


def _first_file_error(serializer_errors: dict) -> str:
    message = first_error(serializer_errors)
    for field_name in _FILE_FIELD_NAMES:
        prefix = f'{field_name}: '
        if message.startswith(prefix):
            return message[len(prefix):]
    return message


def _hire_action_dict(action: HireAction, request=None) -> dict:
    photo_url = None
    if action.photo:
        photo_url = request.build_absolute_uri(action.photo.url) if request else action.photo.url
    return {
        'id':                   str(action.id),
        'reason':               action.reason,
        'reason_display':       action.get_reason_display(),
        'effective_from':       action.effective_from,
        'position':             str(action.position_id),
        'position_title':       action.position.title,
        'org_unit_name':        action.position.org_unit.name,
        'grade':                action.position.grade,
        'employment_type':      action.employment_type,
        'reserved_employee_id': action.reserved_employee_id,
        'status':               action.status,
        'draft_data':           action.draft_data,
        'photo_url':            photo_url,
        'created_employee':     str(action.created_employee_id) if action.created_employee_id else None,
    }


class HireActionListCreateView(APIView):
    """Stage 1 — the "Hire an employee" modal's own POST. GET backs the
    Employee Directory's real "Drafts" popover — the reference mockup's own
    version only ever reads localStorage (browser-only, lost on a new
    device); this lists the user's own real, backend-persisted draft
    HireAction rows instead, so a draft actually survives across sessions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        drafts = HireAction.objects.select_related('position').filter(
            created_by=request.user, status=HireAction.STATUS_DRAFT,
        ).order_by('-updated_at')
        results = []
        def _as_str(v):
            # draft_data can carry stray list-wrapped values from an old
            # multipart PATCH (fixed elsewhere this codebase already
            # guards against, but historical draft rows may predate it).
            if isinstance(v, list):
                return v[0] if v else ''
            return v or ''

        for d in drafts:
            first = _as_str((d.draft_data or {}).get('first_name'))
            last = _as_str((d.draft_data or {}).get('last_name'))
            name = f'{first} {last}'.strip()
            results.append({
                'id': str(d.id),
                'label': name or f'New hire — {d.position.title}',
                'position_title': d.position.title,
                'reserved_employee_id': d.reserved_employee_id,
                'updated_at': d.updated_at,
                # Non-blank when this draft looks like someone who already is an employee (stale / test leftover).
                'existing_employee_match': existing_employee_match(d),
            })
        return success('Draft hire actions.', results)

    def post(self, request):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        reason         = (request.data.get('reason') or '').strip()
        effective_from = (request.data.get('effective_from') or '').strip()
        position_id    = (request.data.get('position') or '').strip()

        if reason not in dict(HireAction.REASON_CHOICES):
            return error('Select a valid reason.')
        if not effective_from:
            return error('Effective from is required.')
        try:
            effective_from = datetime.strptime(effective_from, '%Y-%m-%d').date()
        except ValueError:
            return error('Effective from must be a valid date.')
        if effective_from < timezone.localdate():
            return error('Effective from cannot be in the past.')
        if not position_id:
            return error('Select a position.')
        position = Position.objects.filter(pk=position_id, is_active=True).first()
        if not position:
            return error('Position not found or inactive.')

        action = HireAction.objects.create(
            reason=reason, effective_from=effective_from, position=position,
            created_by=request.user,
        )
        return success('Hire action created.', _hire_action_dict(action, request), http_status=201)


class HireActionDetailView(APIView):
    """GET bootstraps/resumes the wizard; PATCH saves each step's fields."""
    permission_classes = [IsAuthenticated]

    def _get_draft(self, pk):
        return HireAction.objects.select_related('position', 'position__org_unit').filter(
            pk=pk, status=HireAction.STATUS_DRAFT,
        ).first()

    def get(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = HireAction.objects.select_related('position', 'position__org_unit').filter(pk=pk).first()
        if not action:
            return error('Hire action not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Hire action retrieved.', _hire_action_dict(action, request))

    def patch(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)

        # request.data is a QueryDict for multipart/form-encoded requests —
        # dict(querydict) wraps every value in a single-item list (QueryDict
        # supports multiple values per key), silently corrupting every field
        # this view processes (e.g. `employment_type` becomes `['Permanent']`,
        # which then blows up as an unhashable dict-membership test below).
        # The real wizard always PATCHes as JSON so request.data is already a
        # plain dict there, but this must not assume that unconditionally.
        data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
        update_fields: list[str] = []
        rejected: dict[str, str] = {}

        # A draft is saved field by field: a value that cannot be saved is reported (rejected) and left out, and everything
        # else in the same request is still stored. The wizard autosaves the WHOLE form, so one bad field must never stop
        # the rest of the form from being kept.
        self._apply_position(action, data, update_fields, rejected)
        self._apply_employment_type(action, data, update_fields, rejected)
        data, field_errors = validate_draft_fields(data)
        rejected.update(field_errors)

        # Same email or mobile as an existing employee / another open draft: a WARNING on the draft (shown to the person,
        # and the wizard will not advance past it), never a reason to refuse saving. Completing the hire is what blocks it.
        warnings = self._duplicate_warnings(action, data)

        if data:
            action.draft_data = {**action.draft_data, **data}
            update_fields.append('draft_data')
        if update_fields:
            action.save(update_fields=[*update_fields, 'updated_at'])

        if rejected:
            logger.warning('Hire draft %s: %d field(s) not saved (%s); the other fields in the request were saved.',
                           action.pk, len(rejected), ', '.join(sorted(rejected)))  # names only, never the values
            saved = sorted(set(data) | (set(update_fields) & {'position', 'employment_type'}))
            return error(next(iter(rejected.values())), data={**rejected, 'saved_fields': saved, 'warnings': warnings})
        return success('Hire action updated.', {**_hire_action_dict(action, request), 'warnings': warnings})

    @staticmethod
    def _apply_position(action, data: dict, update_fields: list, rejected: dict) -> None:
        if 'position' not in data:
            return
        position = Position.objects.filter(pk=data.pop('position'), is_active=True).first()
        if not position:
            rejected['position'] = 'Position not found or inactive.'
            return
        action.position = position
        update_fields.append('position')

    @staticmethod
    def _apply_employment_type(action, data: dict, update_fields: list, rejected: dict) -> None:
        # The employee number is reserved the moment employment_type is set,
        # and re-reserved (against the new type's own series) if HR corrects
        # the selection before completing the hire — this used to be locked
        # permanently after the first selection, which was QA report #32:
        # a genuine typo/misclick on this field had no way to fix itself
        # short of discarding the whole draft. The previously-reserved
        # number for the old type is simply left unused (this per-type
        # sequence has no "release" concept, so it becomes a gap) rather
        # than reused — matches how real HRMS/payroll number series already
        # tolerate voided/skipped numbers rather than risk ever reusing one.
        employment_type = data.pop('employment_type', None)
        if employment_type is None or employment_type == action.employment_type:
            return
        if employment_type not in dict(User.EMPLOYMENT_TYPE_CHOICES):
            rejected['employment_type'] = 'Select a valid employment type.'
            return
        try:
            reserved = EmployeeCodeSeries.generate_employee_id_for_type(employment_type)
        except EmployeeIdSeriesExhausted as exc:
            rejected['employment_type'] = str(exc)
            return
        action.employment_type = employment_type
        action.reserved_employee_id = reserved
        update_fields += ['employment_type', 'reserved_employee_id']

    @staticmethod
    def _duplicate_warnings(action, data: dict) -> list[dict]:
        if 'email' not in data and 'phone' not in data:
            return []
        merged = {**action.draft_data, **data}
        hits = check_hire_duplicates(str(merged.get('email') or ''), str(merged.get('phone') or ''), exclude_action=action)
        return [hit.as_dict() for hit in hits]

    def delete(self, request, pk):
        """Discard a draft — the Stage 1 modal's "Discard" action."""
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)
        is_released = discard_draft(action, request.user, reason='discarded', ip_address=get_client_ip(request))
        return success('Draft discarded.', data={'number_released': is_released})


class HireActionPhotoView(APIView):
    """
    POST   /hire-actions/<id>/photo/  — upload/replace the Personal Identity
                                         step's employee photo
    DELETE /hire-actions/<id>/photo/  — remove it

    HR-authenticated (not self-service like ProfilePhotoView) — there's no
    User row yet to upload "your own" photo to. Reuses the exact same
    validation as the real profile-photo upload (ProfilePhotoUploadSerializer)
    so the size/type rules match everywhere. HireActionCompleteView copies
    this onto the new employee's User.profile_photo at Stage 2.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_draft(self, pk):
        return HireAction.objects.filter(pk=pk, status=HireAction.STATUS_DRAFT).first()

    def post(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = ProfilePhotoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return error(_first_file_error(serializer.errors), data=serializer.errors, http_status=422)

        if action.photo:
            action.photo.delete(save=False)
        action.photo = serializer.validated_data['photo']
        action.save(update_fields=['photo', 'updated_at'])

        photo_url = request.build_absolute_uri(action.photo.url)
        return success('Photo uploaded.', {'photo_url': photo_url})

    def delete(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)

        if action.photo:
            action.photo.delete(save=False)
            action.photo = None
            action.save(update_fields=['photo', 'updated_at'])
        return success('Photo removed.', {'photo_url': None})


class HireActionDocumentListCreateView(APIView):
    """
    GET  /hire-actions/<id>/documents/  — list documents uploaded so far
    POST /hire-actions/<id>/documents/  — upload one (PAN/Aadhaar on the
                                           Statutory step, or any item on the
                                           Documents step)

    Same shape as EmployeeDocumentView but keyed to a HireAction — there's no
    User row yet to attach a real EmployeeDocument to. Validated against the
    same DocumentTypeConfig rows real employee uploads use. Copied onto real
    EmployeeDocument rows at Stage 2 (HireActionCompleteView).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _get_draft(self, pk):
        return HireAction.objects.filter(pk=pk, status=HireAction.STATUS_DRAFT).first()

    def get(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)
        docs = action.documents.all()
        return success(
            'Documents retrieved.',
            HireActionDocumentSerializer(docs, many=True, context={'request': request}).data,
        )

    def post(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = HireActionDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(_first_file_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        entry_ref = serializer.validated_data.get('entry_ref', '') or ''
        type_config = _get_document_type_config(doc_type)
        if not type_config:
            return error('Invalid document type.', http_status=status.HTTP_400_BAD_REQUEST)

        # Not real content verification (nothing here confirms a "PAN card"
        # upload is actually a PAN card — that needs a real OCR/ID-
        # verification service this app doesn't have) — just catches the
        # careless mistake of uploading the same file twice under two
        # different document types (e.g. the PAN photo re-used for Aadhaar).
        content_hash = hashlib.sha256(file_obj.read()).hexdigest()
        file_obj.seek(0)
        dup = HireActionDocument.objects.filter(
            hire_action=action, content_hash=content_hash,
        ).exclude(document_type=doc_type).first()
        if dup:
            dup_label = _get_document_type_config(dup.document_type)
            dup_label = dup_label.label if dup_label else dup.document_type
            return error(
                f'This file is already uploaded as "{dup_label}". '
                f'Upload the correct document for {type_config.label} instead.',
            )

        with transaction.atomic():
            doc = serializer.save(
                hire_action=action, file_name=file_obj.name[:255], file_size=file_obj.size,
                content_hash=content_hash, entry_ref=entry_ref,
            )
            if entry_ref:
                # Per-entry attachment (e.g. one certificate per education
                # entry) — a re-upload replaces just that entry's file, never
                # touches another entry's file of the same document_type.
                HireActionDocument.objects.filter(
                    hire_action=action, document_type=doc_type, entry_ref=entry_ref,
                ).exclude(pk=doc.pk).delete()
            elif not type_config.allow_multiple:
                HireActionDocument.objects.filter(
                    hire_action=action, document_type=doc_type, entry_ref='',
                ).exclude(pk=doc.pk).delete()

        logger.info('Hire action document %s uploaded for %s by %s', doc_type, action.id, request.user.email)
        return success(
            'Document uploaded.',
            HireActionDocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


class HireActionDocumentDetailView(APIView):
    """
    GET    /hire-actions/<id>/documents/<doc_id>/ — stream the file (signed storage proxy)
    DELETE /hire-actions/<id>/documents/<doc_id>/ — remove an uploaded document

    GET exists because HireActionDocumentSerializer.file_url points here (the
    wizard's "View" link). The stored file sits behind authenticated storage,
    so the browser cannot open its raw URL. Without GET the link only showed a
    405 page. Same approach as EmployeeDocumentView's GET.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, doc_id):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        doc = HireActionDocument.objects.filter(
            pk=doc_id, hire_action_id=pk, hire_action__status=HireAction.STATUS_DRAFT,
        ).first()
        if not doc or not doc.file:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)

        try:
            remote = http_req.get(doc.file.url, stream=True, timeout=30)
            remote.raise_for_status()
        except Exception as exc:
            logger.error('Hire action doc storage fetch failed doc=%s: %s', doc_id, exc)
            return error('File temporarily unavailable.', http_status=status.HTTP_502_BAD_GATEWAY)

        # Recorded only after the fetch succeeded, like EmployeeDocumentView.
        AuditLog.objects.create(
            user=request.user, action='document_viewed', module='accounts', object_id=str(doc.id),
            changes={'document_type': doc.document_type, 'hire_action': str(pk), 'file_name': doc.file_name},
            ip_address=get_client_ip(request),
        )
        is_pdf = doc.file_name.lower().endswith('.pdf')
        content_type = 'application/pdf' if is_pdf else remote.headers.get('content-type', 'application/octet-stream')
        response = StreamingHttpResponse(remote.iter_content(chunk_size=8192), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
        if 'content-length' in remote.headers:
            response['Content-Length'] = remote.headers['content-length']
        response['Cache-Control'] = 'no-store'
        return response

    def delete(self, request, pk, doc_id):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = HireAction.objects.filter(pk=pk, status=HireAction.STATUS_DRAFT).first()
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)
        doc = HireActionDocument.objects.filter(pk=doc_id, hire_action=action).first()
        if not doc:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        doc.delete()
        # Logged like uploads: without it a successful delete left no trace, so a later
        # "document not found" could not be explained from the logs.
        logger.info('Hire action document %s (%s) deleted for %s by %s', doc_id, doc.document_type, pk, request.user.email)
        return success('Document deleted.')
