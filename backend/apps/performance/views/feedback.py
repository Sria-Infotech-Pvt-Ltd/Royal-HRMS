"""
Continuous feedback requests: an employee asks their manager, a peer or a
direct report for focused feedback; the recipient responds (or declines).

Who can be asked is deliberately limited to people the requester actually
works with — their reporting manager, peers who share that manager, and their
own direct reports — so this cannot be used to message arbitrary employees.
"""
import logging

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import User
from core.pagination import paginate, paginated_data
from core.responses import error, success

from ..models import FeedbackRequest

logger = logging.getLogger(__name__)

CYCLE_LABELS = ('Continuous feedback', 'Career conversation')
TOPIC_MAX = 2000
RESPONSE_MAX = 4000


def _colleagues(user: User):
    """(user, relation) pairs the requester may ask, de-duplicated."""
    found = {}
    manager = user.reporting_manager
    if manager and manager.is_active:
        found[manager.id] = (manager, 'Reporting manager')
        for peer in manager.direct_reports.filter(is_active=True).exclude(pk=user.pk).exclude(employee_id=''):
            found.setdefault(peer.id, (peer, 'Peer'))
    for report in user.direct_reports.filter(is_active=True).exclude(employee_id=''):
        found.setdefault(report.id, (report, 'Direct report'))
    return sorted(found.values(), key=lambda pair: (pair[1] != 'Reporting manager', pair[0].full_name))


def _dict(item: FeedbackRequest, viewer: User) -> dict:
    return {
        'id': str(item.id),
        'requester_name': item.requester.full_name,
        'recipient_name': item.recipient.full_name,
        'cycle_label': item.cycle_label,
        'topic': item.topic,
        'status': item.status,
        'status_display': item.get_status_display(),
        'response': item.response,
        'created_at': item.created_at.isoformat(),
        'responded_at': item.responded_at.isoformat() if item.responded_at else None,
        'can_respond': item.status == FeedbackRequest.STATUS_PENDING and item.recipient_id == viewer.id,
    }


class FeedbackColleaguesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = [{'id': str(person.id), 'name': person.full_name, 'employee_id': person.employee_id, 'relation': relation}
                for person, relation in _colleagues(request.user)]
        return success('Colleagues retrieved.', rows)


class FeedbackRequestListCreateView(APIView):
    """GET ?scope=mine (default) | for-me — POST creates a request."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get('scope', 'mine')
        qs = FeedbackRequest.objects.select_related('requester', 'recipient')
        qs = qs.filter(recipient=request.user) if scope == 'for-me' else qs.filter(requester=request.user)
        page_obj, paginator = paginate(qs, request)
        return success('Feedback requests retrieved.', paginated_data(
            paginator, page_obj, [_dict(i, request.user) for i in page_obj.object_list],
        ))

    @transaction.atomic
    def post(self, request):
        recipient_id = str(request.data.get('recipient') or '').strip()
        topic = str(request.data.get('topic') or '').strip()
        cycle_label = str(request.data.get('cycle_label') or '').strip() or CYCLE_LABELS[0]
        if not recipient_id:
            return error('Choose who you would like feedback from.')
        if not topic:
            return error('Describe what feedback would help you.')
        if len(topic) > TOPIC_MAX:
            return error(f'Keep the topic under {TOPIC_MAX} characters.')
        allowed = {str(person.id): person for person, _ in _colleagues(request.user)}
        recipient = allowed.get(recipient_id)
        if recipient is None:
            return error('You can only ask your manager, a peer or a direct report.', http_status=403)
        if FeedbackRequest.objects.filter(
            requester=request.user, recipient=recipient, status=FeedbackRequest.STATUS_PENDING,
        ).exists():
            return error(f'You already have a feedback request waiting with {recipient.full_name}.', http_status=409)
        item = FeedbackRequest.objects.create(
            requester=request.user, recipient=recipient, cycle_label=cycle_label[:60], topic=topic,
        )
        from apps.notifications.signals import _notify
        _notify(recipient, 'Feedback requested',
                f'{request.user.full_name} asked for your feedback: {topic[:140]}',
                'announcement', 'announcement', reference_id=str(item.id), created_by=request.user, category='approval')
        return success('Feedback requested.', _dict(item, request.user), http_status=201)


class FeedbackRequestRespondView(APIView):
    """POST {response} to give feedback, or {decline: true} to decline."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            item = FeedbackRequest.objects.select_for_update(of=('self',)).select_related('requester', 'recipient').get(pk=pk)
        except FeedbackRequest.DoesNotExist:
            return error('Feedback request not found.', http_status=404)
        if item.recipient_id != request.user.id:
            return error('Permission denied.', http_status=403)
        if item.status != FeedbackRequest.STATUS_PENDING:
            return error('This request has already been answered.', http_status=409)
        declining = bool(request.data.get('decline'))
        text = str(request.data.get('response') or '').strip()
        if not declining and not text:
            return error('Write your feedback before sending it.')
        if len(text) > RESPONSE_MAX:
            return error(f'Keep the response under {RESPONSE_MAX} characters.')
        item.status = FeedbackRequest.STATUS_DECLINED if declining else FeedbackRequest.STATUS_PROVIDED
        item.response = '' if declining else text
        item.responded_at = timezone.now()
        item.save(update_fields=['status', 'response', 'responded_at', 'updated_at'])
        from apps.notifications.signals import _notify
        _notify(item.requester, 'Feedback update',
                f'{request.user.full_name} {"declined your feedback request" if declining else "sent you feedback"}.',
                'announcement', 'announcement', reference_id=str(item.id), created_by=request.user, category='approval')
        return success('Response recorded.', _dict(item, request.user))
