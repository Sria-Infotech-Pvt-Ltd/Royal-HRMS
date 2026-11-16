"""
Log file handler that keeps working when Windows refuses to rotate a log file.

Windows cannot rename a file while another process has it open. `manage.py
runserver` runs two processes (the autoreload watcher and the server it
restarts) and both load settings.LOGGING, so both used to open logs/errors.log
at startup. When the server process reached maxBytes, the rename to
errors.log.1 failed with PermissionError [WinError 32] on every record.

settings.py uses this class on Windows only; Linux (production) keeps the
standard RotatingFileHandler.
"""
import logging.handlers
import time


class WindowsSafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that opens its file lazily and survives a failed rotation.

    - delay=True by default: the file is opened on the first record, so a
      process that never logs (the runserver watcher) never holds it open.
    - If the rename still fails because another process has the file open,
      writing continues in the current file and rotation is retried after
      ROLLOVER_RETRY_SECONDS instead of being attempted for every record.
    """

    ROLLOVER_RETRY_SECONDS = 60

    def __init__(self, *args, delay: bool = True, **kwargs):
        super().__init__(*args, delay=delay, **kwargs)
        self._next_rollover_attempt = 0.0

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        if time.monotonic() < self._next_rollover_attempt:
            return False
        return bool(super().shouldRollover(record))

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except PermissionError:
            # The stream was closed before the rename; FileHandler.emit
            # reopens the same file in append mode, so the record is kept.
            self._next_rollover_attempt = time.monotonic() + self.ROLLOVER_RETRY_SECONDS
