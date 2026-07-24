import time
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.voice_commands.clarification import (
    PENDING_TIMEOUT_SECONDS,
    clear_pending,
    get_pending,
    set_pending,
)


class ClarificationCacheTests(SimpleTestCase):
    @patch('apps.voice_commands.clarification.cache')
    def test_set_pending_stores_intent_and_slots_with_120s_timeout(self, mock_cache):
        set_pending(42, 'apply_leave', {'leave_type': 'sick'})

        mock_cache.set.assert_called_once_with(
            'voice:pending:42',
            {'intent': 'apply_leave', 'slots': {'leave_type': 'sick'}},
            timeout=120,
        )
        self.assertEqual(PENDING_TIMEOUT_SECONDS, 120)

    @patch('apps.voice_commands.clarification.cache')
    def test_get_pending_reads_the_same_key_set_pending_writes(self, mock_cache):
        mock_cache.get.return_value = {'intent': 'apply_leave', 'slots': {}}

        result = get_pending(42)

        mock_cache.get.assert_called_once_with('voice:pending:42')
        self.assertEqual(result, {'intent': 'apply_leave', 'slots': {}})

    @patch('apps.voice_commands.clarification.cache')
    def test_get_pending_returns_none_once_the_key_has_expired(self, mock_cache):
        # A real cache backend (Redis or LocMem) returns None once the TTL
        # lapses — this is what get_pending() sees in that case, with no
        # way to distinguish "expired" from "never set".
        mock_cache.get.return_value = None

        self.assertIsNone(get_pending(42))

    @patch('apps.voice_commands.clarification.cache')
    def test_clear_pending_deletes_the_key(self, mock_cache):
        clear_pending(42)

        mock_cache.delete.assert_called_once_with('voice:pending:42')

    @patch('apps.voice_commands.clarification.cache')
    def test_get_pending_refreshes_ttl_on_read_when_something_is_pending(self, mock_cache):
        # A sliding window: every read of an active pending state resets its
        # TTL to the full 120s, not just the write set_pending() already does.
        mock_cache.get.return_value = {'intent': 'apply_leave', 'slots': {}}

        get_pending(42)

        mock_cache.touch.assert_called_once_with('voice:pending:42', 120)

    @patch('apps.voice_commands.clarification.cache')
    def test_get_pending_does_not_touch_the_cache_when_nothing_is_pending(self, mock_cache):
        mock_cache.get.return_value = None

        get_pending(42)

        mock_cache.touch.assert_not_called()


class SlidingWindowRealCacheTests(SimpleTestCase):
    """
    Exercises the real cache backend (LocMemCache/Redis, whichever
    config/settings.py selects) with a shortened TTL so the multi-second
    gaps stay fast, proving get_pending()'s sliding window keeps a
    conversation alive across several turns even though the total elapsed
    time exceeds the original 120s-equivalent window several times over.
    """

    def tearDown(self):
        clear_pending(9001)

    @patch('apps.voice_commands.clarification.PENDING_TIMEOUT_SECONDS', 3)
    def test_ttl_slides_forward_on_each_read_across_multiple_turns(self):
        set_pending(9001, 'apply_leave', {'leave_type': 'sick'})

        # Each gap below is longer than the original 3s TTL would have
        # survived on its own -- if get_pending() didn't touch() the key on
        # every read, this would already be None well before the third turn.
        for _ in range(3):
            time.sleep(2)
            pending = get_pending(9001)
            self.assertIsNotNone(pending, 'sliding window should have kept the key alive')

        self.assertEqual(pending['intent'], 'apply_leave')

    @patch('apps.voice_commands.clarification.PENDING_TIMEOUT_SECONDS', 1)
    def test_real_inactivity_past_the_ttl_still_expires_cleanly(self):
        set_pending(9001, 'apply_leave', {'leave_type': 'sick'})

        time.sleep(1.5)

        self.assertIsNone(get_pending(9001))
