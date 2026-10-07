"""Phase 3B Task H — admin API for event types, notification rules,
message templates (incl. preview/test-send), preferences, and the
delivery log."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasSettingsPermission
from core.responses import error, success

from apps.platform_core import services_notifications as notifications
from apps.platform_core.models import (
    EventType, MessageTemplate, NotificationDelivery, NotificationRule, UserNotificationPreference,
)
from apps.platform_core.serializers_workflow import (
    EventTypeSerializer, MessageTemplateSerializer, NotificationDeliverySerializer,
    NotificationRuleSerializer, UserNotificationPreferenceSerializer,
)
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


class EventTypeListView(_BaseListCreateView):
    """Read access per Task H.1 ("event types (read)") — POST exists for
    the sync command's own convenience, not expected to be the normal path."""
    model = EventType
    serializer_class = EventTypeSerializer
    search_fields = ['code', 'description']


class MessageTemplateListCreateView(_BaseListCreateView):
    model = MessageTemplate
    serializer_class = MessageTemplateSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        event_type_code = request.query_params.get('event_type')
        if event_type_code:
            qs = qs.filter(event_type__code=event_type_code)
        return qs


class MessageTemplateDetailView(_BaseDetailView):
    model = MessageTemplate
    serializer_class = MessageTemplateSerializer


class MessageTemplatePreviewView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        template = MessageTemplate.objects.filter(pk=pk).first()
        if template is None:
            return error('Not found.', http_status=404)
        subject, body = notifications.preview(template)
        return success('Previewed.', {'subject': subject, 'body': body})


class MessageTemplateTestSendView(APIView):
    """Task H.1's "test send to self"."""
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        template = MessageTemplate.objects.filter(pk=pk).first()
        if template is None:
            return error('Not found.', http_status=404)
        subject, body = notifications.preview(template)
        try:
            notifications.send_direct(template.channel, request.user, subject, body)
        except notifications.NotificationError as exc:
            return error(exc.message, http_status=400)
        return success('Test message sent to you.')


class NotificationRuleListCreateView(_BaseListCreateView):
    model = NotificationRule
    serializer_class = NotificationRuleSerializer
    search_fields = ['code']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        event_type_code = request.query_params.get('event_type')
        if event_type_code:
            qs = qs.filter(event_type__code=event_type_code)
        return qs


class NotificationRuleDetailView(_BaseDetailView):
    model = NotificationRule
    serializer_class = NotificationRuleSerializer


class NotificationDeliveryListView(APIView):
    """Admin delivery log (Task H.1)."""
    permission_classes = [HasSettingsPermission]

    def get(self, request):
        from core.pagination import paginate, paginated_data
        qs = NotificationDelivery.objects.all()
        rule_id = request.query_params.get('rule')
        if rule_id:
            qs = qs.filter(rule_id=rule_id)
        page_obj, paginator = paginate(qs, request)
        return success('Delivery log retrieved.', paginated_data(paginator, page_obj, NotificationDeliverySerializer(page_obj, many=True).data))


class MyNotificationPreferencesView(APIView):
    """Task F.4 — the user's own preferences; mandatory rules are never
    exposed here as mutable (is_mandatory ignores this table entirely at
    dispatch time, so showing a toggle for one would be misleading)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prefs = UserNotificationPreference.objects.filter(user=request.user)
        return success('Preferences retrieved.', UserNotificationPreferenceSerializer(prefs, many=True).data)

    def post(self, request):
        data = dict(request.data)
        data['user'] = request.user.pk
        obj, _ = UserNotificationPreference.objects.update_or_create(
            user=request.user, event_category_or_type=data.get('event_category_or_type'), channel=data.get('channel'),
            defaults={'enabled': data.get('enabled', True)},
        )
        return success('Preference saved.', UserNotificationPreferenceSerializer(obj).data)
