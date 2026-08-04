from __future__ import annotations

from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.correction_datetime_extractor import extract_time
from apps.voice_commands.correction_slot_extractor import extract_punch_type, looks_like_correction_reason
from apps.voice_commands.slot_extractor import extract_date_range, extract_leave_type

# Split out of conversation.py (already close to this project's 300-line
# file convention) — a stateless detection heuristic, unlike the
# conversation_*.py modules alongside it which each own a stateful
# start_X/continue_X turn-taking flow. Kept as its own module rather than
# folded into either slot_extractor.py or correction_slot_extractor.py
# because it reuses signals from BOTH (apply_leave's and
# request_attendance_correction's own slot extraction) and belongs to
# neither domain specifically.


def looks_like_expired_slot_answer(text: str) -> bool:
    """
    Best-effort guess that a transcript matching no registered command was
    actually a targeted answer to a clarification question — e.g. "sick
    leave", "july 24th", "9:15 am", "i forgot to punch", or a bare "yes"/"no"
    answering a "did you mean ...?" question — that arrived after its 120s
    window had already lapsed (get_pending() returned None), rather than a
    genuinely unrecognized command. Reuses the exact signals apply_leave's
    and request_attendance_correction's own slot extraction look for (a
    leave-type keyword, a parseable date, a clock time, a punch type, a
    correction reason), plus the same yes/no parser the live "did you mean"
    confirmation step uses, so an unrelated gibberish command isn't
    mislabeled as a timeout.
    """
    if parse_yes_no(text) is not None:
        return True
    if extract_leave_type(text):
        return True
    start, end = extract_date_range(text)
    if start or end:
        return True
    if extract_time(text):
        return True
    # targeted_answer intentionally omitted here (defaults False) — text is
    # whatever full transcript failed to match anything, not guaranteed to be
    # a short one-word answer, and the bare "in"/"out" fallback that flag
    # unlocks would false-positive on any ordinary sentence merely
    # containing those extremely common words (e.g. "what's the weather in
    # paris"). Only the distinctive compound phrases ("clock in", "punch
    # out", "both", ...) are trusted here.
    if extract_punch_type(text):
        return True
    return looks_like_correction_reason(text)
