import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from ..models import PerformanceReview
from ..serializers import (
    ManagerReviewSaveSerializer,
    PerformanceReviewSerializer,
    SelfReviewSaveSerializer,
)
from ._shared import _active_cycle, _resolve_manager

logger = logging.getLogger(__name__)


# ─── My Review (self-service) ───────────────────────────────────────────────────

class MyReviewView(APIView):
    """GET/PATCH — the current employee's own review for the active cycle,
    created on first GET (same get-or-create-on-read convention as
    MyTaxDeclarationView — there's exactly one row per employee per cycle)."""
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, user, cycle):
        review, created = PerformanceReview.objects.get_or_create(
            employee=user, cycle=cycle, defaults={'manager': _resolve_manager(user)},
        )
        return review

    def get(self, request):
        cycle = _active_cycle()
        if not cycle:
            return success('No active review cycle.', None)
        review = self._get_or_create(request.user, cycle)
        return success('Review retrieved.', PerformanceReviewSerializer(review).data)

    def patch(self, request):
        cycle = _active_cycle()
        if not cycle:
            return error('There is no active review cycle.', http_status=409)
        review = self._get_or_create(request.user, cycle)
        if review.self_submitted_at:
            return error('Your self-review has already been submitted for this cycle.', http_status=409)
        serializer = SelfReviewSaveSerializer(review, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Self-review saved.', PerformanceReviewSerializer(review).data)


class SubmitMyReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cycle = _active_cycle()
        if not cycle:
            return error('There is no active review cycle.', http_status=409)
        review, _ = PerformanceReview.objects.get_or_create(
            employee=request.user, cycle=cycle, defaults={'manager': _resolve_manager(request.user)},
        )
        if review.self_submitted_at:
            return error('Already submitted.', http_status=409)
        review.self_submitted_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['self_submitted_at', 'status', 'updated_at'])
        logger.info('Self-review submitted by %s for cycle %s', request.user.email, cycle.name)
        return success('Self-review submitted.', PerformanceReviewSerializer(review).data)


# ─── Manager review ──────────────────────────────────────────────────────────

class TeamReviewListView(APIView):
    """GET — the current user's direct reports' reviews for the active
    cycle, resolved via reporting_manager (same scoping mechanism
    Separation/Expense already use for "is this my direct report")."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cycle = _active_cycle()
        if not cycle:
            return success('No active review cycle.', [])
        reviews = PerformanceReview.objects.filter(
            cycle=cycle, employee__reporting_manager=request.user,
        ).select_related('employee', 'manager')
        return success('Team reviews retrieved.', PerformanceReviewSerializer(reviews, many=True).data)


class ManagerReviewDetailView(APIView):
    """PATCH (save manager fields) — manager-only, scoped to their own
    direct report's review."""
    permission_classes = [IsAuthenticated]

    def _get_review(self, pk, user):
        try:
            review = PerformanceReview.objects.select_related('employee').get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return None, error('Review not found.', http_status=404)
        if review.employee.reporting_manager_id != user.id and not _has_perm(user, 'performance.manage_cycles'):
            return None, error('Permission denied.', http_status=403)
        return review, None

    def patch(self, request, pk):
        review, err = self._get_review(pk, request.user)
        if err:
            return err
        if not review.self_submitted_at:
            return error('The employee has not submitted their self-review yet.', http_status=409)
        if review.manager_submitted_at:
            return error('Manager review has already been submitted.', http_status=409)
        serializer = ManagerReviewSaveSerializer(review, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Manager review saved.', PerformanceReviewSerializer(review).data)


class SubmitManagerReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            review = PerformanceReview.objects.select_related('employee').get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if review.employee.reporting_manager_id != request.user.id and not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        if not review.self_submitted_at:
            return error('The employee has not submitted their self-review yet.', http_status=409)
        if review.manager_submitted_at:
            return error('Already submitted.', http_status=409)
        review.manager_submitted_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['manager_submitted_at', 'status', 'updated_at'])
        logger.info('Manager review submitted by %s for review %s', request.user.email, review.pk)
        return success('Manager review submitted.', PerformanceReviewSerializer(review).data)
