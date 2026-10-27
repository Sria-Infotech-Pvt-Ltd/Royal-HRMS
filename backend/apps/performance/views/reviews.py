import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from django.db import transaction

from ..models import Goal, PerformanceReview
from ..serializers import (
    GoalSerializer,
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
            # success() coerces data=None into {} (its genuine-"nothing
            # configured" convention elsewhere), but the frontend needs to
            # tell "no active cycle" apart from "a real, empty-ish review" —
            # built directly here so `data` is a real JSON null, not {}.
            return Response({
                'status': 'success', 'message': 'No active review cycle.', 'data': None,
            })
        review = self._get_or_create(request.user, cycle)
        return success('Review retrieved.', PerformanceReviewSerializer(review, context={'request': request}).data)

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
        return success('Self-review saved.', PerformanceReviewSerializer(review, context={'request': request}).data)


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
        return success('Self-review submitted.', PerformanceReviewSerializer(review, context={'request': request}).data)


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
        # A review row normally appears when the employee first opens their
        # own appraisal. The manager's workspace should list every active
        # direct report from the start of the cycle, so make sure the row
        # exists (idempotent: one row per employee per cycle).
        for report in request.user.direct_reports.filter(is_active=True).exclude(employee_id=''):
            PerformanceReview.objects.get_or_create(employee=report, cycle=cycle, defaults={'manager': request.user})
        reviews = PerformanceReview.objects.filter(
            cycle=cycle, employee__reporting_manager=request.user,
        ).select_related('employee', 'manager').order_by('employee__full_name')
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
        # Rating + assessment are always required. The development plan and
        # next check-in are required of the reporting manager; an HR override
        # (performance.manage_cycles acting for a manager) may omit them.
        if not review.manager_rating or not (review.manager_notes or '').strip():
            return error('Add a rating and your assessment comments before sending to HR.')
        is_reporting_manager = review.employee.reporting_manager_id == request.user.id
        if is_reporting_manager and (not (review.manager_development_plan or '').strip() or not review.manager_next_checkin):
            return error('Add a development plan and the next check-in date before sending to HR.')
        review.manager_submitted_at = timezone.now()
        review.recompute_status()
        review.save(update_fields=['manager_submitted_at', 'status', 'updated_at'])
        logger.info('Manager review submitted by %s for review %s', request.user.email, review.pk)
        return success('Manager review submitted.', PerformanceReviewSerializer(review).data)


class ReturnReviewView(APIView):
    """POST {reason} - the reporting manager (or HR acting for them) sends a
    submitted self-review back to the employee for changes. Clears
    self_submitted_at so the employee can edit and resubmit; the reason and
    time are kept for the employee's banner and the activity history."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            review = PerformanceReview.objects.select_for_update(of=('self',)).select_related('employee').get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if review.employee.reporting_manager_id != request.user.id and not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        if not review.self_submitted_at:
            return error('The employee has no submitted self-review to return.', http_status=409)
        if review.manager_submitted_at:
            return error('This review has already been sent to HR and can no longer be returned.', http_status=409)
        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return error('Enter what the employee should revise.')
        review.self_submitted_at = None
        review.returned_at = timezone.now()
        review.return_reason = reason
        review.recompute_status()
        review.save(update_fields=['self_submitted_at', 'returned_at', 'return_reason', 'status', 'updated_at'])
        logger.info('Review %s returned for changes by %s', review.pk, request.user.email)
        return success('Returned to the employee.', PerformanceReviewSerializer(review).data)


class ReviewGoalsView(APIView):
    """GET - the review's employee's goals for that review's cycle, including
    the self-review ratings/outcomes/evidence, so the reporting manager (or HR)
    can assess them. Same access rule as the manager review endpoints."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            review = PerformanceReview.objects.select_related('employee').get(pk=pk)
        except PerformanceReview.DoesNotExist:
            return error('Review not found.', http_status=404)
        if review.employee.reporting_manager_id != request.user.id and not _has_perm(request.user, 'performance.manage_cycles'):
            return error('Permission denied.', http_status=403)
        goals = Goal.objects.filter(employee=review.employee, cycle=review.cycle).order_by('due_date', 'created_at')
        return success('Goals retrieved.', GoalSerializer(goals, many=True).data)
