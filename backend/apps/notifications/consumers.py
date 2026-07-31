import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    One socket per browser tab, joined to a per-user group so
    apps.notifications.signals._notify() can push new notifications the
    moment they're created — see group_send call there.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f'notifications_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, 'group_name', None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Called by channel_layer.group_send(..., {'type': 'notification.push', ...})
    async def notification_push(self, event):
        await self.send_json({'type': 'notification', 'notification': event['notification']})

    # Called by channel_layer.group_send(..., {'type': 'attendance.update'})
    async def attendance_update(self, event):
        await self.send_json({'type': 'attendance_update'})

    # Called by channel_layer.group_send(..., {'type': 'leave.update', 'action_queue': {...}, 'pending_actions': N})
    async def leave_update(self, event):
        await self.send_json({
            'type':            'leave_update',
            'action_queue':    event.get('action_queue'),
            'pending_actions': event.get('pending_actions'),
        })
