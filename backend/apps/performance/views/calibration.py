import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success

from ..models import PerformanceReview
from ..serializers import PerformanceReviewSerializer

logger = logging.getLogger(__name__)


# ─── HR calibration, publish, acknowledge ───────────────────────────────────

class CalibrateReviewView(APIView):
    """POST — HR confirms/finalizes the manager's rating, setting
    hr_calibrated_at. Gated by the same performance.manage_cycles
    permission as ReviewCycleListCreateView/HRReviewQueueView, since
    calibration is an HR-only action, not a reporting-manager one."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        try:
            review = PerformanceReview.objects.get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if not review.manager_submitted_at:
            return error('The manager review has not been submitted yet.', http_status=409)
        if review.hr_calibrated_at:
            return error('Already calibrated.', http_status=409)
        review.hr_calibrated_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['hr_calibrated_at', 'status', 'updated_at'])
        logger.info('Review %s calibrated by %s', review.pk, request.user.email)
        return success('Review calibrated.', PerformanceReviewSerializer(review).data)


class PublishReviewView(APIView):
    """POST — HR publishes the calibrated outcome to the employee, setting
    published_at. Only allowed once hr_calibrated_at is set."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        try:
            review = PerformanceReview.objects.get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if not review.hr_calibrated_at:
            return error('This review has not been HR-calibrated yet.', http_status=409)
        if review.published_at:
            return error('Already published.', http_status=409)
        review.published_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['published_at', 'status', 'updated_at'])
        logger.info('Review %s published by %s', review.pk, request.user.email)
        return success('Review published.', PerformanceReviewSerializer(review).data)


class AcknowledgeReviewView(APIView):
    """POST — the review's own employee acknowledges the published outcome,
    setting acknowledged_at. Only allowed once published_at is set."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            review = PerformanceReview.objects.get(pk=pk, employee=request.user)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if not review.published_at:
            return error('This review has not been published yet.', http_status=409)
        if review.acknowledged_at:
            return error('Already acknowledged.', http_status=409)
        review.acknowledged_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['acknowledged_at', 'status', 'updated_at'])
        logger.info('Review %s acknowledged by %s', review.pk, request.user.email)
        return success('Outcome acknowledged.', PerformanceReviewSerializer(review).data)
