"""Tests for core/redis_connection.py (fail fast while the local Redis is down)."""
from unittest import mock

from django.test import SimpleTestCase
from django_redis.exceptions import ConnectionInterrupted
from redis.connection import Connection
from redis.exceptions import ConnectionError as RedisConnectionError

from core.redis_connection import FailFastRedisConnection, RedisCircuitBreaker


class FailFastRedisConnectionTests(SimpleTestCase):
    def setUp(self):
        self.now = 1000.0
        clock = mock.patch('core.redis_connection.time.monotonic', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        breaker = mock.patch.object(FailFastRedisConnection, 'breaker', RedisCircuitBreaker(cooldown_seconds=30))
        breaker.start()
        self.addCleanup(breaker.stop)

    def test_connects_normally_while_redis_is_reachable(self):
        with mock.patch.object(Connection, 'connect') as real_connect:
            FailFastRedisConnection().connect()
            FailFastRedisConnection().connect()
        self.assertEqual(real_connect.call_count, 2)

    def test_skips_redis_right_after_a_refused_connection(self):
        refused = RedisConnectionError('Error 10061 connecting to 127.0.0.1:6379.')
        with mock.patch.object(Connection, 'connect', side_effect=refused) as real_connect:
            with self.assertRaises(RedisConnectionError):
                FailFastRedisConnection().connect()
            with self.assertRaises(RedisConnectionError):
                FailFastRedisConnection().connect()
        self.assertEqual(real_connect.call_count, 1)

    def test_tries_redis_again_after_the_cooldown_and_resumes_caching(self):
        refused = RedisConnectionError('refused')
        with mock.patch.object(Connection, 'connect', side_effect=refused):
            with self.assertRaises(RedisConnectionError):
                FailFastRedisConnection().connect()
        self.now += 31
        with mock.patch.object(Connection, 'connect') as real_connect:
            FailFastRedisConnection().connect()
            FailFastRedisConnection().connect()
        self.assertEqual(real_connect.call_count, 2)
        self.assertFalse(FailFastRedisConnection.breaker.is_open())

    def test_an_existing_connection_is_not_blocked(self):
        FailFastRedisConnection.breaker.record_failure()
        connection = FailFastRedisConnection()
        connection._sock = object()  # already connected
        with mock.patch.object(Connection, 'connect') as real_connect:
            connection.connect()
        real_connect.assert_called_once()
        connection._sock = None

    def test_outage_is_logged_once_not_per_call(self):
        with self.assertLogs('core.redis_connection', level='WARNING') as logs:
            FailFastRedisConnection.breaker.record_failure()
            self.now += 31
            FailFastRedisConnection.breaker.record_failure()
            FailFastRedisConnection.breaker.record_success()
        self.assertEqual(len(logs.records), 2)  # "unreachable" once, then "reachable again"


class DocumentTypeConfigCacheFallbackTests(SimpleTestCase):
    """The employee list reads document type labels through this cache: a Redis
    error must fall back to the database result, not fail the request."""

    def test_falls_back_to_the_database_when_the_cache_is_down(self):
        from apps.accounts.models import DocumentTypeConfig
        from core import cache_service

        rows = [mock.Mock(type_key='pan_card', label='PAN Card')]
        down = ConnectionInterrupted(connection=None)
        with mock.patch.object(cache_service.cache, 'get', side_effect=down), \
                mock.patch.object(cache_service.cache, 'set', side_effect=down), \
                mock.patch.object(DocumentTypeConfig, 'objects') as manager:
            manager.all.return_value = rows
            label = cache_service.DocumentTypeConfigCacheService.label_for('pan_card')
        self.assertEqual(label, 'PAN Card')
