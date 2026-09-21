from __future__ import annotations

import datetime


def format_date_display(value: datetime.date | datetime.datetime | None, fmt: str = '%d-%m-%Y') -> str:
    """Render a date/datetime for human-facing text (emails, exports, PDFs) as DD-MM-YYYY.

    API/JSON payloads must keep DRF's default ISO 8601 serialization — this helper
    is only for strings shown directly to a user (emails, notifications, documents).
    """
    if value is None:
        return ''
    return value.strftime(fmt)
