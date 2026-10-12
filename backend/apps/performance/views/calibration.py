import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, success

from ..models import RATING_CHOICES, PerformanceReview
from ..serializers import PerformanceReviewSerializer

_VALID_RATINGS = {value for value, _ in RATING_CHOICES}


def _apply_calibration(review, data):
    """Record HR's final rating + note when supplied. Returns an error
    message, or None. A rating without a note (or vice versa) is rejected:
    a changed rating must always carry its reason."""
    rating = str(data.get('final_rating') or '').strip()
    note = str(data.get('note') or '').strip()
    if not rating and not note:
        return None
    if rating not in _VALID_RATINGS:
        return 'Select a final rating from 1 to 5.'
    if not note:
        return 'Record a calibration note explaining the final rating.'
    review.final_rating = rating
    review.calibration_note = note
    return None

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
        problem = _apply_calibration(review, request.data)
        if problem:
            return error(problem)
        review.hr_calibrated_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['hr_calibrated_at', 'final_rating', 'calibration_note', 'status', 'updated_at'])
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
        if review.published_at:
            return error('Already published.', http_status=409)
        if not review.manager_submitted_at:
            return error('The manager review has not been submitted yet.', http_status=409)
        # One-step "Publish to employee": supplying the final rating + note
        # calibrates and publishes together. Without them the review must
        # already have been calibrated (the two-step flow the HR queue uses).
        problem = _apply_calibration(review, request.data)
        if problem:
            return error(problem)
        if not review.hr_calibrated_at:
            if not (review.final_rating and review.calibration_note):
                return error('This review has not been HR-calibrated yet.', http_status=409)
            review.hr_calibrated_at = timezone.now()
        review.published_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['hr_calibrated_at', 'final_rating', 'calibration_note', 'published_at', 'status', 'updated_at'])
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
        review.acknowledgement_comment = str(request.data.get('comment') or '').strip()
        review.recompute_status()
        review.save(update_fields=['acknowledged_at', 'acknowledgement_comment', 'status', 'updated_at'])
        logger.info('Review %s acknowledged by %s', review.pk, request.user.email)
        return success('Outcome acknowledged.', PerformanceReviewSerializer(review, context={'request': request}).data)
