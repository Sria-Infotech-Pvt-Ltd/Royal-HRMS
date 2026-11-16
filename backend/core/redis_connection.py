"""
Redis connection that stops trying an unreachable Redis server for a short time.

Local development only (settings.py wires it in when DEBUG is True).

Cache failures are already absorbed (IGNORE_EXCEPTIONS in settings.CACHES and
the try/except fallbacks in core/cache_service.py), but each failed call still
waits for the connection attempt. On Windows a refused connection to
127.0.0.1 takes about 2 seconds, so a request that makes ~17 cache calls (the
employee list) took over 30 seconds and the frontend's 15-second timeout
reported "Could not load employees".

After one failed connection this class refuses new connections immediately
for COOLDOWN_SECONDS, so cache calls fall back to the database at once. The
next connection attempt after the cooldown tries Redis again, and caching
resumes as soon as Redis is reachable.
"""
import logging
import threading
import time

from redis.connection import Connection
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)


class RedisCircuitBreaker:
    """Process-wide record of whether Redis was recently unreachable."""

    def __init__(self, cooldown_seconds: float):
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._open_until = 0.0

    def is_open(self) -> bool:
        return time.monotonic() < self._open_until

    def record_failure(self) -> None:
        with self._lock:
            was_open = self._open_until > 0.0
            self._open_until = time.monotonic() + self.cooldown_seconds
        if not was_open:
            logger.warning(
                'Redis is unreachable; skipping it for %s seconds at a time until it is back.',
                self.cooldown_seconds,
            )

    def record_success(self) -> None:
        if self._open_until == 0.0:
            return
        with self._lock:
            self._open_until = 0.0
        logger.warning('Redis is reachable again; caching resumed.')


class FailFastRedisConnection(Connection):
    """redis-py Connection that skips connecting while the breaker is open."""

    COOLDOWN_SECONDS = 30
    breaker = RedisCircuitBreaker(cooldown_seconds=COOLDOWN_SECONDS)

    def connect(self) -> None:
        is_connected = getattr(self, '_sock', None) is not None
        if not is_connected and self.breaker.is_open():
            raise RedisConnectionError('Redis was unreachable moments ago; not retrying yet.')
        try:
            super().connect()
        except (RedisConnectionError, RedisTimeoutError):
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
