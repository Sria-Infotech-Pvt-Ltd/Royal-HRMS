import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from ..models import ReviewCycle
from ..serializers import ReviewCycleCreateSerializer, ReviewCycleSerializer
from ._shared import _active_cycle

logger = logging.getLogger(__name__)


# ─── Review Cycles (admin) ──────────────────────────────────────────────────────

class ReviewCycleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        cycles = ReviewCycle.objects.all()
        return success('Review cycles retrieved.', ReviewCycleSerializer(cycles, many=True).data)

    def post(self, request):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        serializer = ReviewCycleCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        cycle = serializer.save(created_by=request.user)
        logger.info('Review cycle "%s" created by %s', cycle.name, request.user.email)
        return success('Review cycle created.', ReviewCycleSerializer(cycle).data, http_status=201)


class ReviewCycleDetailView(APIView):
    """PATCH — the only transition an admin drives by hand is
    draft -> active or active -> closed; the daily
    close_expired_review_cycles task handles the date-driven active ->
    closed transition automatically (see tasks.py)."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        try:
            cycle = ReviewCycle.objects.get(pk=pk)
        except ReviewCycle.DoesNotExist:
            return error('Review cycle not found.', http_status=404)

        new_status = request.data.get('status')
        if new_status not in ('active', 'closed'):
            return error('status must be "active" or "closed".')
        if new_status == 'active':
            active = _active_cycle()
            if active and active.pk != cycle.pk:
                return error(f'"{active.name}" is already active — close it first.', http_status=409)
        cycle.status = new_status
        cycle.save(update_fields=['status', 'updated_at'])
        return success('Review cycle updated.', ReviewCycleSerializer(cycle).data)
