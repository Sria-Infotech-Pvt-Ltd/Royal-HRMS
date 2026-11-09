"""
Voice payroll analytics (executor_payroll_analytics.py) against the real payroll models, real users and Aira's real
seat-aware permission helpers (private test DB only).

Covered: permission (payroll.view via has_perm, no-branch users, the voice gate), admin vs branch scoping, empty/no-data
answers, period handling (latest / "last month" / explicit month / cancelled cycles ignored), the spoken summary shape and
Hindi wording, and the pending-cycles dispatch through the existing AttendancePendingCyclesView.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.payroll.models import EmployeePayslip, PayrollCycle
from apps.voice_commands import language
from apps.voice_commands.executor import (
    INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN, INTENT_CHECK_PAYROLL_COST_SUMMARY, INTENT_CHECK_PENDING_PAYROLL_CYCLES,
    execute_intent,
)
from apps.voice_commands.executor_payroll_analytics import (
    execute_check_branch_payroll_breakdown, execute_check_payroll_cost_summary, execute_check_pending_payroll_cycles,
)

_YEAR = datetime.date.today().year
_seq = [0]


def _unique(prefix: str) -> str:
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _branch(name: str) -> Branch:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=_unique('VPA'), branch_name=name, address='Test address', state=state, city=city,
        latitude=Decimal('17.4'), longitude=Decimal('78.4'), allowed_radius_meters=150, geofencing_enabled=True,
    )


def _cycle(branch, month, status=PayrollCycle.STATUS_PAID, *, year=_YEAR) -> PayrollCycle:
    creator = make_user(f'{_unique("creator")}@voice-analytics.test')
    start = datetime.date(year, month, 1)
    end = datetime.date(year, month, 28)
    return PayrollCycle.objects.create(
        branch=branch, cycle_start=start, cycle_end=end, pay_date=end, status=status, created_by=creator,
    )


def _payslip(cycle, gross, net) -> EmployeePayslip:
    employee = make_user(f'{_unique("emp")}@voice-analytics.test', role=make_role(_unique('role')))
    return EmployeePayslip.objects.create(
        cycle=cycle, employee=employee, annual_ctc=Decimal('120000'), monthly_ctc=Decimal('10000'),
        gross_earnings=Decimal(gross), net_pay=Decimal(net),
    )


def _user(permission_codenames, branch=None, **extra):
    return make_user(
        f'{_unique("user")}@voice-analytics.test', role=make_role(_unique('role'), permission_codenames=permission_codenames),
        branch=branch.branch_name if branch else '', **extra,
    )


def _request(user):
    return SimpleNamespace(user=user, META={})


class _AnalyticsBase(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(language.set_current_language, language.LANG_EN)
        language.set_current_language(language.LANG_EN)
        self.branch_a = _branch('Voice Analytics A')
        self.branch_b = _branch('Voice Analytics B')
        # Latest (October) cycle and the one before it (September) for A; one October cycle for B.
        self.a_oct = _cycle(self.branch_a, 10)
        self.a_sep = _cycle(self.branch_a, 9)
        self.b_oct = _cycle(self.branch_b, 10)
        _payslip(self.a_oct, '1000.00', '800.00')
        _payslip(self.a_oct, '2000.00', '1600.00')
        _payslip(self.a_sep, '500.00', '400.00')
        _payslip(self.b_oct, '5000.00', '4000.00')
        self.admin = _user(['payroll.view', 'settings.edit'])
        self.hr_a = _user(['payroll.view'], self.branch_a)
        self.hr_b = _user(['payroll.view'], self.branch_b)


class CostSummaryTests(_AnalyticsBase):
    def test_admin_sees_every_branch_latest_cycle(self):
        result = execute_check_payroll_cost_summary(_request(self.admin))
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.data['gross_earnings'], '8000.00')
        self.assertEqual(result.data['net_pay'], '6400.00')
        self.assertEqual(result.data['employee_count'], 3)
        self.assertEqual({row['branch_name'] for row in result.data['branches_included']},
                         {'Voice Analytics A', 'Voice Analytics B'})
        self.assertIn('₹8000.00', result.message)
        self.assertIn('₹6400.00', result.message)
        self.assertIn('3 employees', result.message)
        # the screen keeps the figures; the SPOKEN text carries none of them (see SpeechSafetyTests)
        self.assertIsNotNone(result.speech_message)

    def test_branch_scoped_user_sees_only_their_own_branch(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_a))
        self.assertTrue(result.success)
        self.assertEqual(result.data['gross_earnings'], '3000.00')
        self.assertEqual(result.data['employee_count'], 2)
        self.assertEqual([row['branch_name'] for row in result.data['branches_included']], ['Voice Analytics A'])

    def test_branch_scoped_user_never_sees_another_branchs_figures(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_b))
        self.assertEqual(result.data['gross_earnings'], '5000.00')
        self.assertNotIn('Voice Analytics A', [row['branch_name'] for row in result.data['branches_included']])

    def test_last_month_uses_the_previous_cycle(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_a), 'what was our payroll cost last month')
        self.assertEqual(result.data['gross_earnings'], '500.00')
        self.assertEqual(result.data['employee_count'], 1)

    def test_explicit_month_wins_over_offset(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_a), 'payroll cost summary for september')
        self.assertEqual(result.data['gross_earnings'], '500.00')

    def test_cancelled_latest_cycle_is_ignored(self):
        cancelled = _cycle(self.branch_a, 11, status=PayrollCycle.STATUS_CANCELLED)
        _payslip(cancelled, '99999.00', '99999.00')
        result = execute_check_payroll_cost_summary(_request(self.hr_a))
        self.assertEqual(result.data['gross_earnings'], '3000.00')

    def test_no_data_for_the_period_gives_a_clear_message(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_a), 'payroll cost for january')
        self.assertTrue(result.success)
        self.assertEqual(result.message, 'No payroll data was found for that period.')
        self.assertEqual(result.data['employee_count'], 0)

    def test_user_without_payroll_view_is_denied(self):
        user = _user(['payroll.view_own'], self.branch_a)
        result = execute_check_payroll_cost_summary(_request(user))
        self.assertFalse(result.success)
        self.assertEqual(result.message, "You don't have permission to view payroll analytics.")
        self.assertIsNone(result.data)

    def test_non_admin_without_a_branch_is_told_so(self):
        user = _user(['payroll.view'])
        result = execute_check_payroll_cost_summary(_request(user))
        self.assertFalse(result.success)
        self.assertIn('not assigned to a branch', result.message)

    def test_hindi_response(self):
        language.set_current_language(language.LANG_HI)
        result = execute_check_payroll_cost_summary(_request(self.admin))
        self.assertIn('चयनित अवधि', result.message)
        self.assertIn('₹8000.00', result.message)


class BranchBreakdownTests(_AnalyticsBase):
    def test_admin_gets_every_branch_highest_net_pay_first(self):
        result = execute_check_branch_payroll_breakdown(_request(self.admin))
        self.assertTrue(result.success)
        self.assertEqual([row['branch_name'] for row in result.data], ['Voice Analytics B', 'Voice Analytics A'])
        self.assertEqual(result.data[0]['net_pay'], '4000.00')
        self.assertEqual(result.data[1]['net_pay'], '2400.00')
        self.assertEqual(result.message, 'Top branches by net pay: Voice Analytics B: ₹4000.00, Voice Analytics A: ₹2400.00.')

    def test_spoken_summary_is_capped_at_three_branches_but_data_is_full(self):
        for index in range(3):
            extra = _branch(f'Voice Analytics Extra {index}')
            _payslip(_cycle(extra, 10), '100.00', f'{10 + index}.00')
        result = execute_check_branch_payroll_breakdown(_request(self.admin))
        self.assertEqual(len(result.data), 5)
        self.assertEqual(result.message.count('₹'), 3)

    def test_branch_scoped_user_gets_the_single_branch_phrasing(self):
        result = execute_check_branch_payroll_breakdown(_request(self.hr_a))
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.message, 'For Voice Analytics A, net pay for the period was ₹2400.00, across 2 employees.')

    def test_period_handling(self):
        result = execute_check_branch_payroll_breakdown(_request(self.hr_a), 'branch payroll breakdown last month')
        self.assertEqual(result.data[0]['net_pay'], '400.00')

    def test_no_data_message(self):
        result = execute_check_branch_payroll_breakdown(_request(self.admin), 'payroll breakdown by branch in january')
        self.assertTrue(result.success)
        self.assertEqual(result.message, 'No branch payroll data was found for that period.')
        self.assertEqual(result.data, [])

    def test_permission_denied_and_no_branch(self):
        denied = execute_check_branch_payroll_breakdown(_request(_user(['payroll.view_own'], self.branch_a)))
        self.assertFalse(denied.success)
        self.assertEqual(denied.message, "You don't have permission to view payroll analytics.")
        no_branch = execute_check_branch_payroll_breakdown(_request(_user(['payroll.view'])))
        self.assertFalse(no_branch.success)
        self.assertIn('not assigned to a branch', no_branch.message)


class VoiceGateAndPendingCyclesTests(_AnalyticsBase):
    def test_voice_gate_blocks_callers_without_payroll_view_before_any_query(self):
        user = _user(['payroll.view_own'], self.branch_a)
        for intent in (INTENT_CHECK_PAYROLL_COST_SUMMARY, INTENT_CHECK_BRANCH_PAYROLL_BREAKDOWN,
                       INTENT_CHECK_PENDING_PAYROLL_CYCLES):
            with self.subTest(intent):
                result = execute_intent(intent, _request(user), slots={'raw_text': ''})
                self.assertFalse(result.success)
                self.assertEqual(result.message, "You don't have permission to do that.")

    def test_dispatch_reaches_the_analytics_with_the_spoken_period(self):
        result = execute_intent(
            INTENT_CHECK_PAYROLL_COST_SUMMARY, _request(self.hr_a), slots={'raw_text': 'payroll cost last month'},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data['gross_earnings'], '500.00')

    def test_pending_cycles_counts_what_the_existing_view_returns(self):
        hr = _user(['payroll.view', 'payroll.edit'], self.branch_a)
        _cycle(self.branch_a, 12, status=PayrollCycle.STATUS_ATTENDANCE_PENDING)
        result = execute_check_pending_payroll_cycles(_request(hr))
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.message, 'You have 1 payroll cycle(s) awaiting your approval.')
        self.assertEqual(len(result.data), 1)

    def test_pending_cycles_respects_branch_scope(self):
        hr_b = _user(['payroll.view', 'payroll.edit'], self.branch_b)
        _cycle(self.branch_a, 12, status=PayrollCycle.STATUS_ATTENDANCE_PENDING)
        result = execute_check_pending_payroll_cycles(_request(hr_b))
        self.assertEqual(result.message, 'No payroll cycles are currently awaiting your approval.')

    def test_pending_cycles_for_someone_who_cannot_approve_is_denied_by_the_existing_view(self):
        user = _user(['payroll.view'], self.branch_a)
        _cycle(self.branch_a, 12, status=PayrollCycle.STATUS_ATTENDANCE_PENDING)
        result = execute_check_pending_payroll_cycles(_request(user))
        self.assertFalse(result.success)
        self.assertEqual(result.message, "You don't have permission to view payroll analytics.")


class SpeechSafetyTests(_AnalyticsBase):
    """Phase 7.2: figures stay on screen (`message`/`data`); what is SPOKEN (`speech_message`) is a scope-level aggregate
    only - counts of people/branches, never rupee amounts, branch names, per-branch pay or employee detail."""

    @staticmethod
    def _assert_speech_has_no_figures(result, *extra_forbidden):
        spoken = result.speech_message
        assert spoken, 'a speech-safe stand-in must be set'
        assert spoken != result.message
        for forbidden in ('\u20b9', 'gross', 'net pay', 'Voice Analytics', *extra_forbidden):
            assert forbidden.lower() not in spoken.lower(), (forbidden, spoken)

    def test_cost_summary_speech_is_an_aggregate_count_with_no_amounts(self):
        result = execute_check_payroll_cost_summary(_request(self.admin))
        self._assert_speech_has_no_figures(result, '8000', '6400')
        self.assertEqual(
            result.speech_message,
            'Your payroll cost summary for 3 employees across 2 branch(es) is ready to view on screen.',
        )
        # the screen still shows everything
        self.assertIn('\u20b98000.00', result.message)
        self.assertEqual(result.data['gross_earnings'], '8000.00')

    def test_cost_summary_speech_stays_inside_the_callers_branch_scope(self):
        result = execute_check_payroll_cost_summary(_request(self.hr_a))
        self.assertEqual(
            result.speech_message,
            'Your payroll cost summary for 2 employees across 1 branch(es) is ready to view on screen.',
        )
        self.assertNotIn('3', result.speech_message.replace('2 employees', ''))  # nothing from the other branch

    def test_breakdown_speech_names_no_branch_and_speaks_no_pay(self):
        result = execute_check_branch_payroll_breakdown(_request(self.admin))
        self._assert_speech_has_no_figures(result, '4000', '2400')
        self.assertEqual(result.speech_message, 'Your branch payroll breakdown for 2 branch(es) is ready to view on screen.')
        self.assertIn('Voice Analytics B: \u20b94000.00', result.message)  # full detail remains on screen

    def test_single_branch_breakdown_speech_is_a_count_only(self):
        result = execute_check_branch_payroll_breakdown(_request(self.hr_a))
        self._assert_speech_has_no_figures(result, '2400')
        self.assertEqual(result.speech_message, 'Your branch payroll summary for 2 employees is ready to view on screen.')

    def test_hindi_speech_is_also_figure_free(self):
        language.set_current_language(language.LANG_HI)
        for result in (
            execute_check_payroll_cost_summary(_request(self.admin)),
            execute_check_branch_payroll_breakdown(_request(self.admin)),
            execute_check_branch_payroll_breakdown(_request(self.hr_a)),
        ):
            self.assertTrue(result.speech_message)
            self.assertIn('स्क्रीन', result.speech_message)
            for figure in ('\u20b9', '8000', '6400', '4000', '2400', 'Voice Analytics'):
                self.assertNotIn(figure, result.speech_message)

    def test_no_data_and_denied_answers_carry_no_figures_and_are_spoken_as_shown(self):
        no_data = execute_check_payroll_cost_summary(_request(self.hr_a), 'payroll cost for january')
        self.assertIsNone(no_data.speech_message)
        denied = execute_check_payroll_cost_summary(_request(_user(['payroll.view_own'], self.branch_a)))
        self.assertIsNone(denied.speech_message)
        self.assertFalse(denied.success)

    def test_permission_and_branch_scoping_are_unchanged_by_the_speech_layer(self):
        self.assertFalse(execute_check_payroll_cost_summary(_request(_user(['payroll.view_own'], self.branch_a))).success)
        self.assertFalse(execute_check_branch_payroll_breakdown(_request(_user(['payroll.view']))).success)  # no branch
        self.assertEqual(execute_check_payroll_cost_summary(_request(self.hr_b)).data['gross_earnings'], '5000.00')

    def test_the_conversation_response_the_client_speaks_uses_the_safe_text(self):
        """End of the voice path: handle_transcript's payload (what /voice/parse/ returns and TTS reads) must carry the
        safe speech_message while its `message` still has the figures."""
        from unittest.mock import MagicMock

        from apps.voice_commands.conversation import handle_transcript

        request = MagicMock()
        request.user = self.admin
        request.META = {}
        payload = handle_transcript(request, 'what is our payroll cost')
        self.assertEqual(payload['intent'], 'check_payroll_cost_summary')
        self.assertIn('\u20b9', payload['message'])
        self.assertIsNotNone(payload['speech_message'])
        self.assertNotIn('\u20b9', payload['speech_message'])
        self.assertNotIn('8000', payload['speech_message'])
