"""ResilientRedisChannelLayer: a read timeout while waiting is an empty wait, anything else still raises."""
from unittest import mock

from channels_redis.core import RedisChannelLayer
from django.test import SimpleTestCase
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from core import channel_layer
from core.channel_layer import ResilientRedisChannelLayer


def _layer() -> ResilientRedisChannelLayer:
    # No Redis is needed: the library's receive() is replaced below, only the wrapper is under test.
    return object.__new__(ResilientRedisChannelLayer)


@mock.patch.object(channel_layer, 'RETRY_DELAY_SECONDS', 0)
class ResilientChannelLayerTests(SimpleTestCase):
    def setUp(self):
        ResilientRedisChannelLayer._timeouts_since_warning = 0
        ResilientRedisChannelLayer._last_warning_at = 0.0

    async def test_a_read_timeout_is_retried_until_a_message_arrives(self):
        receive = mock.AsyncMock(side_effect=[RedisTimeoutError('Timeout reading from 127.0.0.1:6379'), RedisTimeoutError('again'), {'type': 'attendance.update'}])
        with mock.patch.object(RedisChannelLayer, 'receive', receive):
            message = await _layer().receive('specific.abc!def')
        self.assertEqual(message, {'type': 'attendance.update'})
        self.assertEqual(receive.await_count, 3)

    async def test_a_message_that_arrives_at_once_is_returned_untouched(self):
        with mock.patch.object(RedisChannelLayer, 'receive', mock.AsyncMock(return_value={'type': 'x'})) as receive:
            self.assertEqual(await _layer().receive('specific.abc!def'), {'type': 'x'})
        receive.assert_awaited_once_with('specific.abc!def')

    async def test_a_dropped_connection_still_raises(self):
        with mock.patch.object(RedisChannelLayer, 'receive', mock.AsyncMock(side_effect=RedisConnectionError('refused'))):
            with self.assertRaises(RedisConnectionError):
                await _layer().receive('specific.abc!def')

    async def test_many_timeouts_log_one_warning_not_one_per_timeout(self):
        receive = mock.AsyncMock(side_effect=[RedisTimeoutError('t')] * 50 + [{'type': 'x'}])
        with mock.patch.object(RedisChannelLayer, 'receive', receive), self.assertLogs('core.channel_layer', level='WARNING') as logs:
            await _layer().receive('specific.abc!def')
        self.assertEqual(len(logs.records), 1)
        self.assertIn('socket_timeout', logs.records[0].getMessage())
