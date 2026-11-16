"""Tests for core/logging_handlers.py (Windows-safe log rotation)."""
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from core.logging_handlers import WindowsSafeRotatingFileHandler


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord('test', logging.WARNING, __file__, 1, message, None, None)


class WindowsSafeRotatingFileHandlerTests(SimpleTestCase):
    def setUp(self):
        self.log_dir = Path(tempfile.mkdtemp())
        self.log_path = self.log_dir / 'errors.log'
        self.handler = WindowsSafeRotatingFileHandler(
            self.log_path, maxBytes=50, backupCount=2, encoding='utf-8',
        )
        self.handler.setFormatter(logging.Formatter('%(message)s'))

    def tearDown(self):
        self.handler.close()
        shutil.rmtree(self.log_dir, ignore_errors=True)

    def test_file_is_not_opened_until_the_first_record(self):
        self.assertFalse(self.log_path.exists())
        self.handler.emit(_record('first'))
        self.assertTrue(self.log_path.exists())

    def test_rotates_normally_when_the_file_is_not_locked(self):
        for index in range(10):
            self.handler.emit(_record(f'line {index} ' + 'x' * 20))
        self.assertTrue((self.log_dir / 'errors.log.1').exists())

    def test_failed_rename_keeps_writing_to_the_current_file(self):
        self.handler.emit(_record('x' * 60))  # file is now over maxBytes
        locked = PermissionError(32, 'The process cannot access the file because it is being used by another process')
        with mock.patch.object(self.handler, 'rotate', side_effect=locked):
            self.handler.emit(_record('kept after failed rotation'))
        self.handler.flush()
        self.assertIn('kept after failed rotation', self.log_path.read_text(encoding='utf-8'))
        self.assertFalse((self.log_dir / 'errors.log.1').exists())

    def test_failed_rename_is_not_retried_for_every_record(self):
        self.handler.emit(_record('x' * 60))
        with mock.patch.object(self.handler, 'rotate', side_effect=PermissionError(32, 'locked')) as rotate:
            for index in range(5):
                self.handler.emit(_record(f'record {index}'))
        self.assertEqual(rotate.call_count, 1)

    def test_rotation_is_retried_after_the_wait(self):
        self.handler.emit(_record('x' * 60))
        with mock.patch.object(self.handler, 'rotate', side_effect=PermissionError(32, 'locked')):
            self.handler.emit(_record('blocked'))
        self.handler._next_rollover_attempt = 0.0  # the wait has passed
        self.handler.emit(_record('rotates now'))
        self.assertTrue((self.log_dir / 'errors.log.1').exists())


class LoggingSettingsTests(SimpleTestCase):
    def test_file_handlers_use_the_windows_safe_class_only_on_windows(self):
        expected = (
            'core.logging_handlers.WindowsSafeRotatingFileHandler'
            if sys.platform == 'win32'
            else 'logging.handlers.RotatingFileHandler'
        )
        for name in ('auth_file', 'error_file', 'voice_commands_file'):
            self.assertEqual(settings.LOGGING['handlers'][name]['class'], expected, name)
