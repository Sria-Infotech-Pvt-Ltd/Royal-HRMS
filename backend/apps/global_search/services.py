"""Running a search: free text plus filters over one module's scoped queryset, entirely in the database.

Nothing here loads a table into memory: the text box and the filters become one WHERE clause on the module's own scoped queryset,
results are sliced by the paginator, and only the rows on the page are turned into dictionaries.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet

from apps.global_search.filters import FilterError, build_filter
from apps.global_search.registry import SearchModule, modules_for

logger = logging.getLogger(__name__)

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 100
MAX_TERMS = 5
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20
MAX_FILTER_JSON_LENGTH = 8000


class SearchError(FilterError):
    """A search request that cannot be honoured (a bad query, an unknown module, malformed filters)."""


def clean_query(raw) -> str:
    text = ' '.join(str(raw or '').split())
    if len(text) > MAX_QUERY_LENGTH:
        raise SearchError(f'Search for at most {MAX_QUERY_LENGTH} characters.')
    return text


def query_terms(query: str) -> list[str]:
    return query.lower().split()[:MAX_TERMS]


def parse_filter_json(raw):
    """The filter tree from a query-string value or request body: None when absent, SearchError when malformed."""
    if raw in (None, '', {}):
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if len(raw) > MAX_FILTER_JSON_LENGTH:
        raise SearchError('The filters are too long.')
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise SearchError('The filters are not valid JSON.') from None


def _text_q(fields: dict, terms: list[str]) -> Q:
    """Every typed word must appear somewhere in the searchable fields (AND across words, OR across fields)."""
    searchable = [spec for spec in fields.values() if spec.searchable]
    combined = Q()
    for term in terms:
        word_q = Q(pk__in=[])
        for spec in searchable:
            word_q |= Q(**{f'{spec.path}__icontains': term})
        combined &= word_q
    return combined


def scoped_queryset(user, module: SearchModule, query: str, tree) -> QuerySet:
    """The viewer's rows of `module` that match the text and the filters, ordered. Raises FilterError for a bad filter."""
    fields = module.fields_for(user)
    rows = module.queryset(user)
    terms = query_terms(query)
    if terms:
        rows = rows.filter(_text_q(fields, terms))
    rows = rows.filter(build_filter(tree, fields))
    return rows.order_by(*module.order_by)


def _value_at(obj, path: str):
    for part in path.split('__'):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def matched_fields(obj, module: SearchModule, user, terms: list[str]) -> list[str]:
    """Labels of the searchable fields whose value contains one of the typed words: the "why did this match" hint."""
    if not terms:
        return []
    labels = []
    for spec in module.fields_for(user).values():
        if not spec.searchable:
            continue
        value = _value_at(obj, spec.path)
        text = str(value).lower() if value is not None else ''
        if text and any(term in text for term in terms):
            labels.append(spec.label)
    return labels


@dataclass
class ModulePage:
    module: SearchModule
    count: int
    page: int
    page_size: int
    total_pages: int
    results: list[dict]


def search_module(user, module: SearchModule, *, query: str, tree, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> ModulePage:
    rows = scoped_queryset(user, module, query, tree)
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))
    paginator = Paginator(rows, page_size)
    terms = query_terms(query)
    current = paginator.get_page(page)
    results = []
    for obj in current.object_list:
        entry = module.describe(obj)
        entry['matched'] = matched_fields(obj, module, user, terms)
        results.append(entry)
    return ModulePage(module, paginator.count, current.number, page_size, paginator.num_pages, results)


def resolve_module(user, key: str) -> SearchModule:
    """The module `key` if this viewer may search it. An unknown module and a forbidden one look the same, so the response never
    reveals which modules exist but are closed to them."""
    module = modules_for(user).get(key)
    if module is None:
        raise SearchError('That area cannot be searched.')
    return module


def grouped_search(user, query: str, *, keys: list[str] | None = None, limit: int = 5) -> list[ModulePage]:
    """The first `limit` matches in every module the viewer may search (or only `keys`), skipping modules with no match."""
    if len(query) < MIN_QUERY_LENGTH:
        raise SearchError(f'Type at least {MIN_QUERY_LENGTH} characters to search.')
    available = modules_for(user)
    chosen = [available[key] for key in (keys or available) if key in available]
    groups = []
    for module in chosen:
        found = search_module(user, module, query=query, tree=None, page=1, page_size=max(1, min(limit, 10)))
        if found.count:
            groups.append(found)
    return groups
