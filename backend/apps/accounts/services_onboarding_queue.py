"""The onboarding approvals list: real totals across every page, plus the status / search filters and the order.

It holds the people who went through the self-service onboarding wizard: those waiting for review, those sent back for changes, and
those already approved. People hired another way (HR hiring form, imports) never use the wizard, so they are not in it.
"""
from django.db.models import Case, F, IntegerField, Q, Value, When

from apps.accounts.models import User

# The word the page sends to filter on each status, and who it matches.
STATUS_FILTERS = {
    'submitted': Q(onboarding_status=User.ONBOARDING_SUBMITTED),
    'rejected':  Q(onboarding_status=User.ONBOARDING_REJECTED),
    'approved':  Q(onboarding_status=User.ONBOARDING_COMPLETE, requires_self_service_onboarding=True),
}
# Everyone the list can show: any of the three.
QUEUE_MEMBERSHIP = STATUS_FILTERS['submitted'] | STATUS_FILTERS['rejected'] | STATUS_FILTERS['approved']
MAX_SEARCH_LENGTH = 100
_SEARCH_FIELDS = ('full_name', 'email', 'designation', 'employee_id')


def queue_counts(queue) -> dict:
    """Totals for the whole list the person is allowed to see, whatever filters are applied to it."""
    counts = {key: queue.filter(matches).count() for key, matches in STATUS_FILTERS.items()}
    return {'total': sum(counts.values()), **counts}


def apply_queue_filters(queue, status: str, search: str):
    """Narrow by status ('submitted' / 'rejected' / 'approved'; anything else means no status filter) and by search text."""
    status = (status or '').strip().lower()
    if status in STATUS_FILTERS:
        queue = queue.filter(STATUS_FILTERS[status])
    needle = (search or '').strip()[:MAX_SEARCH_LENGTH]
    if needle:
        matches = Q()
        for field in _SEARCH_FIELDS:
            matches |= Q(**{f'{field}__icontains': needle})
        queue = queue.filter(matches)
    return queue


def order_queue(queue):
    """What needs action first: waiting for review (longest-waiting first), then sent back, then approved (most recent first)."""
    rank = Case(
        When(STATUS_FILTERS['submitted'], then=Value(0)),
        When(STATUS_FILTERS['rejected'], then=Value(1)),
        default=Value(2), output_field=IntegerField(),
    )
    # Only approved people carry a value here, so only they are sorted newest-first; for the others it is empty and the
    # longest-waiting-first order below applies.
    recently_approved = Case(When(STATUS_FILTERS['approved'], then=F('updated_at')), default=None)
    return queue.annotate(_queue_rank=rank, _recently_approved=recently_approved).order_by(
        '_queue_rank', F('_recently_approved').desc(nulls_last=True), 'date_joined', 'pk',
    )
