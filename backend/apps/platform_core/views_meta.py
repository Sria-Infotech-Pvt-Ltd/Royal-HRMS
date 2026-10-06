"""
Phase 2 Task F — metadata admin API (EntityDefinition/FieldDefinition/
FormLayout CRUD, same HasSettingsPermission convention as views.py) and
the generic CUSTOM-RECORD data API (Task F.2): one set of endpoints that
works for ANY published custom entity, gated by the per-entity
Permission rows services_custom_objects.publish_entity() creates — never
a new endpoint per custom entity.

Core-entity attribute read/write (Task F.3) is intentionally NOT a
separate generic endpoint here: every core entity already has its own
detail endpoint (employee detail, branch detail, etc.) with its own
object-level permission checks, and services_attributes.save()/read()
is the shared function those existing views call directly. Building a
second, parallel "generic core attributes" endpoint would bypass
whatever object-level scoping (branch access, reporting-line visibility)
those real endpoints already enforce — flagged in PHASE2_REPORT.md
rather than built here.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission, has_perm
from core.responses import error, success

from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import EntityDefinition, FieldDefinition, FormLayout
from apps.platform_core.serializers_meta import (
    EntityDefinitionSerializer, FieldDefinitionSerializer, FormLayoutSerializer,
)
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


# ─── Admin config: entities / fields / layouts ──────────────────────────────

class EntityDefinitionListCreateView(_BaseListCreateView):
    model = EntityDefinition
    serializer_class = EntityDefinitionSerializer
    search_fields = ['code', 'label']
    ordering = ['module', 'label']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        kind = request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class EntityDefinitionDetailView(_BaseDetailView):
    model = EntityDefinition
    serializer_class = EntityDefinitionSerializer


class EntityDefinitionPublishView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        entity = EntityDefinition.objects.filter(pk=pk).first()
        if entity is None:
            return error('Not found.', http_status=404)
        try:
            entity = custom_objects.publish_entity(entity, actor=request.user)
        except custom_objects.CustomObjectError as exc:
            return error(exc.message, http_status=400)
        return success('Entity published.', EntityDefinitionSerializer(entity).data)


class FieldDefinitionListCreateView(_BaseListCreateView):
    model = FieldDefinition
    serializer_class = FieldDefinitionSerializer
    search_fields = ['code', 'label']
    ordering = ['entity', 'order']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_code = request.query_params.get('entity')
        if entity_code:
            qs = qs.filter(entity__code=entity_code)
        return qs


class FieldDefinitionDetailView(_BaseDetailView):
    model = FieldDefinition
    serializer_class = FieldDefinitionSerializer


class FormLayoutListCreateView(_BaseListCreateView):
    model = FormLayout
    serializer_class = FormLayoutSerializer
    search_fields = ['code', 'name']
    ordering = ['entity', 'context', '-priority']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_code = request.query_params.get('entity')
        context = request.query_params.get('context')
        if entity_code:
            qs = qs.filter(entity__code=entity_code)
        if context:
            qs = qs.filter(context=context)
        return qs


class FormLayoutDetailView(_BaseDetailView):
    model = FormLayout
    serializer_class = FormLayoutSerializer


class ResolveLayoutView(APIView):
    """Task D.5 — the endpoint the frontend actually calls to render a
    form. Open to any authenticated user (not settings-gated) since this
    is read access to a resolved, already-published layout, not
    metadata configuration."""
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code):
        from apps.platform_core import services_forms

        entity = EntityDefinition.objects.filter(code=entity_code).first()
        if entity is None:
            return error('Unknown entity.', http_status=404)
        context = request.query_params.get('context')
        if not context:
            return error('A "context" query parameter is required.', http_status=400)
        layout = services_forms.resolve_layout(
            entity, context,
            legal_entity=request.query_params.get('legal_entity'),
            country=request.query_params.get('country'),
            employment_type=request.query_params.get('employment_type'),
        )
        if layout is None:
            return error('No published layout for this entity/context.', http_status=404)
        return success('Layout resolved.', layout)


# ─── Generic custom-record data API (Task F.2) ──────────────────────────────

def _get_published_custom_entity(entity_code):
    return EntityDefinition.objects.filter(
        code=entity_code, kind=EntityDefinition.KIND_CUSTOM, status=EntityDefinition.STATUS_PUBLISHED,
    ).first()


class CustomRecordListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code):
        entity = _get_published_custom_entity(entity_code)
        if entity is None:
            return error('Unknown or unpublished custom entity.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(entity.code, 'view')):
            return error('You do not have permission to view this.', http_status=403)

        qs = custom_objects.list_records(entity, legal_entity=request.query_params.get('legal_entity'))
        page_obj, paginator = paginate(qs, request)
        data = [custom_objects.read_record(r, for_user=request.user) | {'id': str(r.pk), 'title': r.title} for r in page_obj]
        return success('Records retrieved.', paginated_data(paginator, page_obj, data))

    def post(self, request, entity_code):
        entity = _get_published_custom_entity(entity_code)
        if entity is None:
            return error('Unknown or unpublished custom entity.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(entity.code, 'add')):
            return error('You do not have permission to create this.', http_status=403)

        from apps.platform_core.services_attributes import AttributeValidationError
        try:
            record = custom_objects.create_record(entity, request.data, actor=request.user)
        except AttributeValidationError as exc:
            return error('Validation failed.', data=exc.errors, http_status=400)
        data = custom_objects.read_record(record, for_user=request.user) | {'id': str(record.pk), 'title': record.title}
        return success('Record created.', data, http_status=201)


class CustomRecordDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_record(self, entity, pk):
        return custom_objects.list_records(entity).filter(pk=pk).first()

    def get(self, request, entity_code, pk):
        entity = _get_published_custom_entity(entity_code)
        if entity is None:
            return error('Unknown or unpublished custom entity.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(entity.code, 'view')):
            return error('You do not have permission to view this.', http_status=403)
        record = self._get_record(entity, pk)
        if record is None:
            return error('Not found.', http_status=404)
        data = custom_objects.read_record(record, for_user=request.user) | {'id': str(record.pk), 'title': record.title}
        return success('Record retrieved.', data)

    def patch(self, request, entity_code, pk):
        entity = _get_published_custom_entity(entity_code)
        if entity is None:
            return error('Unknown or unpublished custom entity.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(entity.code, 'change')):
            return error('You do not have permission to edit this.', http_status=403)
        record = self._get_record(entity, pk)
        if record is None:
            return error('Not found.', http_status=404)

        from apps.platform_core.services_attributes import AttributeValidationError
        try:
            record = custom_objects.update_record(record, request.data, actor=request.user)
        except AttributeValidationError as exc:
            return error('Validation failed.', data=exc.errors, http_status=400)
        data = custom_objects.read_record(record, for_user=request.user) | {'id': str(record.pk), 'title': record.title}
        return success('Record updated.', data)

    def delete(self, request, entity_code, pk):
        entity = _get_published_custom_entity(entity_code)
        if entity is None:
            return error('Unknown or unpublished custom entity.', http_status=404)
        if not has_perm(request.user, custom_objects.permission_codename(entity.code, 'delete')):
            return error('You do not have permission to delete this.', http_status=403)
        record = self._get_record(entity, pk)
        if record is None:
            return error('Not found.', http_status=404)
        custom_objects.soft_delete_record(record, actor=request.user)
        return success('Record deleted.')
