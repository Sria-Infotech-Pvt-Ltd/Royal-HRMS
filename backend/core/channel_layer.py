"""
Redis channel layer that treats a read timeout while WAITING for a message as "no message yet".

The notifications WebSocket (apps/notifications/consumers.py) waits on Redis for its next message. When the Redis connection has a
read timeout that is not longer than that wait, every quiet period raises redis.exceptions.TimeoutError ("Timeout reading from
127.0.0.1:6379") inside the library's receive loop. The consumer crashes, the browser reconnects, and the next idle wait does the same:
one full traceback per open tab, over and over, which filled backend/logs/errors.log (5 MB x 5 files) within about two hours and pushed
real errors out of it.

Redis itself is healthy in that situation, so the timeout is not a failure, only an empty wait. channels_redis is safe to call again
straight after it: a message popped just before the timeout sits in its backup queue and is put back by the next receive. Only the
timeout is absorbed. A refused or dropped connection, or any other error, still raises as before.
"""
import asyncio
import logging
import time

from channels_redis.core import RedisChannelLayer
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)

# A short pause so a very small socket timeout cannot turn the retry into a busy loop.
RETRY_DELAY_SECONDS = 0.5
# Say it happened (the cause is a setting worth fixing) but at most this often, so it can never flood the log again.
WARN_EVERY_SECONDS = 600


class ResilientRedisChannelLayer(RedisChannelLayer):
    _timeouts_since_warning = 0
    _last_warning_at = 0.0

    async def receive(self, channel):
        while True:
            try:
                return await super().receive(channel)
            except RedisTimeoutError:
                self._note_timeout()
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    def _note_timeout(self) -> None:
        cls = ResilientRedisChannelLayer
        cls._timeouts_since_warning += 1
        now = time.monotonic()
        if now - cls._last_warning_at < WARN_EVERY_SECONDS:
            return
        logger.warning(
            'Redis read timed out %d time(s) while the notifications socket waited for a message; waiting again. '
            'Check that REDIS_URL has no socket_timeout shorter than the 5 s the channel layer waits.',
            cls._timeouts_since_warning,
        )
        cls._timeouts_since_warning = 0
        cls._last_warning_at = now
