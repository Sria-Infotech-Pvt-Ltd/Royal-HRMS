from django.test import SimpleTestCase

from apps.attendance.models import AttendancePunch
from apps.voice_commands.matcher import match_intent
from apps.voice_commands.mode_extractor import extract_attendance_mode
from apps.voice_commands.normalizer import normalize_transcript


class ExtractAttendanceModeTests(SimpleTestCase):
    def test_office_phrase_maps_to_office_mode(self):
        mode, _ = extract_attendance_mode(normalize_transcript('clock in at office'))
        self.assertEqual(mode, AttendancePunch.MODE_OFFICE)

    def test_wfh_phrase_maps_to_wfh_mode(self):
        mode, _ = extract_attendance_mode(normalize_transcript('clock in from home'))
        self.assertEqual(mode, AttendancePunch.MODE_WFH)

    def test_field_phrase_maps_to_field_mode(self):
        mode, _ = extract_attendance_mode(normalize_transcript('clock in for field work'))
        self.assertEqual(mode, AttendancePunch.MODE_FIELD)

    def test_client_location_phrase_maps_to_client_location_mode(self):
        mode, _ = extract_attendance_mode(normalize_transcript('clock in at client site'))
        self.assertEqual(mode, AttendancePunch.MODE_CLIENT_LOCATION)

    def test_remote_office_phrase_maps_to_remote_office_mode(self):
        mode, _ = extract_attendance_mode(normalize_transcript('clock in remote'))
        self.assertEqual(mode, AttendancePunch.MODE_REMOTE_OFFICE)

    def test_no_mode_mentioned_returns_none(self):
        """
        No default here — extract_attendance_mode() returns None (not
        MODE_OFFICE) when nothing is said, so executor.py can apply its own
        per-intent fallback (clock_in -> office, clock_out -> inherit from
        the open IN punch) instead of both being forced to the same default.
        """
        mode, remaining = extract_attendance_mode(normalize_transcript('clock me in'))
        self.assertIsNone(mode)
        self.assertEqual(remaining, 'clock me in')

    def test_mode_phrase_is_stripped_from_remaining_text(self):
        _, remaining = extract_attendance_mode(normalize_transcript('clock in from home'))
        self.assertNotIn('from home', remaining)

    def test_mode_phrase_stripped_before_intent_matching(self):
        """
        Regression test: left in the transcript, 'from home' drags the fuzzy
        score against 'clock in' below match_intent()'s threshold, causing a
        false no_match. extract_attendance_mode() must strip it out first so
        the remainder scores cleanly against the intent's own phrase list.
        """
        normalized = normalize_transcript('clock in from home')
        mode, remaining = extract_attendance_mode(normalized)
        self.assertEqual(mode, AttendancePunch.MODE_WFH)

        result = match_intent(remaining)
        self.assertEqual(result.intent, 'clock_in')
        self.assertGreaterEqual(result.confidence, 80)


class ModePrepositionCombinationRegressionTests(SimpleTestCase):
    """
    Regression coverage for the whole class of bug 'clock in from home' was
    one instance of: a mode phrase spoken with a leading preposition that
    isn't baked into the registered phrase text (e.g. "from client
    location", "for field work", "at remote office") leaves that preposition
    dangling after stripping, dragging the fuzzy score against 'clock in'
    below match_intent()'s threshold — even though extract_attendance_mode()
    still returns the *correct mode*, which is exactly why
    test_field_phrase_maps_to_field_mode and
    test_client_location_phrase_maps_to_client_location_mode above didn't
    catch it: they only ever asserted on the returned mode, never on whether
    match_intent() could still recognize clock_in afterwards.

    This checks every mode against every preposition that naturally
    introduces it (plus the no-preposition and "in X" forms), asserting BOTH
    the mode returned and that match_intent() still recognizes clock_in on
    what's left — the only way to actually catch the leftover-preposition
    class of bug rather than just the mode-detection half of it.
    """

    CASES = [
        ('clock in at office',            AttendancePunch.MODE_OFFICE),
        ('clock in in office',            AttendancePunch.MODE_OFFICE),
        ('clock in from office',          AttendancePunch.MODE_OFFICE),
        ('clock in for office',           AttendancePunch.MODE_OFFICE),
        ('clock in from home',            AttendancePunch.MODE_WFH),
        ('clock in at home',              AttendancePunch.MODE_WFH),
        ('clock in for home',             AttendancePunch.MODE_WFH),
        ('clock in wfh',                  AttendancePunch.MODE_WFH),
        ('clock in for field work',       AttendancePunch.MODE_FIELD),
        ('clock in at field work',        AttendancePunch.MODE_FIELD),
        ('clock in from field work',      AttendancePunch.MODE_FIELD),
        ('clock in in the field',         AttendancePunch.MODE_FIELD),
        ('clock in from client location', AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in at client location',   AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in for client location',  AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in at client site',       AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in at the client',        AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in from the client',      AttendancePunch.MODE_CLIENT_LOCATION),
        ('clock in at remote office',     AttendancePunch.MODE_REMOTE_OFFICE),
        ('clock in from remote office',   AttendancePunch.MODE_REMOTE_OFFICE),
        ('clock in for remote office',    AttendancePunch.MODE_REMOTE_OFFICE),
        ('clock in remote',               AttendancePunch.MODE_REMOTE_OFFICE),
        ('clock in at remote',            AttendancePunch.MODE_REMOTE_OFFICE),
        ('clock in from remote',          AttendancePunch.MODE_REMOTE_OFFICE),
    ]

    def test_every_mode_and_preposition_combination_still_matches_clock_in(self):
        for transcript, expected_mode in self.CASES:
            with self.subTest(transcript=transcript):
                normalized = normalize_transcript(transcript)
                mode, remaining = extract_attendance_mode(normalized)

                self.assertEqual(mode, expected_mode)

                result = match_intent(remaining)
                self.assertEqual(
                    result.intent, 'clock_in',
                    f'{transcript!r} left remaining={remaining!r}, which failed to match clock_in '
                    f'(confidence={result.confidence})',
                )
                self.assertGreaterEqual(result.confidence, 80)

    def test_no_leading_preposition_is_left_dangling_in_the_remainder(self):
        dangling_words = {'from', 'at', 'for'}
        for transcript, _ in self.CASES:
            with self.subTest(transcript=transcript):
                normalized = normalize_transcript(transcript)
                _, remaining = extract_attendance_mode(normalized)
                remaining_words = set(remaining.split())
                self.assertFalse(
                    remaining_words & dangling_words,
                    f'{transcript!r} left a dangling preposition in remaining={remaining!r}',
                )
