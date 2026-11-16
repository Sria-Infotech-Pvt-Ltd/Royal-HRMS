import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from core.permissions import HasCompletedOnboardingStatus
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from apps.accounts.services_access_guards import is_full_access_actor
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from ..models import HR_HELP_RESOLVED, HRHelpRequest
from ..profile_change_fields import public_registry
from ..services_profile_change import ProfileChangeError, apply_change, reject_change
from ..serializers import (
    HRHelpRequestCreateSerializer,
    HRHelpRequestRespondSerializer,
    HRHelpRequestSerializer,
)

logger = logging.getLogger(__name__)


def _can_respond(user) -> bool:
    """HR-side access: hr_help.respond, or full access (superuser / settings.edit, i.e. the System Admin), who sees every ticket."""
    return _has_perm(user, 'hr_help.respond') or is_full_access_actor(user)


class HRHelpRequestListCreateView(APIView):
    """GET/POST /hr-help/requests/ — a plain employee sees and creates only
    their own requests; hr_help.respond holders see everyone's (optionally
    filtered by status), mirroring ExpenseListCreateView's own
    submitter-vs-approver split."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        can_respond = _can_respond(request.user)
        queryset = HRHelpRequest.objects.select_related('submitted_by', 'assigned_to')
        # mine=1 asks for the caller's own tickets even when they could see everyone's (the "My requests" lists), so staff
        # keep the organisation-wide queue on the Approvals page and their own tickets in My Workspace.
        if not can_respond or request.query_params.get('mine') == '1':
            queryset = queryset.filter(submitted_by=request.user)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        # topic / exclude_topic split the staff queue, e.g. profile corrections apart from every other HR question.
        topic_param = request.query_params.get('topic')
        if topic_param:
            queryset = queryset.filter(topic=topic_param)
        exclude_topic_param = request.query_params.get('exclude_topic')
        if exclude_topic_param:
            queryset = queryset.exclude(topic=exclude_topic_param)

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = HRHelpRequestSerializer(page_obj.object_list, many=True)
        return success('HR help requests retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        serializer = HRHelpRequestCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        with transaction.atomic():
            # Same select_for_update-on-the-last-row pattern as Expense's own
            # sequential numbering (see ExpenseListCreateView.post's comment)
            # — locks the actual last row rather than an aggregate MAX(), so
            # two concurrent submissions can't read the same last number.
            last_row = (
                HRHelpRequest.objects
                .exclude(request_number__isnull=True)
                .select_for_update()
                .order_by('-request_number')
                .first()
            )
            last_num = last_row.request_number if last_row else 0
            help_request = serializer.save(submitted_by=request.user, request_number=last_num + 1)

        logger.info('HR help request #%s submitted by %s', help_request.request_number, request.user.email)
        return success(
            'Your request has been submitted to HR.',
            HRHelpRequestSerializer(help_request).data,
            http_status=201,
        )


class HRHelpRequestDetailView(APIView):
    """GET (submitter or hr_help.respond) / PATCH (hr_help.respond only —
    status, response, assignment) /hr-help/requests/<id>/."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def _get_request(self, pk, user):
        try:
            help_request = HRHelpRequest.objects.select_related('submitted_by', 'assigned_to').get(pk=pk)
        except HRHelpRequest.DoesNotExist:
            return None, error('Request not found.', http_status=404)
        can_respond = _can_respond(user)
        if help_request.submitted_by_id != user.id and not can_respond:
            return None, error('Permission denied.', http_status=403)
        return help_request, None

    def get(self, request, pk):
        help_request, err = self._get_request(pk, request.user)
        if err:
            return err
        return success('HR help request retrieved.', HRHelpRequestSerializer(help_request).data)

    def patch(self, request, pk):
        if not _can_respond(request.user):
            return error('Permission denied.', http_status=403)
        help_request, err = self._get_request(pk, request.user)
        if err:
            return err

        serializer = HRHelpRequestRespondSerializer(help_request, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        new_status = serializer.validated_data.get('status', help_request.status)
        resolved_at = help_request.resolved_at
        if new_status == HR_HELP_RESOLVED and help_request.status != HR_HELP_RESOLVED:
            resolved_at = timezone.now()
        elif new_status != HR_HELP_RESOLVED:
            resolved_at = None

        help_request = serializer.save(resolved_at=resolved_at)
        logger.info('HR help request #%s updated by %s (status=%s)', help_request.request_number, request.user.email, help_request.status)
        return success('Request updated.', HRHelpRequestSerializer(help_request).data)


class HRHelpChangeFieldsView(APIView):
    """GET /hr-help/change-fields/ — the profile fields an employee can ask to change with a new value (and how to draw each input)."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        return success('Profile change fields retrieved.', public_registry())


class HRHelpDecideChangeView(APIView):
    """POST /hr-help/requests/<id>/decide-change/ {decision: 'approve' | 'reject', note} — HR / the System Admin applies or declines
    the new value a profile-correction ticket carries, and the ticket is resolved in the same step."""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def post(self, request, pk):
        if not _can_respond(request.user):
            return error('Permission denied.', http_status=403)
        ticket = HRHelpRequest.objects.select_related('submitted_by', 'assigned_to').filter(pk=pk).first()
        if ticket is None:
            return error('Request not found.', http_status=404)
        decision = (request.data.get('decision') or '').strip()
        note = (request.data.get('note') or '').strip()
        if decision not in ('approve', 'reject'):
            return error('Choose approve or reject.')
        try:
            if decision == 'approve':
                apply_change(ticket, request.user, note)
            else:
                reject_change(ticket, request.user, note)
        except ProfileChangeError as exc:
            return error(exc.message)
        return success('Request updated.', HRHelpRequestSerializer(ticket).data)
