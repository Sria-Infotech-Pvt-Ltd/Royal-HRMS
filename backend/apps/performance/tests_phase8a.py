"""Phase 8A Task C — review templates, calibration, PIP, v2 gate."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.performance.models import CalibrationSession, PerformanceImprovementPlan, ReviewCycle, ReviewTemplate
from apps.performance.services_performance_v2 import (
    check_calibration_distribution, close_pip, lock_calibration_session,
    record_calibration_adjustment, seed_standard_review_template, validate_section_weights,
)
from apps.recruitment.services_v2_flags import V2GateError, enable_performance_v2

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class StandardReviewTemplateTests(TestCase):
    def test_seed_is_idempotent_and_weights_valid(self):
        first = seed_standard_review_template()
        second = seed_standard_review_template()
        self.assertEqual(first.id, second.id)
        validate_section_weights(first)  # must not raise

    def test_invalid_weights_rejected(self):
        from apps.performance.services_performance_v2 import seed_standard_rating_scale
        scale = seed_standard_rating_scale()
        bad_template = ReviewTemplate.objects.create(
            code=_unique('BAD'), name='Bad', rating_scale=scale,
            sections=[{'key': 'a', 'weight': 50}],
        )
        with self.assertRaises(ValueError):
            validate_section_weights(bad_template)


class CalibrationTests(TestCase):
    def test_distribution_warning_fires_when_over_target(self):
        cycle = ReviewCycle.objects.create(
            name=_unique('Cycle'), period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 3, 31),
            self_review_due=datetime.date(2026, 2, 1), manager_review_due=datetime.date(2026, 2, 15),
        )
        session = CalibrationSession.objects.create(
            cycle=cycle, name='Q1', distribution_guideline={'5': 10, '4': 20, '3': 40, '2': 20, '1': 10},
        )
        warnings = check_calibration_distribution(session, {'5': 25, '4': 20, '3': 35, '2': 15, '1': 5})
        self.assertIn('5', warnings)
        self.assertEqual(warnings['5']['over_by'], 15)
        self.assertNotIn('4', warnings)

    def test_adjustment_requires_reason_and_blocked_once_locked(self):
        cycle = ReviewCycle.objects.create(
            name=_unique('Cycle'), period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 3, 31),
            self_review_due=datetime.date(2026, 2, 1), manager_review_due=datetime.date(2026, 2, 15),
        )
        session = CalibrationSession.objects.create(cycle=cycle, name='Q1')
        employee = _make_employee()
        manager = _make_employee()
        from apps.performance.models import PerformanceReview
        review = PerformanceReview.objects.create(employee=employee, cycle=cycle, manager=manager)

        with self.assertRaises(ValueError):
            record_calibration_adjustment(session, review, '3', '4', '', manager)

        adjustment = record_calibration_adjustment(session, review, '3', '4', 'Strong peer feedback.', manager)
        self.assertEqual(adjustment.adjusted_rating, '4')

        lock_calibration_session(session)
        with self.assertRaises(ValueError):
            record_calibration_adjustment(session, review, '3', '4', 'Too late.', manager)


class PipTests(TestCase):
    def test_close_pip_sets_outcome(self):
        employee = _make_employee()
        pip = PerformanceImprovementPlan.objects.create(
            employee=employee, objectives='Improve X', start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 1),
        )
        close_pip(pip, PerformanceImprovementPlan.STATUS_COMPLETED, 'Met all objectives.')
        pip.refresh_from_db()
        self.assertEqual(pip.status, PerformanceImprovementPlan.STATUS_COMPLETED)

    def test_close_pip_rejects_unknown_outcome(self):
        employee = _make_employee()
        pip = PerformanceImprovementPlan.objects.create(
            employee=employee, objectives='Improve X', start_date=datetime.date(2026, 1, 1), end_date=datetime.date(2026, 3, 1),
        )
        with self.assertRaises(ValueError):
            close_pip(pip, 'not_a_real_status', 'x')


class PerformanceV2GateTests(TestCase):
    def test_gate_requires_standard_template_seeded(self):
        with self.assertRaises(V2GateError):
            enable_performance_v2()

    def test_gate_passes_once_seeded(self):
        seed_standard_review_template()
        entitlement = enable_performance_v2()
        self.assertTrue(entitlement.is_enabled)
