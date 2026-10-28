"""UAT-043: the read-only leave policy consistency report, and the carry-forward job logging a real year transition."""
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.hrms.models import CarryForwardLog, LeaveBalance, LeavePolicy
from apps.hrms.services_leave_policy_report import find_mismatches


def _policy(**overrides):
    base = dict(
        leave_type='x', annual_days=12, can_carry_forward=False, max_carry_forward_days=0, maximum_consecutive_days=0,
        minimum_notice_period=0, attachment_required=False, applicable_gender='all', allow_probation_leave=False, policy_note='',
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class MismatchRuleTests(SimpleTestCase):
    def test_the_reported_earned_leave_case(self):
        policy = _policy(policy_note='Min 3 days notice. Carry-forward up to 30 days.', can_carry_forward=False)
        problems = find_mismatches(policy)
        self.assertTrue(any('carry-forward is switched off' in problem for problem in problems))
        self.assertTrue(any('advance notice' in problem for problem in problems))

    def test_the_reported_maternity_case(self):
        problems = find_mismatches(_policy(annual_days=90, policy_note='Up to 180 days per Maternity Benefit Act.'))
        self.assertEqual(len(problems), 1)
        self.assertIn('up to 180 days', problems[0])

    def test_the_reported_casual_case(self):
        problems = find_mismatches(_policy(policy_note='Max 3 consecutive days. Apply 1 day in advance.'))
        self.assertTrue(any('3 consecutive days' in problem for problem in problems))

    def test_a_consistent_policy_raises_nothing(self):
        policy = _policy(can_carry_forward=True, max_carry_forward_days=30, policy_note='Carry-forward up to 30 days.')
        self.assertEqual(find_mismatches(policy), [])

    def test_a_blank_note_is_never_flagged(self):
        self.assertEqual(find_mismatches(_policy(policy_note='')), [])


class ReportCommandTests(TestCase):
    def test_is_read_only_and_lists_flags(self):
        policy, _ = LeavePolicy.objects.update_or_create(
            leave_type='earned', defaults={'annual_days': 15, 'can_carry_forward': False, 'policy_note': 'Carry-forward up to 30 days.', 'is_active': True},
        )
        out = StringIO()
        call_command('report_leave_policy_consistency', stdout=out)
        self.assertIn('earned:', out.getvalue())
        self.assertIn('CHECK:', out.getvalue())
        self.assertIn('Nothing was changed', out.getvalue())
        policy.refresh_from_db()
        self.assertFalse(policy.can_carry_forward)


class CarryForwardLoggingTests(TestCase):
    def test_empty_expiry_sweep_writes_no_log_row(self):
        from apps.hrms.tasks import expire_unused_carry_forward
        before = CarryForwardLog.objects.count()
        result = expire_unused_carry_forward.run()
        self.assertEqual((result['processed'], result['skipped'], result['failed']), (0, 0, 0))
        self.assertEqual(CarryForwardLog.objects.count(), before)  # no more "2026 -> 2026, 0 processed" every night

    def test_year_end_job_logs_the_real_transition_once_and_never_double_credits(self):
        from datetime import date
        from unittest import mock
        from apps.accounts.factories import make_user
        from apps.hrms.tasks import reset_annual_leave_balances

        LeavePolicy.objects.update_or_create(
            leave_type='earned', defaults={'annual_days': 15, 'can_carry_forward': True, 'max_carry_forward_days': 30,
                                           'carry_forward_type': 'limited', 'is_active': True, 'minimum_service_period': 0, 'applicable_gender': 'all'},
        )
        employee = make_user('yearend@test.com', employee_id='EMPYE001')
        LeaveBalance.objects.create(employee=employee, leave_type='earned', year=2030, total_days=15, used_days=5)

        with mock.patch('apps.hrms.tasks.timezone.localdate', return_value=date(2031, 1, 1)):
            first = reset_annual_leave_balances.run()
            again = reset_annual_leave_balances.run()

        self.assertEqual((first['from_year'], first['to_year']), (2030, 2031))
        balance = LeaveBalance.objects.get(employee=employee, leave_type='earned', year=2031)
        self.assertEqual(float(balance.carried_forward), 10.0)       # 15 - 5 unused carried over
        self.assertEqual(float(balance.total_days), 25.0)             # 15 new + 10 carried
        self.assertEqual(again['created'], 0)                         # the re-run credits nothing more
        logs = CarryForwardLog.objects.filter(process_mode='year_end', from_year=2030, to_year=2031)
        self.assertEqual(logs.count(), 1)                             # and logs the transition once
        self.assertIn('carried forward from 2030', logs.first().notes)


class EmploymentTypeMasterTests(TestCase):
    """One master list: policies store the canonical employment types, and existing values can be remapped after review."""

    def test_remap_dry_run_shows_the_mapping_and_apply_writes_it(self):
        policy, _ = LeavePolicy.objects.update_or_create(
            leave_type='sick', defaults={'is_active': True, 'applicable_employment_types': ['Full-time', 'Part-time', 'Intern', 'Mystery']},
        )
        out = StringIO()
        call_command('remap_policy_employment_types', stdout=out)
        self.assertIn("['Full-time', 'Part-time', 'Intern', 'Mystery'] -> ['Permanent', 'Part-Time', 'Intern', 'Mystery']", out.getvalue())
        self.assertIn('"Mystery" has no match', out.getvalue())
        policy.refresh_from_db()
        self.assertEqual(policy.applicable_employment_types, ['Full-time', 'Part-time', 'Intern', 'Mystery'])  # dry run: untouched
        call_command('remap_policy_employment_types', apply=True, stdout=StringIO())
        policy.refresh_from_db()
        self.assertEqual(policy.applicable_employment_types, ['Permanent', 'Part-Time', 'Intern', 'Mystery'])

    def test_saving_a_policy_normalises_what_was_typed(self):
        from apps.hrms.serializers import LeavePolicyUpdateSerializer
        serializer = LeavePolicyUpdateSerializer(data={'applicable_employment_types': ['Full-time', 'permanent', 'Part time']}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['applicable_employment_types'], ['Permanent', 'Part-Time'])

    def test_an_unknown_type_is_refused_with_the_valid_list(self):
        from apps.hrms.serializers import LeavePolicyUpdateSerializer
        serializer = LeavePolicyUpdateSerializer(data={'applicable_employment_types': ['Astronaut']}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('Permanent', str(serializer.errors['applicable_employment_types']))
