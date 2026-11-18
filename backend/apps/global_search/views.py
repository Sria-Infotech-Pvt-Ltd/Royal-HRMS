import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.global_search import filters as f
from apps.global_search.filters import FilterError, operators_for
from apps.global_search.registry import modules_for
from apps.global_search.services import (
    DEFAULT_PAGE_SIZE, clean_query, grouped_search, parse_filter_json, resolve_module, search_module,
)
from core.permissions import HasCompletedOnboardingStatus
from core.responses import error, success

logger = logging.getLogger(__name__)


def _int(request, name: str, default: int) -> int:
    try:
        return int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        return default


def _module_payload(found) -> dict:
    return {
        'module': found.module.key, 'label': found.module.label, 'icon': found.module.icon, 'url': found.module.default_url,
        'count': found.count, 'page': found.page, 'page_size': found.page_size, 'total_pages': found.total_pages, 'results': found.results,
    }


class GlobalSearchView(APIView):
    """GET /search/?q=<text>&modules=a,b&limit=5: the first matches in every area the signed-in person may search."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        try:
            query = clean_query(request.query_params.get('q'))
            wanted = [key for key in request.query_params.get('modules', '').split(',') if key.strip()] or None
            groups = grouped_search(request.user, query, keys=[key.strip() for key in wanted] if wanted else None, limit=_int(request, 'limit', 5))
        except FilterError as exc:
            return error(exc.message, http_status=status.HTTP_400_BAD_REQUEST)
        return success('Search results.', {'query': query, 'total': sum(group.count for group in groups), 'groups': [_module_payload(group) for group in groups]})


class ModuleSearchView(APIView):
    """GET or POST /search/<module>/: one area, with free text, the filter tree, and pages.

    GET takes ?q=&filters=<json>&page=&page_size=; POST takes the same as a JSON body (for long filters)."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request, module):
        return self._run(request, module, request.query_params.get('q'), request.query_params.get('filters'))

    def post(self, request, module):
        body = request.data if isinstance(request.data, dict) else {}
        return self._run(request, module, body.get('q'), body.get('filters'))

    def _run(self, request, module_key, raw_query, raw_filters):
        try:
            module = resolve_module(request.user, module_key)
            found = search_module(
                request.user, module, query=clean_query(raw_query), tree=parse_filter_json(raw_filters),
                page=_int(request, 'page', 1), page_size=_int(request, 'page_size', DEFAULT_PAGE_SIZE),
            )
        except FilterError as exc:
            return error(exc.message, http_status=status.HTTP_400_BAD_REQUEST)
        return success('Search results.', _module_payload(found))


class SearchRegistryView(APIView):
    """GET /search/registry/: the areas, fields and operators the signed-in person may use, to draw the filter builder."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        user = request.user
        modules = []
        for module in modules_for(user).values():
            modules.append({
                'key': module.key, 'label': module.label, 'icon': module.icon, 'url': module.default_url,
                'fields': [
                    {
                        'key': spec.key, 'label': spec.label, 'type': spec.type, 'searchable': spec.searchable,
                        'choices': [{'value': value, 'label': label} for value, label in spec.choices],
                        'operators': [{'code': code, 'label': f.OPERATOR_LABELS[code]} for code in operators_for(spec)],
                    }
                    for spec in module.fields_for(user).values() if spec.show
                ],
            })
        return success('Search registry.', {'modules': modules})
