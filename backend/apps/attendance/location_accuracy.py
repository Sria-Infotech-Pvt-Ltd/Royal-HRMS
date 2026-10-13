"""
Display-only GPS accuracy indicators for punch locations (HR detail + CSV).

Stored location_label / accuracy are never rewritten. Thresholds are display
guidance, not a guarantee of where the employee actually was:
  ≤ 100 m        → address shown as-is
  100 – 1,000 m  → "Location approximate (±X m): …"
  > 1,000 m      → "Approximate location (±X km): …"
A missing or invalid accuracy is "unknown" — never shown as zero or precise.
"""
from __future__ import annotations

import math

PRECISE_MAX_M = 100
APPROXIMATE_MAX_M = 1000
OFFICE_LABEL_PREFIX = 'Office – '  # written by reverse_geocode_punch_task for UK office punches

LEVEL_PRECISE = 'precise'
LEVEL_APPROXIMATE = 'approximate'
LEVEL_VERY_APPROXIMATE = 'very_approximate'


def parse_accuracy(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        metres = float(value)
    except (TypeError, ValueError, ArithmeticError):
        return None
    if not math.isfinite(metres) or metres < 0:
        return None
    return metres


def accuracy_level(value) -> str | None:
    metres = parse_accuracy(value)
    if metres is None:
        return None
    if metres <= PRECISE_MAX_M:
        return LEVEL_PRECISE
    if metres <= APPROXIMATE_MAX_M:
        return LEVEL_APPROXIMATE
    return LEVEL_VERY_APPROXIMATE


def format_accuracy(value) -> str | None:
    """'±17 m', '±390 m', '±1.5 km', '±20 km' — None when unknown. Rounds up beyond
    100 m so the shown uncertainty is never smaller than the reported one."""
    metres = parse_accuracy(value)
    if metres is None:
        return None
    if metres <= PRECISE_MAX_M:
        return f'±{round(metres)} m'
    if metres <= APPROXIMATE_MAX_M:
        return f'±{math.ceil(metres / 10) * 10} m'
    km = metres / 1000
    if km < 10:
        return f'±{math.ceil(km * 10) / 10:g} km'
    return f'±{math.ceil(km):,} km'


def is_office_label(text: str | None) -> bool:
    return bool(text) and text.startswith(OFFICE_LABEL_PREFIX)


def display_location(text: str | None, accuracy) -> str:
    """Location text with an approximate-location prefix when accuracy is poor."""
    if not text or is_office_label(text):
        return text or ''
    level = accuracy_level(accuracy)
    if level == LEVEL_APPROXIMATE:
        return f'Location approximate ({format_accuracy(accuracy)}): {text}'
    if level == LEVEL_VERY_APPROXIMATE:
        return f'Approximate location ({format_accuracy(accuracy)}): {text}'
    return text


def csv_accuracy_metres(value) -> str:
    """Whole metres for the CSV accuracy column, '' when unknown."""
    metres = parse_accuracy(value)
    return '' if metres is None else str(round(metres))
