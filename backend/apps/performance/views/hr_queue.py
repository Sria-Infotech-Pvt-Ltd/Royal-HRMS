from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success

from ..models import REVIEW_COMPLETED, Goal, PerformanceReview
from ..serializers import PerformanceReviewSerializer, ReviewCycleSerializer
from ._shared import _active_cycle


# ─── HR queue + KPIs ─────────────────────────────────────────────────────────

class HRReviewQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        cycle = _active_cycle()
        if not cycle:
            return success('No active review cycle.', {'cycle': None, 'reviews': [], 'stats': None})

        reviews = PerformanceReview.objects.filter(cycle=cycle).select_related('employee', 'manager')
        total = reviews.count()
        self_done    = reviews.exclude(self_submitted_at__isnull=True).count()
        manager_done = reviews.filter(status=REVIEW_COMPLETED).count()
        goals_at_risk = Goal.objects.filter(cycle=cycle, status='at_risk').count()

        return success('HR review queue retrieved.', {
            'cycle': ReviewCycleSerializer(cycle).data,
            'reviews': PerformanceReviewSerializer(reviews, many=True).data,
            'stats': {
                'total_employees_with_reviews': total,
                'self_reviews_done':    self_done,
                'manager_reviews_done': manager_done,
                'goals_at_risk':        goals_at_risk,
            },
        })


class AppraisalBannerSummaryView(APIView):
    """A tiny read-only endpoint just for the Employee Directory banner —
    active cycle name + a one-line submitted-vs-total summary, gated the
    same way as the full HR queue."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # `data=None` on the shared success() helper is coerced to `{}` (see
        # core/responses.py), not JSON null — so "nothing to show" is a
        # dict with no 'cycle_name' key, not a null payload. Consumers
        # (AppraisalBanner.tsx) check for that key's presence, not truthiness
        # of the payload itself.
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return success('No active review cycle.', {})
        cycle = _active_cycle()
        if not cycle:
            return success('No active review cycle.', {})
        reviews = PerformanceReview.objects.filter(cycle=cycle).select_related('employee')
        total = reviews.count()
        self_done = reviews.exclude(self_submitted_at__isnull=True).count()
        latest = reviews.order_by('-updated_at').first()
        return success('Active cycle summary retrieved.', {
            'cycle_name': cycle.name,
            'total': total,
            'self_reviews_done': self_done,
            'latest_employee_name': latest.employee.full_name if latest else None,
            'latest_employee_code': latest.employee.employee_id if latest else None,
            'latest_status_display': latest.get_status_display() if latest else None,
        })
