import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.notification_groups import notification_group_name

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    One socket per browser tab, joined to a per-user group so
    apps.notifications.signals._notify() can push new notifications the
    moment they're created — see group_send call there.
    """

    async def connect(self):
        user = self.scope.get('user')
        schema_name = self.scope.get('tenant_schema')
        if not user or not user.is_authenticated or not schema_name:
            await self.close(code=4401)
            return
        self.group_name = notification_group_name(user.id, schema_name)
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


class NotFoundConsumer(AsyncJsonWebsocketConsumer):
    """
    Catch-all for any WebSocket path that doesn't match a real route (see the
    trailing pattern in routing.py) — closes immediately instead of letting
    Channels' URLRouter raise an unhandled ValueError per connection attempt,
    which otherwise dumps a full traceback to the server log for every stray
    or outdated client (e.g. a stale cached page hitting the old '/notifications/'
    path instead of '/ws/notifications/').
    """

    async def connect(self):
        logger.warning('WebSocket connection to unknown path %r rejected.', self.scope.get('path'))
        await self.close(code=4004)
