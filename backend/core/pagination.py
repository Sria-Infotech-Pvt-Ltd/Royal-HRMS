from django.core.paginator import Paginator


def paginate(queryset, request, default_page_size: int = 20, max_page_size: int = 100):
    """
    Paginate a queryset or list using ?page and ?page_size query params.
    Returns (page_obj, paginator).
    """
    try:
        page_num  = max(1, int(request.query_params.get('page', 1)))
        page_size = min(
            max_page_size,
            max(1, int(request.query_params.get('page_size', default_page_size))),
        )
    except (ValueError, TypeError):
        page_num, page_size = 1, default_page_size

    paginator = Paginator(queryset, page_size)
    return paginator.get_page(page_num), paginator


def paginated_data(paginator, page_obj, results):
    """
    Build the standard pagination envelope used across all list endpoints.

    Returns a dict with:
        count        — total matching records across all pages
        page         — current page number
        page_size    — records per page
        total_pages  — total number of pages
        results      — serialized records for this page
    """
    return {
        'count':       paginator.count,
        'page':        page_obj.number,
        'page_size':   paginator.per_page,
        'total_pages': paginator.num_pages,
        'results':     results,
    }
