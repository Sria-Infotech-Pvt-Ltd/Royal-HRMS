import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from .models import Notification, NotificationSettings
from .serializers import NotificationSerializer, NotificationSettingsSerializer

logger = logging.getLogger(__name__)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        base_qs     = Notification.objects.filter(user=request.user)
        unread_count = base_qs.filter(is_read=False).count()

        queryset = base_qs

        is_read_param = request.query_params.get('is_read')
        if is_read_param is not None:
            queryset = queryset.filter(is_read=is_read_param.lower() == 'true')

        module = request.query_params.get('module')
        if module:
            queryset = queryset.filter(module=module)

        notification_type = request.query_params.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = NotificationSerializer(page_obj.object_list, many=True)
        data = paginated_data(paginator, page_obj, serializer.data)
        data['unread_count'] = unread_count
        return success('Notifications retrieved.', data)


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return success('Unread count retrieved.', {'unread_count': count})


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id: str):
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
        except Notification.DoesNotExist:
            return error('Notification not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read', 'updated_at'])
        return success('Notification marked as read.')


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        logger.info('Marked %d notifications as read for user %s', updated, request.user.id)
        return success('All notifications marked as read.')


class NotificationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings_row, _ = NotificationSettings.objects.get_or_create(user=request.user)
        return success('Notification settings retrieved.', NotificationSettingsSerializer(settings_row).data)

    def patch(self, request):
        settings_row, _ = NotificationSettings.objects.get_or_create(user=request.user)
        serializer = NotificationSettingsSerializer(settings_row, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Notification settings updated.', serializer.data)
