from django.test import SimpleTestCase

from apps.voice_commands.matcher import NO_MATCH_INTENT, match_intent
from apps.voice_commands.normalizer import normalize_transcript


class MatchIntentTests(SimpleTestCase):
    def test_matches_clock_in_exact_phrase(self):
        result = match_intent(normalize_transcript('clock in'))
        self.assertEqual(result.intent, 'clock_in')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_clock_in_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please punch in'))
        self.assertEqual(result.intent, 'clock_in')

    def test_matches_clock_in_with_typo(self):
        result = match_intent(normalize_transcript('clok in'))
        self.assertEqual(result.intent, 'clock_in')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_clock_out_exact_phrase(self):
        result = match_intent(normalize_transcript('clock out'))
        self.assertEqual(result.intent, 'clock_out')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_clock_out_with_typo(self):
        result = match_intent(normalize_transcript('clock uot'))
        self.assertEqual(result.intent, 'clock_out')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_leave_balance_exact_phrase(self):
        result = match_intent(normalize_transcript('how many leaves do i have'))
        self.assertEqual(result.intent, 'check_leave_balance')

    def test_matches_check_leave_balance_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('please check my leave balance'))
        self.assertEqual(result.intent, 'check_leave_balance')

    def test_matches_check_leave_status_exact_phrase(self):
        result = match_intent(normalize_transcript('check my leave status'))
        self.assertEqual(result.intent, 'check_leave_status')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_leave_status_alternate_phrasing(self):
        result = match_intent(normalize_transcript('did my leave get approved'))
        self.assertEqual(result.intent, 'check_leave_status')

    def test_matches_check_leave_status_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please check my leave status'))
        self.assertEqual(result.intent, 'check_leave_status')

    def test_matches_check_leave_status_with_typo(self):
        result = match_intent(normalize_transcript('wat is teh staus of my leve'))
        self.assertEqual(result.intent, 'check_leave_status')
        self.assertGreaterEqual(result.confidence, 80)

    def test_check_leave_status_not_confused_with_check_leave_balance(self):
        """'status' vs 'balance' are different intents — must not cross-match."""
        result = match_intent(normalize_transcript('check my leave balance'))
        self.assertEqual(result.intent, 'check_leave_balance')

    def test_matches_cancel_leave_exact_phrase(self):
        result = match_intent(normalize_transcript('cancel my leave'))
        self.assertEqual(result.intent, 'cancel_leave')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_cancel_leave_alternate_phrasing(self):
        result = match_intent(normalize_transcript('withdraw my leave request'))
        self.assertEqual(result.intent, 'cancel_leave')

    def test_matches_cancel_leave_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('um cancel my leave application please'))
        self.assertEqual(result.intent, 'cancel_leave')

    def test_matches_cancel_leave_with_typo(self):
        result = match_intent(normalize_transcript('cancl my leav'))
        self.assertEqual(result.intent, 'cancel_leave')
        self.assertGreaterEqual(result.confidence, 80)

    def test_nonsense_transcript_returns_no_match(self):
        result = match_intent(normalize_transcript('what is the weather today in paris'))
        self.assertEqual(result.intent, NO_MATCH_INTENT)

    def test_empty_transcript_returns_no_match(self):
        result = match_intent('')
        self.assertEqual(result.intent, NO_MATCH_INTENT)

    def test_matches_check_attendance_stats_exact_phrase(self):
        result = match_intent(normalize_transcript('check my attendance'))
        self.assertEqual(result.intent, 'check_attendance_stats')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_attendance_stats_alternate_phrasing(self):
        result = match_intent(normalize_transcript('how many days have i been present'))
        self.assertEqual(result.intent, 'check_attendance_stats')

    def test_matches_check_attendance_stats_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript("please show my attendance stats"))
        self.assertEqual(result.intent, 'check_attendance_stats')

    def test_matches_check_attendance_stats_with_typo(self):
        result = match_intent(normalize_transcript('wats my attendence percentage'))
        self.assertEqual(result.intent, 'check_attendance_stats')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_attendance_summary_exact_phrase(self):
        result = match_intent(normalize_transcript('show my attendance summary'))
        self.assertEqual(result.intent, 'check_attendance_summary')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_attendance_summary_alternate_phrasing(self):
        result = match_intent(normalize_transcript('monthly attendance summary'))
        self.assertEqual(result.intent, 'check_attendance_summary')

    def test_check_attendance_stats_not_confused_with_check_attendance_summary(self):
        """'stats' vs 'summary' are different intents — must not cross-match."""
        result = match_intent(normalize_transcript('show my attendance stats'))
        self.assertEqual(result.intent, 'check_attendance_stats')

    def test_matches_request_attendance_correction_exact_phrase(self):
        result = match_intent(normalize_transcript('request attendance correction'))
        self.assertEqual(result.intent, 'request_attendance_correction')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_request_attendance_correction_alternate_phrasing(self):
        result = match_intent(normalize_transcript('my attendance is wrong'))
        self.assertEqual(result.intent, 'request_attendance_correction')

    def test_matches_request_attendance_correction_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please correct my attendance'))
        self.assertEqual(result.intent, 'request_attendance_correction')

    # ── Fuzzy-match collision checks ────────────────────────────────────────
    # The new attendance intents share the "check my <noun>" phrasing pattern
    # with check_leave_balance/check_leave_status — these prove the fuzzy
    # matcher keeps "leave" vs "attendance" transcripts routed to the right
    # domain instead of cross-matching on shared filler tokens.

    def test_check_my_leave_status_not_confused_with_check_attendance_stats(self):
        result = match_intent(normalize_transcript('check my leave status'))
        self.assertEqual(result.intent, 'check_leave_status')

    def test_check_my_leave_balance_not_confused_with_check_attendance_stats(self):
        result = match_intent(normalize_transcript('check my leave balance'))
        self.assertEqual(result.intent, 'check_leave_balance')

    def test_check_my_attendance_not_confused_with_check_leave_status(self):
        result = match_intent(normalize_transcript('check my attendance'))
        self.assertEqual(result.intent, 'check_attendance_stats')

    def test_check_my_attendance_not_confused_with_check_leave_balance(self):
        result = match_intent(normalize_transcript('check my attendance'))
        self.assertNotEqual(result.intent, 'check_leave_balance')

    def test_attendance_summary_not_confused_with_leave_status(self):
        result = match_intent(normalize_transcript('show my attendance summary'))
        self.assertNotEqual(result.intent, 'check_leave_status')

    def test_attendance_correction_not_confused_with_cancel_leave(self):
        """Both involve a written request/correction of an existing record — must not cross-match."""
        result = match_intent(normalize_transcript('request attendance correction'))
        self.assertNotEqual(result.intent, 'cancel_leave')

    def test_cancel_leave_not_confused_with_attendance_correction(self):
        result = match_intent(normalize_transcript('cancel my leave'))
        self.assertEqual(result.intent, 'cancel_leave')

    def test_matches_apply_leave_exact_phrase(self):
        result = match_intent(normalize_transcript('apply for leave'))
        self.assertEqual(result.intent, 'apply_leave')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_apply_leave_alternate_phrasing(self):
        result = match_intent(normalize_transcript('i need to take leave'))
        self.assertEqual(result.intent, 'apply_leave')

    def test_matches_apply_leave_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('please request leave'))
        self.assertEqual(result.intent, 'apply_leave')

    def test_apply_leave_not_confused_with_cancel_leave(self):
        result = match_intent(normalize_transcript('apply for leave'))
        self.assertNotEqual(result.intent, 'cancel_leave')

    def test_apply_leave_not_confused_with_check_leave_status(self):
        result = match_intent(normalize_transcript('i want to apply for leave'))
        self.assertNotEqual(result.intent, 'check_leave_status')

    def test_apply_leave_not_confused_with_check_leave_balance(self):
        result = match_intent(normalize_transcript('request leave'))
        self.assertNotEqual(result.intent, 'check_leave_balance')

    def test_cancel_my_leave_not_confused_with_apply_leave(self):
        result = match_intent(normalize_transcript('cancel my leave'))
        self.assertEqual(result.intent, 'cancel_leave')

    def test_check_my_leave_status_not_confused_with_apply_leave(self):
        result = match_intent(normalize_transcript('check my leave status'))
        self.assertEqual(result.intent, 'check_leave_status')

    def test_matches_check_team_leave_queue_exact_phrase(self):
        result = match_intent(normalize_transcript("show my team's leave requests"))
        self.assertEqual(result.intent, 'check_team_leave_queue')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_team_leave_queue_alternate_phrasing(self):
        result = match_intent(normalize_transcript('how many leave requests are pending'))
        self.assertEqual(result.intent, 'check_team_leave_queue')

    def test_matches_check_team_leave_queue_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please show the approval queue'))
        self.assertEqual(result.intent, 'check_team_leave_queue')

    def test_check_team_leave_queue_not_confused_with_check_leave_status(self):
        """Team queue vs. the caller's own status — must not cross-match."""
        result = match_intent(normalize_transcript('check my leave status'))
        self.assertEqual(result.intent, 'check_leave_status')

    def test_check_leave_status_not_confused_with_check_team_leave_queue(self):
        result = match_intent(normalize_transcript('check pending leave approvals'))
        self.assertEqual(result.intent, 'check_team_leave_queue')

    def test_matches_how_many_unapproved_leaves_i_have_as_check_leave_status(self):
        """
        "leaves I have" reads as the employee's own pending requests, not the
        team approval queue — this must route to check_leave_status, not
        check_team_leave_queue, despite the "unapproved" wording overlapping
        with that intent's phrasing.
        """
        result = match_intent(normalize_transcript('how many unapproved leaves i have'))
        self.assertEqual(result.intent, 'check_leave_status')
        self.assertGreaterEqual(result.confidence, 80)

    def test_how_many_unapproved_leaves_i_have_not_confused_with_check_team_leave_queue(self):
        result = match_intent(normalize_transcript('how many unapproved leaves i have'))
        self.assertNotEqual(result.intent, 'check_team_leave_queue')

    def test_matches_check_team_attendance_exact_phrase(self):
        result = match_intent(normalize_transcript('check team attendance'))
        self.assertEqual(result.intent, 'check_team_attendance')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_team_attendance_alternate_phrasing(self):
        result = match_intent(normalize_transcript("how's the team's attendance today"))
        self.assertEqual(result.intent, 'check_team_attendance')

    def test_matches_check_team_attendance_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please show attendance dashboard'))
        self.assertEqual(result.intent, 'check_team_attendance')

    def test_check_team_attendance_not_confused_with_check_attendance_stats(self):
        """Team-wide dashboard vs. the caller's own attendance — must not cross-match."""
        result = match_intent(normalize_transcript('check my attendance'))
        self.assertEqual(result.intent, 'check_attendance_stats')

    def test_check_attendance_stats_not_confused_with_check_team_attendance(self):
        result = match_intent(normalize_transcript('show attendance dashboard'))
        self.assertEqual(result.intent, 'check_team_attendance')
