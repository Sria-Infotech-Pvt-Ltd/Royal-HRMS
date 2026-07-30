from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.voice_commands.executor import INTENT_GREETING, execute_intent
from apps.voice_commands.executor_greeting import execute_greeting
from apps.voice_commands.matcher import get_conversational, get_required_permission


def _fake_request(full_name='', email='jane@example.com'):
    return SimpleNamespace(user=SimpleNamespace(full_name=full_name, email=email))


class GreetingRegistryTests(SimpleTestCase):
    def test_requires_no_permission(self):
        """Matches VoiceParseView itself, which is IsAuthenticated only —
        greeting needs nothing beyond that."""
        self.assertIsNone(get_required_permission(INTENT_GREETING))

    def test_is_not_conversational(self):
        """Single-turn — no slot-filling, no follow-up question."""
        self.assertFalse(get_conversational(INTENT_GREETING))


class GreetingDisplayNameTests(SimpleTestCase):
    """
    display_name must reuse the exact same source the dashboard's
    "Welcome back, {name}" banner uses — User.full_name — falling back to
    email the same way dashboard/views/manager.py's manager_name does.
    """

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_uses_full_name_when_present(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 10, 0)
        request = _fake_request(full_name='Priya Sharma', email='priya@example.com')

        result = execute_greeting(request)

        self.assertIn('Priya Sharma', result.message)
        self.assertNotIn('priya@example.com', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_falls_back_to_email_when_full_name_blank(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 10, 0)
        request = _fake_request(full_name='', email='priya@example.com')

        result = execute_greeting(request)

        self.assertIn('priya@example.com', result.message)


class GreetingTimeOfDayTests(SimpleTestCase):
    """
    Time-of-day must come from the actual server clock (timezone.localtime()),
    never from parsing what the user said — execute_greeting() takes no
    transcript at all, so "hi", "hey", and "good morning" all resolve through
    this same clock-only path regardless of phrasing.
    """

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_early_morning_is_morning(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 6, 30)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good morning', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_just_before_noon_is_still_morning(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 11, 59)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good morning', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_noon_is_afternoon(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 12, 0)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good afternoon', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_mid_afternoon_is_afternoon(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 15, 0)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good afternoon', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_5pm_is_evening(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 17, 0)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good evening', result.message)

    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_late_night_is_still_evening(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 23, 30)
        result = execute_greeting(_fake_request(full_name='Priya'))
        self.assertIn('good evening', result.message)


class GreetingDispatchTests(SimpleTestCase):
    @patch('apps.voice_commands.executor_greeting.timezone.localtime')
    def test_execute_intent_routes_to_greeting(self, mock_localtime):
        mock_localtime.return_value = datetime(2026, 7, 28, 9, 0)
        request = _fake_request(full_name='Priya Sharma')

        result = execute_intent(INTENT_GREETING, request)

        self.assertTrue(result.success)
        self.assertIn('Priya Sharma', result.message)
        self.assertIn('good morning', result.message)
        self.assertIn('How can I help you today', result.message)
