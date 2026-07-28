from django.test import SimpleTestCase

from apps.voice_commands.matcher import (
    CLARIFICATION_CONFIDENCE_THRESHOLD,
    DEFAULT_CONFIDENCE_THRESHOLD,
    NO_MATCH_INTENT,
    match_intent,
)
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

    # ── Payroll intents ──────────────────────────────────────────────────────

    def test_matches_check_my_payslip_exact_phrase(self):
        result = match_intent(normalize_transcript('check my payslip'))
        self.assertEqual(result.intent, 'check_my_payslip')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_my_payslip_alternate_phrasing(self):
        result = match_intent(normalize_transcript("what's my net pay"))
        self.assertEqual(result.intent, 'check_my_payslip')

    def test_matches_check_my_payslip_with_filler_words_stripped(self):
        result = match_intent(normalize_transcript('can you please check my salary'))
        self.assertEqual(result.intent, 'check_my_payslip')

    def test_check_my_payslip_not_confused_with_check_leave_balance(self):
        """Shared 'check my <noun>' phrasing — must not cross-match into leave/attendance."""
        result = match_intent(normalize_transcript('check my payslip'))
        self.assertNotEqual(result.intent, 'check_leave_balance')

    def test_check_my_payslip_not_confused_with_check_attendance_stats(self):
        result = match_intent(normalize_transcript('check my salary'))
        self.assertNotEqual(result.intent, 'check_attendance_stats')

    def test_check_leave_balance_not_confused_with_check_my_payslip(self):
        result = match_intent(normalize_transcript('how many leaves do i have'))
        self.assertEqual(result.intent, 'check_leave_balance')

    def test_matches_acknowledge_payslip_exact_phrase(self):
        result = match_intent(normalize_transcript('acknowledge my payslip'))
        self.assertEqual(result.intent, 'acknowledge_payslip')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_acknowledge_payslip_alternate_phrasing(self):
        result = match_intent(normalize_transcript('confirm my payslip'))
        self.assertEqual(result.intent, 'acknowledge_payslip')

    def test_acknowledge_payslip_not_confused_with_check_my_payslip(self):
        result = match_intent(normalize_transcript('acknowledge my payslip'))
        self.assertNotEqual(result.intent, 'check_my_payslip')

    def test_check_my_payslip_not_confused_with_acknowledge_payslip(self):
        result = match_intent(normalize_transcript('check my payslip'))
        self.assertNotEqual(result.intent, 'acknowledge_payslip')

    def test_matches_raise_payslip_query_exact_phrase(self):
        result = match_intent(normalize_transcript('raise a payslip query'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_raise_payslip_query_alternate_phrasing(self):
        result = match_intent(normalize_transcript('something\'s wrong with my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')

    def test_matches_raise_a_query_about_my_payslip_with_high_confidence(self):
        """Regression guard for the reported recognition failures on this
        exact phrase and its close variants — this one is registered
        verbatim so it should score a perfect match, not just clear the
        threshold."""
        result = match_intent(normalize_transcript('raise a query about my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 95)

    def test_matches_raise_a_query_regarding_my_payslip(self):
        """'regarding' isn't stripped as filler like 'please'/'can you' are —
        it's a genuine content-word substitution for 'about'/'on' that used
        to drag this below match_intent()'s 80 threshold before a phrase
        anchoring 'regarding' was registered."""
        result = match_intent(normalize_transcript('raise a query regarding my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_i_want_to_raise_a_query_regarding_my_payslip(self):
        result = match_intent(normalize_transcript('i want to raise a query regarding my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_i_have_a_query_regarding_my_payslip(self):
        result = match_intent(normalize_transcript('i have a query regarding my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_raise_a_concern_about_my_payslip(self):
        result = match_intent(normalize_transcript('raise a concern about my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_raise_an_issue_about_my_payslip(self):
        result = match_intent(normalize_transcript('raise an issue about my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_raise_a_complaint_about_my_payslip(self):
        result = match_intent(normalize_transcript('raise a complaint about my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_raise_a_concern_about_my_attendance_not_confused_with_raise_payslip_query(self):
        """The new 'concern'/'issue' wording is payslip-specific — swapping
        in 'attendance' must not cross-match into raise_payslip_query."""
        result = match_intent(normalize_transcript('i want to raise a concern about my attendance'))
        self.assertNotEqual(result.intent, 'raise_payslip_query')

    def test_matches_download_my_payslip_as_raise_payslip_query(self):
        """Download-flavored phrases route into the same intent — see
        conversation_payroll.py's download-redirect preamble, not a
        dead-end rejection."""
        result = match_intent(normalize_transcript('download my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_send_me_my_payslip_as_raise_payslip_query(self):
        result = match_intent(normalize_transcript('send me my payslip'))
        self.assertEqual(result.intent, 'raise_payslip_query')

    def test_matches_get_my_payslip_pdf_as_raise_payslip_query(self):
        result = match_intent(normalize_transcript('get my payslip pdf'))
        self.assertEqual(result.intent, 'raise_payslip_query')

    def test_raise_payslip_query_not_confused_with_check_my_payslip(self):
        result = match_intent(normalize_transcript('raise a query about my payslip'))
        self.assertNotEqual(result.intent, 'check_my_payslip')

    def test_check_my_payslip_not_confused_with_raise_payslip_query(self):
        result = match_intent(normalize_transcript('check my payslip'))
        self.assertNotEqual(result.intent, 'raise_payslip_query')

    def test_raise_payslip_query_not_confused_with_request_attendance_correction(self):
        """Both are 'raise a request about something wrong' shaped phrases —
        must not cross-match across domains."""
        result = match_intent(normalize_transcript('raise a payslip query'))
        self.assertNotEqual(result.intent, 'request_attendance_correction')

    def test_request_attendance_correction_not_confused_with_raise_payslip_query(self):
        result = match_intent(normalize_transcript('request attendance correction'))
        self.assertEqual(result.intent, 'request_attendance_correction')

    def test_matches_check_employee_payslip_exact_phrase(self):
        result = match_intent(normalize_transcript("check an employee's payslip"))
        self.assertEqual(result.intent, 'check_employee_payslip')
        self.assertGreaterEqual(result.confidence, 80)

    def test_matches_check_employee_payslip_alternate_phrasing(self):
        result = match_intent(normalize_transcript('how much did an employee get paid'))
        self.assertEqual(result.intent, 'check_employee_payslip')

    def test_check_employee_payslip_not_confused_with_check_my_payslip(self):
        """'an employee's'/'someone's' vs 'my' — must not cross-match."""
        result = match_intent(normalize_transcript("check an employee's payslip"))
        self.assertNotEqual(result.intent, 'check_my_payslip')

    def test_check_my_payslip_not_confused_with_check_employee_payslip(self):
        result = match_intent(normalize_transcript('check my payslip'))
        self.assertEqual(result.intent, 'check_my_payslip')

    def test_check_employee_payslip_not_confused_with_check_team_leave_queue(self):
        result = match_intent(normalize_transcript("check an employee's payslip"))
        self.assertNotEqual(result.intent, 'check_team_leave_queue')

    def test_check_employee_payslip_not_confused_with_approve_leave(self):
        """Both can be phrased with a bare pronoun ('check her payslip' /
        'approve her leave') — must not cross-match across domains."""
        result = match_intent(normalize_transcript('check her payslip'))
        self.assertNotEqual(result.intent, 'approve_leave')

    def test_approve_leave_not_confused_with_check_employee_payslip(self):
        result = match_intent(normalize_transcript('approve her leave'))
        self.assertEqual(result.intent, 'approve_leave')


class CandidateIntentClarificationBandTests(SimpleTestCase):
    """
    MatchResult.candidate_intent — the "did you mean" clarification flow's
    only hook into the matcher (see conversation.py's _start_clarification).
    Set exactly when confidence lands in
    [CLARIFICATION_CONFIDENCE_THRESHOLD, DEFAULT_CONFIDENCE_THRESHOLD); None
    both below that band (too far off to guess) and at/above it (already a
    confident match, nothing left to clarify).
    """

    def test_confident_match_has_no_candidate_intent(self):
        result = match_intent(normalize_transcript('clock in'))
        self.assertEqual(result.intent, 'clock_in')
        self.assertIsNone(result.candidate_intent)

    def test_real_garbled_stt_transcript_sets_candidate_intent(self):
        """'raise a queryAbout my Paisley' — an actual logged near-miss for
        raise_payslip_query's registered phrasing — must resolve to a
        NO_MATCH_INTENT result that still carries the candidate."""
        result = match_intent(normalize_transcript('raise a queryAbout my Paisley'))
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertTrue(CLARIFICATION_CONFIDENCE_THRESHOLD <= result.confidence < DEFAULT_CONFIDENCE_THRESHOLD)
        self.assertEqual(result.candidate_intent, 'raise_payslip_query')
        self.assertIsNotNone(result.matched_phrase)

    def test_real_gibberish_transcript_has_no_candidate_intent(self):
        """'asdkjhasd' — actual logged gibberish — must score well below the
        clarification floor and carry no guess at all."""
        result = match_intent(normalize_transcript('asdkjhasd'))
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertLess(result.confidence, CLARIFICATION_CONFIDENCE_THRESHOLD)
        self.assertIsNone(result.candidate_intent)

    def test_unrelated_sentence_has_no_candidate_intent(self):
        result = match_intent(normalize_transcript('what is the weather today in paris'))
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertLess(result.confidence, CLARIFICATION_CONFIDENCE_THRESHOLD)
        self.assertIsNone(result.candidate_intent)

    def test_empty_transcript_has_no_candidate_intent(self):
        result = match_intent('')
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertIsNone(result.candidate_intent)

    def test_score_just_below_clarification_threshold_has_no_candidate_intent(self):
        """A custom threshold pins the boundary itself, independent of
        whatever real registry phrases happen to score today — proves the
        cutoff is exact (score >= floor), not off-by-one in either direction."""
        result = match_intent(
            normalize_transcript('clock in'), threshold=101,
        )
        # 'clock in' now can't clear the (impossible) 101 confident-match
        # threshold, so it falls into the NO_MATCH branch — but its exact
        # phrase match (100) still clears CLARIFICATION_CONFIDENCE_THRESHOLD.
        self.assertEqual(result.intent, NO_MATCH_INTENT)
        self.assertEqual(result.candidate_intent, 'clock_in')
