"""
Two-stage Hire flow — Stage 1 (HireActionListCreateView.post) reserves a
position + reason + effective date before any User exists; the wizard then
PATCHes HireActionDetailView as each step is filled in (employment_type
reserves the employee number via EmployeeCodeSeries, everything else lands
in draft_data — see HireAction's own docstring for why); Stage 2
(HireActionCompleteView.post) is what actually creates the User, mirroring
the sequence EmployeeListCreateView.post already runs today.
"""
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success, get_client_ip
from apps.accounts.models import (
    AuditLog, EmployeeCodeSeries, HireAction, HireActionDocument, Position, Role, User,
)
from apps.accounts.serializers import HireActionDocumentSerializer
from apps.accounts.serializers_profile_photo import ProfilePhotoUploadSerializer
from apps.accounts.services_placement import assign_position
from apps.accounts.views.shared import _get_document_type_config

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to perform this action.'


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
        'default_role_id':      str(action.position.default_role_id) if action.position.default_role_id else None,
        'default_role_name':    action.position.default_role.display_name if action.position.default_role_id else None,
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
        return HireAction.objects.select_related('position', 'position__org_unit', 'position__default_role').filter(
            pk=pk, status=HireAction.STATUS_DRAFT,
        ).first()

    def get(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = HireAction.objects.select_related('position', 'position__org_unit', 'position__default_role').filter(pk=pk).first()
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
        update_fields = []

        if 'position' in data:
            position = Position.objects.filter(pk=data.pop('position'), is_active=True).first()
            if not position:
                return error('Position not found or inactive.')
            action.position = position
            update_fields.append('position')

        # The employee number is reserved exactly once, the moment
        # employment_type is first set — matches the wizard's own copy
        # ("Employee number is reserved once employment type is set.").
        # Changing employment_type afterwards would either orphan the
        # already-reserved number or require un-reserving it, neither of
        # which this simple per-type sequence supports — so it's locked
        # once set, same spirit as Position.default_role never re-syncing
        # Role after creation.
        employment_type = data.pop('employment_type', None)
        if employment_type is not None and not action.employment_type:
            if employment_type not in dict(User.EMPLOYMENT_TYPE_CHOICES):
                return error('Select a valid employment type.')
            action.employment_type = employment_type
            action.reserved_employee_id = EmployeeCodeSeries.generate_employee_id_for_type(employment_type)
            update_fields += ['employment_type', 'reserved_employee_id']
        elif employment_type is not None and employment_type != action.employment_type:
            return error(
                f'Employment type is locked to "{action.employment_type}" — the employee number '
                f'{action.reserved_employee_id} has already been reserved against it.',
            )

        if data:
            action.draft_data = {**action.draft_data, **data}
            update_fields.append('draft_data')

        if update_fields:
            action.save(update_fields=[*update_fields, 'updated_at'])
        return success('Hire action updated.', _hire_action_dict(action, request))

    def delete(self, request, pk):
        """Discard a draft — the Stage 1 modal's "Discard" action."""
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        action = self._get_draft(pk)
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)
        action.status = HireAction.STATUS_DISCARDED
        action.save(update_fields=['status', 'updated_at'])
        return success('Hire action discarded.', data={})


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
            from core.responses import first_error
            return error(first_error(serializer.errors), data=serializer.errors, http_status=422)

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
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        doc_type = serializer.validated_data['document_type']
        type_config = _get_document_type_config(doc_type)
        if not type_config:
            return error('Invalid document type.', http_status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            doc = serializer.save(hire_action=action, file_name=file_obj.name[:255], file_size=file_obj.size)
            if not type_config.allow_multiple:
                HireActionDocument.objects.filter(
                    hire_action=action, document_type=doc_type,
                ).exclude(pk=doc.pk).delete()

        logger.info('Hire action document %s uploaded for %s by %s', doc_type, action.id, request.user.email)
        return success(
            'Document uploaded.',
            HireActionDocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


class HireActionDocumentDetailView(APIView):
    """DELETE /hire-actions/<id>/documents/<doc_id>/ — remove an uploaded document."""
    permission_classes = [IsAuthenticated]

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
        return success('Document deleted.')
