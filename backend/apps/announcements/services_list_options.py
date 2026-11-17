"""Search, pinned-only and sort options for the announcements list.

Kept out of views.py (already long). Every option is optional and is read from the query string, so an older client that sends only
`category` and `page` gets exactly what it always got: pinned first, then newest.
"""
from __future__ import annotations

from django.db.models import Q

MAX_SEARCH_LENGTH = 100
DEFAULT_SORT = 'newest'

# Pinned posts always stay on top; the choice only decides the order within pinned and within the rest. `id` is the final
# tie-breaker so pagination never shows a row twice or skips one when posts share a timestamp or a count.
SORT_ORDERINGS = {
    'newest':    ('-is_pinned', '-created_at', '-id'),
    'oldest':    ('-is_pinned', 'created_at', 'id'),
    'reactions': ('-is_pinned', '-reaction_count', '-created_at', '-id'),
    'views':     ('-is_pinned', '-views_count', '-created_at', '-id'),
}
_TRUE_VALUES = {'1', 'true', 'yes'}


def parse_options(params) -> dict:
    """The validated options from a query string: {'search': str, 'pinned_only': bool, 'sort': str}. Anything unrecognised falls back."""
    sort = params.get('sort')
    return {
        'search': (params.get('search') or '').strip()[:MAX_SEARCH_LENGTH],
        'pinned_only': str(params.get('pinned') or '').lower() in _TRUE_VALUES,
        'sort': sort if sort in SORT_ORDERINGS else DEFAULT_SORT,
    }


def apply_list_options(queryset, params):
    """`queryset` narrowed by the search text (title or body) and the pinned switch, then ordered. The queryset must already carry
    the `reaction_count` annotation the 'reactions' sort uses (views._visible_qs adds it)."""
    options = parse_options(params)
    if options['search']:
        queryset = queryset.filter(Q(title__icontains=options['search']) | Q(body__icontains=options['search']))
    if options['pinned_only']:
        queryset = queryset.filter(is_pinned=True)
    return queryset.order_by(*SORT_ORDERINGS[options['sort']])
