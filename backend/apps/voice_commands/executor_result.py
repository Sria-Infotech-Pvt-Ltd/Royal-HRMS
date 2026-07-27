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
