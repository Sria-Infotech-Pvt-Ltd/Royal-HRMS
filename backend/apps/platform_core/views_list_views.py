from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

from apps.platform_core import services_list_views as list_views
from apps.platform_core.models import EntityDefinition, ListViewDefinition
from apps.platform_core.serializers_meta import ListViewDefinitionSerializer
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


class ListViewDefinitionListCreateView(_BaseListCreateView):
    """Admin/system-view management — same HasSettingsPermission
    convention as every other metadata endpoint. Saving a PERSONAL view
    is a separate, any-authenticated-user action (MyListViewSaveView
    below), not this endpoint."""
    model = ListViewDefinition
    serializer_class = ListViewDefinitionSerializer
    search_fields = ['code', 'name']
    ordering = ['entity', 'name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_code = request.query_params.get('entity')
        if entity_code:
            qs = qs.filter(entity__code=entity_code)
        return qs

    def post(self, request):
        entity = EntityDefinition.objects.filter(pk=request.data.get('entity')).first()
        if entity is None:
            return error('Unknown entity.', http_status=400)
        try:
            list_views.validate_columns(
                entity, request.data.get('columns') or [], sort_field=request.data.get('default_sort'),
            )
        except list_views.ListViewError as exc:
            return error(exc.message, http_status=400)
        return super().post(request)


class ListViewDefinitionDetailView(_BaseDetailView):
    model = ListViewDefinition
    serializer_class = ListViewDefinitionSerializer


class MyDefaultListViewView(APIView):
    """Any authenticated user can resolve (not configure) the default
    view that applies to them for an entity — personal > role > system."""
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_code):
        entity = EntityDefinition.objects.filter(code=entity_code).first()
        if entity is None:
            return error('Unknown entity.', http_status=404)
        view = list_views.resolve_default_view(entity, request.user)
        if view is None:
            return success('No list view configured for this entity.', None)
        return success('Default view resolved.', list_views.build_view_payload(view))
