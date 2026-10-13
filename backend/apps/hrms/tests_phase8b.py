"""Phase 8B Tasks A/B/C/H — expenses, separation, help desk, flags."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import CATEGORY_MEALS, CATEGORY_TRAVEL, STATUS_APPROVED, Expense, ExpenseCategory, HRHelpRequest
from apps.hrms.services_expense_v2 import evaluate_policy, migrate_expense_to_claim, seed_expense_categories
from apps.hrms.services_helpdesk_v2 import check_sla_breach, migrate_ticket_to_thread, reopen_ticket
from apps.hrms.services_separation_v2 import create_alumni_record, is_rehire_eligible
from apps.hrms.services_v2_flags import ModuleV2GateError, enable_expenses_v2, enable_helpdesk_v2

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class ExpenseMigrationTests(TestCase):
    def test_seed_reproduces_category_choices_exactly(self):
        categories = seed_expense_categories()
        self.assertEqual(set(categories.keys()), {c for c, _ in Expense.CATEGORY_CHOICES})

    def test_migrate_expense_creates_single_line_claim(self):
        employee = _make_employee()
        expense = Expense.objects.create(
            employee=employee, title='Taxi', category=CATEGORY_TRAVEL,
            amount=Decimal('500.00'), expense_date=datetime.date(2026, 4, 1), status=STATUS_APPROVED,
        )
        claim = migrate_expense_to_claim(expense)
        self.assertEqual(claim.lines.count(), 1)
        line = claim.lines.first()
        self.assertEqual(line.base_amount, Decimal('500.00'))
        self.assertEqual(claim.status, 'approved')

    def test_migration_is_idempotent(self):
        employee = _make_employee()
        expense = Expense.objects.create(
            employee=employee, title='Taxi', category=CATEGORY_TRAVEL,
            amount=Decimal('500.00'), expense_date=datetime.date(2026, 4, 1),
        )
        first = migrate_expense_to_claim(expense)
        second = migrate_expense_to_claim(expense)
        self.assertEqual(first.id, second.id)

    def test_gate_blocks_with_unmigrated_expenses(self):
        employee = _make_employee()
        Expense.objects.create(
            employee=employee, title='Taxi', category=CATEGORY_TRAVEL,
            amount=Decimal('500.00'), expense_date=datetime.date(2026, 4, 1),
        )
        with self.assertRaises(ModuleV2GateError):
            enable_expenses_v2()


class ExpensePolicyTests(TestCase):
    def test_period_limit_blocks_over_total(self):
        category = ExpenseCategory.objects.create(code=_unique('CAT'), name='Meals', period_limit_amount=Decimal('1000'))
        employee = _make_employee()
        expense = Expense.objects.create(
            employee=employee, title='Lunch', category=CATEGORY_MEALS,
            amount=Decimal('800'), expense_date=datetime.date(2026, 4, 5),
        )
        claim = migrate_expense_to_claim(expense)
        claim.lines.update(category=category)

        result, explanation = evaluate_policy(
            category, employee, Decimal('500'), datetime.date(2026, 4, 1), datetime.date(2026, 4, 30),
        )
        self.assertEqual(result, 'over_limit')
        self.assertIn('1300', explanation)

    def test_within_limit_passes(self):
        category = ExpenseCategory.objects.create(code=_unique('CAT'), name='Meals', period_limit_amount=Decimal('1000'))
        employee = _make_employee()
        result, _ = evaluate_policy(category, employee, Decimal('500'), datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        self.assertEqual(result, 'within_policy')

    def test_receipt_threshold_flags_over(self):
        category = ExpenseCategory.objects.create(code=_unique('CAT'), name='Travel', requires_receipt_above_amount=Decimal('100'))
        employee = _make_employee()
        result, explanation = evaluate_policy(category, employee, Decimal('150'), datetime.date(2026, 4, 1), datetime.date(2026, 4, 30))
        self.assertEqual(result, 'over_limit')
        self.assertIn('receipt', explanation.lower())


class SeparationV2Tests(TestCase):
    def test_rehire_eligible_defaults_true_with_no_record(self):
        employee = _make_employee()
        self.assertTrue(is_rehire_eligible(employee.email))

    def test_alumni_record_reflects_ineligibility(self):
        from apps.hrms.models import SeparationRequest
        employee = _make_employee()
        creator = _make_employee()
        request = SeparationRequest.objects.create(
            employee=employee, separation_type='termination', request_date=datetime.date(2026, 4, 1),
            proposed_last_working_day=datetime.date(2026, 5, 1), created_by=creator,
        )
        create_alumni_record(request, datetime.date(2026, 5, 1), rehire_eligible=False, rehire_note='Policy violation.')
        self.assertFalse(is_rehire_eligible(employee.email))


class HelpDeskV2Tests(TestCase):
    def test_migrate_ticket_creates_message_from_legacy_response(self):
        employee = _make_employee()
        assignee = _make_employee()
        ticket = HRHelpRequest.objects.create(
            submitted_by=employee, topic='payroll_query', message='Why is my payslip wrong?',
            status='resolved', assigned_to=assignee, response='Fixed in the next cycle.',
            resolved_at=datetime.datetime.now(),
        )
        thread = migrate_ticket_to_thread(ticket)
        self.assertEqual(thread.messages.count(), 1)
        self.assertTrue(thread.messages.first().is_legacy_migrated)

    def test_reopen_within_window_succeeds(self):
        from django.utils import timezone
        employee = _make_employee()
        ticket = HRHelpRequest.objects.create(
            submitted_by=employee, topic='leave_query', message='x',
            status='resolved', resolved_at=timezone.now(),
        )
        reopened = reopen_ticket(ticket, within_days=7)
        self.assertTrue(reopened)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'in_progress')

    def test_reopen_outside_window_fails(self):
        from django.utils import timezone
        employee = _make_employee()
        ticket = HRHelpRequest.objects.create(
            submitted_by=employee, topic='leave_query', message='x',
            status='resolved', resolved_at=timezone.now() - datetime.timedelta(days=30),
        )
        reopened = reopen_ticket(ticket, within_days=7)
        self.assertFalse(reopened)

    def test_gate_blocks_with_unmigrated_tickets(self):
        employee = _make_employee()
        HRHelpRequest.objects.create(submitted_by=employee, topic='other', message='x')
        with self.assertRaises(ModuleV2GateError):
            enable_helpdesk_v2()
