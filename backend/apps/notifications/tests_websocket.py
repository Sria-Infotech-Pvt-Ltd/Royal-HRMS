"""
Real-time notifications over WebSocket, end to end through config.asgi
(the application Daphne serves): cookie-JWT authentication, tenant
activation, per-user + per-company group isolation, and live delivery of a
notification created by the app's own helper.
"""
from __future__ import annotations

from unittest import mock

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.db import connection
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.tokens import RoleBasedRefreshToken
from apps.tenants.models import Client
from config.asgi import application
from config.test_runner import TEST_COMPANY_CODE

PATH = '/ws/notifications/'


def token_for(user, schema: str, code: str) -> str:
    connection.set_tenant(Client.objects.get(company_code=TEST_COMPANY_CODE))
    refresh = RoleBasedRefreshToken.for_user(user)
    refresh['company_schema'] = schema
    refresh['company_code'] = code
    return str(refresh.access_token)


class NotificationSocketTests(TestCase):
    # channels.db.database_sync_to_async closes "old" connections around every
    # call — in a TestCase that would close the test's own transaction
    # connection. Production behaviour is unaffected by this patch.

    def setUp(self):
        patcher = mock.patch('channels.db.close_old_connections', lambda: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tenant = Client.objects.get(company_code=TEST_COMPANY_CODE)
        connection.set_tenant(self.tenant)
        self.alice = make_user('ws.alice@test.com', full_name='Alice WS')
        self.bob = make_user('ws.bob@test.com', full_name='Bob WS')

    def tearDown(self):
        connection.set_tenant(self.tenant)          # the WS auth resets the schema on rejection

    def open(self, token: str | None, path: str = PATH):
        headers = [(b'origin', b'https://royalhrms.com')]
        if token:
            headers.append((b'cookie', f'royal_access_token={token}'.encode()))
        return WebsocketCommunicator(application, path, headers=headers)

    def connect(self, communicator):
        connected, _ = async_to_sync(communicator.connect)()
        return connected

    def receive(self, communicator, timeout=2):
        return async_to_sync(communicator.receive_json_from)(timeout)

    def nothing(self, communicator):
        return async_to_sync(communicator.receive_nothing)(0.5)

    def close(self, communicator):
        async_to_sync(communicator.disconnect)()

    def notify(self, user, title):
        from apps.notifications.signals import _notify
        connection.set_tenant(self.tenant)
        _notify(user, title, 'message', 'general', 'leave')

    def test_unauthenticated_and_forged_are_rejected(self):
        self.assertFalse(self.connect(self.open(None)))
        self.assertFalse(self.connect(self.open('not-a-jwt')))
        forged = token_for(self.alice, 'tenant_doesnotexist', 'NOPE')
        self.assertFalse(self.connect(self.open(forged)))

    def test_unknown_path_rejected(self):
        token = token_for(self.alice, self.tenant.schema_name, self.tenant.company_code)
        self.assertFalse(self.connect(self.open(token, '/ws/elsewhere/')))

    def test_live_delivery_and_isolation(self):
        from asgiref.sync import sync_to_async
        a = self.open(token_for(self.alice, self.tenant.schema_name, self.tenant.company_code))
        b = self.open(token_for(self.bob, self.tenant.schema_name, self.tenant.company_code))
        notify = sync_to_async(self.notify, thread_sensitive=True)

        async def scenario():
            # One event loop for the whole conversation, as under Daphne.
            assert (await a.connect())[0] and (await b.connect())[0]
            await notify(self.alice, 'For Alice only')
            frame = await a.receive_json_from(timeout=3)
            assert frame['type'] == 'notification'
            assert frame['notification']['title'] == 'For Alice only'
            assert await b.receive_nothing(0.5)                 # Bob gets nothing
            await notify(self.bob, 'For Bob')
            assert (await b.receive_json_from(timeout=3))['notification']['title'] == 'For Bob'
            assert await a.receive_nothing(0.5)
            await a.disconnect()
            await b.disconnect()

        async_to_sync(scenario)()

    def test_same_user_id_in_another_company_is_a_different_group(self):
        from core.notification_groups import notification_group_name
        self.assertNotEqual(notification_group_name(self.alice.id, self.tenant.schema_name),
                            notification_group_name(self.alice.id, 'tenant_othercompany'))
