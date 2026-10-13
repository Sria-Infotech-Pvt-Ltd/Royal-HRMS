"""Phase 7B Task A — generate_periods() and link_historical_cycles()."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.branch.models import Branch, City, State
from apps.hrms.models import Holiday
from apps.payroll.models import PayGroup, PayPeriod, PayrollCalendar, PayrollCycle
from apps.payroll.services_pay_calendar import generate_periods, link_historical_cycles


def _make_calendar(**overrides):
    defaults = dict(code='TEST_CAL', name='Test Calendar', frequency=PayrollCalendar.FREQ_MONTHLY)
    defaults.update(overrides)
    return PayrollCalendar.objects.create(**defaults)


class MonthlyPeriodGenerationTests(TestCase):
    def test_generates_twelve_periods_spanning_month_boundary(self):
        calendar = _make_calendar(cycle_start_day=25, cycle_end_day=24, pay_day=30)
        periods = generate_periods(calendar, 2026)
        self.assertEqual(len(periods), 12)

        january = next(p for p in periods if p.period_start.month == 1)
        self.assertEqual(january.period_start, datetime.date(2026, 1, 25))
        self.assertEqual(january.period_end, datetime.date(2026, 2, 24))

    def test_pay_day_clamps_in_february(self):
        calendar = _make_calendar(cycle_start_day=25, cycle_end_day=24, pay_day=30, pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
        periods = generate_periods(calendar, 2026)
        # The January-starting period ends in February; pay_day=30 doesn't
        # exist in Feb 2026 (not a leap year) — must clamp to Feb 28.
        january = next(p for p in periods if p.period_start.month == 1)
        self.assertEqual(january.raw_pay_date, datetime.date(2026, 2, 28))

    def test_leap_year_clamps_to_29(self):
        calendar = _make_calendar(cycle_start_day=25, cycle_end_day=24, pay_day=30, pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
        periods = generate_periods(calendar, 2028)  # 2028 is a leap year
        january = next(p for p in periods if p.period_start.month == 1)
        self.assertEqual(january.raw_pay_date, datetime.date(2028, 2, 29))

    def test_financial_year_start_follows_april_boundary(self):
        calendar = _make_calendar(pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
        periods = generate_periods(calendar, 2026)
        march_period = next(p for p in periods if p.period_start.month == 3)
        april_period = next(p for p in periods if p.period_start.month == 4)
        self.assertEqual(march_period.financial_year_start, 2025)
        self.assertEqual(april_period.financial_year_start, 2026)

    def test_regenerating_is_idempotent(self):
        calendar = _make_calendar()
        generate_periods(calendar, 2026)
        count_after_first = PayPeriod.objects.filter(calendar=calendar).count()
        generate_periods(calendar, 2026)
        count_after_second = PayPeriod.objects.filter(calendar=calendar).count()
        self.assertEqual(count_after_first, count_after_second)
        self.assertEqual(count_after_first, 12)


class PayDateAdjustmentTests(TestCase):
    def test_weekend_pay_date_shifts_to_previous_working_day(self):
        # Construct a calendar whose pay_day lands on a known weekend.
        # 2026-05-30 is a Saturday.
        calendar = _make_calendar(
            code='WEEKEND_CAL', cycle_start_day=25, cycle_end_day=24, pay_day=30,
            pay_date_adjustment_rule=PayrollCalendar.ADJUST_PREVIOUS,
        )
        periods = generate_periods(calendar, 2026)
        april_period = next(p for p in periods if p.period_start.month == 4)
        self.assertEqual(april_period.raw_pay_date, datetime.date(2026, 5, 30))
        self.assertEqual(april_period.raw_pay_date.weekday(), 5)  # Saturday
        self.assertEqual(april_period.pay_date, datetime.date(2026, 5, 29))  # Friday
        self.assertNotEqual(april_period.pay_date, april_period.raw_pay_date)

    def test_weekend_pay_date_shifts_to_next_working_day(self):
        calendar = _make_calendar(
            code='WEEKEND_CAL_NEXT', cycle_start_day=25, cycle_end_day=24, pay_day=30,
            pay_date_adjustment_rule=PayrollCalendar.ADJUST_NEXT,
        )
        periods = generate_periods(calendar, 2026)
        april_period = next(p for p in periods if p.period_start.month == 4)
        self.assertEqual(april_period.pay_date, datetime.date(2026, 6, 1))  # Monday

    def test_holiday_pay_date_also_shifts(self):
        # Pick a pay_day that lands on a weekday, then mark it a company holiday.
        # 2026-06-30 is a Tuesday.
        Holiday.objects.create(name='Test Holiday', date=datetime.date(2026, 6, 30), branch=None)
        calendar = _make_calendar(
            code='HOLIDAY_CAL', cycle_start_day=25, cycle_end_day=24, pay_day=30,
            pay_date_adjustment_rule=PayrollCalendar.ADJUST_PREVIOUS,
        )
        periods = generate_periods(calendar, 2026)
        may_period = next(p for p in periods if p.period_start.month == 5)
        self.assertEqual(may_period.raw_pay_date, datetime.date(2026, 6, 30))
        self.assertEqual(may_period.pay_date, datetime.date(2026, 6, 29))  # shifted off the holiday

    def test_branch_scoped_holiday_does_not_affect_other_branches(self):
        state = State.objects.create(name='CalTestState', code='CTS')
        city = City.objects.create(name='CalTestCity', state=state)
        branch = Branch.objects.create(branch_code='CALTEST', branch_name='Cal Test Branch', address='x', state=state, city=city)
        Holiday.objects.create(name='Branch-only Holiday', date=datetime.date(2026, 6, 30), branch=branch)

        company_wide_calendar = _make_calendar(
            code='NO_BRANCH_CAL', cycle_start_day=25, cycle_end_day=24, pay_day=30,
            pay_date_adjustment_rule=PayrollCalendar.ADJUST_PREVIOUS, branch=None,
        )
        periods = generate_periods(company_wide_calendar, 2026)
        may_period = next(p for p in periods if p.period_start.month == 5)
        # 2026-06-30 is a Tuesday with no company-wide holiday — a
        # branch-only holiday on a DIFFERENT (None) calendar must not apply.
        self.assertEqual(may_period.pay_date, datetime.date(2026, 6, 30))


class FixedLengthPeriodTests(TestCase):
    def test_weekly_periods_are_seven_days_from_anchor(self):
        calendar = _make_calendar(
            code='WEEKLY_CAL', frequency=PayrollCalendar.FREQ_WEEKLY,
            anchor_date=datetime.date(2026, 1, 5), period_length_days=7,
            pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE,
        )
        periods = generate_periods(calendar, 2026)
        first = sorted(periods, key=lambda p: p.period_start)[0]
        self.assertEqual((first.period_end - first.period_start).days, 6)
        self.assertEqual(first.period_start.weekday(), datetime.date(2026, 1, 5).weekday())

    def test_fixed_length_calendar_requires_anchor_and_length(self):
        calendar = _make_calendar(code='BROKEN_WEEKLY', frequency=PayrollCalendar.FREQ_WEEKLY)
        with self.assertRaises(ValueError):
            generate_periods(calendar, 2026)


class LinkHistoricalCyclesTests(TestCase):
    def test_overlapping_cycle_gets_linked(self):
        calendar = _make_calendar(code='LINK_CAL', pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
        generate_periods(calendar, 2026)
        pay_group = PayGroup.objects.create(code='LINK_PG', name='Link PG', calendar=calendar, branch=None)

        role = make_role('link_cycle_role')
        user = make_user('link.cycle@example.com', role=role, password='TestPass123!')
        cycle = PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 4, 25), cycle_end=datetime.date(2026, 5, 24),
            pay_date=datetime.date(2026, 5, 30), created_by=user, branch=None,
        )

        summary = link_historical_cycles(pay_group)
        cycle.refresh_from_db()
        self.assertEqual(summary['linked'], 1)
        self.assertEqual(cycle.pay_group, pay_group)
        self.assertIsNotNone(cycle.pay_period)

    def test_non_overlapping_cycle_is_reported_unmatched(self):
        calendar = _make_calendar(code='LINK_CAL_GAP', pay_date_adjustment_rule=PayrollCalendar.ADJUST_NONE)
        # Deliberately don't generate any periods for this calendar.
        pay_group = PayGroup.objects.create(code='LINK_PG_GAP', name='Link PG Gap', calendar=calendar, branch=None)

        role = make_role('link_cycle_gap_role')
        user = make_user('link.cycle.gap@example.com', role=role, password='TestPass123!')
        PayrollCycle.objects.create(
            cycle_start=datetime.date(2026, 4, 25), cycle_end=datetime.date(2026, 5, 24),
            pay_date=datetime.date(2026, 5, 30), created_by=user, branch=None,
        )

        summary = link_historical_cycles(pay_group)
        self.assertEqual(summary['linked'], 0)
        self.assertEqual(len(summary['unmatched_cycle_ids']), 1)
