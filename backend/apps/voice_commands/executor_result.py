from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Split out of executor.py on its own so executor_attendance.py/executor_leave.py/
# executor_approval.py can import it without a circular import back to
# executor.py (which imports execute_* functions from all three of them).


@dataclass
class ExecutionResult:
    success: bool
    message: str
    data: Optional[Any] = None
    # Optional, content-redacted stand-in for `message` when TTS speaks this
    # result aloud — None (the default, used by every intent that doesn't set
    # it) means "speak `message` unchanged", same as before this field
    # existed. Only intents whose `message` contains figures or a third
    # party's personal details set this — see executor_payroll.py/
    # executor_leave.py/executor_approval.py. `message` itself is never
    # redacted: the panel/toast always shows full detail regardless of what
    # gets spoken.
    speech_message: Optional[str] = None
