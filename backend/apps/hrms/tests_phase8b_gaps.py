"""Phase 8B gap-closure tests — travel advances, remaining expense policy rules, exit interview, attrition, clearance checklist, KB suggestions, satisfaction, merge, round-robin."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import (
    ChecklistTaskTemplate, ChecklistTemplate, Expense, ExpenseCategory, HelpDeskCategory,
    HRHelpRequest, KnowledgeBaseArticle, SeparationRequest, TravelRequest,
)
from apps.hrms.services_expense_gaps import (
    check_submission_deadline, compute_per_diem, compute_unit_based_amount,
    find_duplicate_lines, link_claim_to_trip, route_out_of_policy, travel_advance_balance,
)
from apps.hrms.services_expense_v2 import migrate_expense_to_claim
from apps.hrms.services_helpdesk_gaps import assign_round_robin, merge_tickets, record_satisfaction, suggest_articles
from apps.hrms.services_separation_gaps import (
    attrition_by_reason, clearance_complete, record_exit_interview, start_clearance_checklist,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class ExpensePolicyGapTests(TestCase):
    def test_unit_based_mileage_computed(self):
        category = ExpenseCategory.objects.create(code=_unique('CAT'), name='Mileage', is_unit_based=True, unit_rate=Decimal('12.00'))
        amount = compute_unit_based_amount(category, Decimal('50'))
        self.assertEqual(amount, Decimal('600.00'))

    def test_per_diem_by_city_tier(self):
        category = ExpenseCategory.objects.create(
            code=_unique('CAT'), name='Per Diem', per_diem_by_city_tier={'tier_1': '2000', 'tier_2': '1200'},
        )
        self.assertEqual(compute_per_diem(category, 'tier_1'), Decimal('2000'))
        with self.assertRaises(ValueError):
            compute_per_diem(category, 'tier_3')

    def test_submission_deadline(self):
        category = ExpenseCategory.objects.create(code=_unique('CAT'), name='Travel', submission_deadline_days=30)
        self.assertTrue(check_submission_deadline(category, datetime.date(2026, 4, 1), datetime.date(2026, 4, 20)))
        self.assertFalse(check_submission_deadline(category, datetime.date(2026, 4, 1), datetime.date(2026, 6, 1)))

    def test_duplicate_detection_finds_same_amount_date_merchant(self):
        employee = _make_employee()
        expense = Expense.objects.create(
            employee=employee, title='Lunch', category='meals', amount=Decimal('500'),
            expense_date=datetime.date(2026, 4, 1), description='',
        )
        claim = migrate_expense_to_claim(expense)
        line = claim.lines.first()
        line.merchant = 'Cafe X'
        line.save(update_fields=['merchant'])

        duplicates = find_duplicate_lines(employee, Decimal('500'), datetime.date(2026, 4, 1), 'Cafe X')
        self.assertEqual(duplicates.count(), 1)

    def test_out_of_policy_routing_returns_configured_behavior(self):
        category = ExpenseCategory.objects.create(
            code=_unique('CAT'), name='Travel', out_of_policy_behavior=ExpenseCategory.OUT_OF_POLICY_EXTRA_APPROVAL,
        )
        employee = _make_employee()
        expense = Expense.objects.create(
            employee=employee, title='Taxi', category='travel', amount=Decimal('5000'), expense_date=datetime.date(2026, 4, 1),
        )
        claim = migrate_expense_to_claim(expense)
        line = claim.lines.first()
        line.category = category
        line.policy_result = 'over_limit'
        line.save()

        self.assertEqual(route_out_of_policy(category, line), ExpenseCategory.OUT_OF_POLICY_EXTRA_APPROVAL)


class TravelAdvanceTests(TestCase):
    def test_advance_balance_reduces_as_claims_settle(self):
        employee = _make_employee()
        trip = TravelRequest.objects.create(employee=employee, purpose='Client visit', estimated_cost=Decimal('10000'), advance_requested=Decimal('8000'))
        expense = Expense.objects.create(
            employee=employee, title='Hotel', category='travel', amount=Decimal('3000'), expense_date=datetime.date(2026, 4, 1),
        )
        claim = migrate_expense_to_claim(expense)
        link_claim_to_trip(claim, trip)

        balance = travel_advance_balance(trip)
        self.assertEqual(balance, Decimal('5000'))


class ExitInterviewAndAttritionTests(TestCase):
    def test_record_exit_interview_is_confidential_by_default(self):
        employee = _make_employee()
        creator = _make_employee()
        request = SeparationRequest.objects.create(
            employee=employee, separation_type='resignation', request_date=datetime.date(2026, 4, 1),
            proposed_last_working_day=datetime.date(2026, 5, 1), created_by=creator,
        )
        interview = record_exit_interview(request, 'better_career_opportunity', {'q1': 'Growth.'}, creator)
        self.assertTrue(interview.is_confidential)

    def test_attrition_by_reason_counts(self):
        employee_a = _make_employee()
        employee_b = _make_employee()
        creator = _make_employee()
        SeparationRequest.objects.create(
            employee=employee_a, separation_type='resignation', reason='compensation',
            request_date=datetime.date(2026, 4, 1), proposed_last_working_day=datetime.date(2026, 5, 1), created_by=creator,
        )
        SeparationRequest.objects.create(
            employee=employee_b, separation_type='resignation', reason='compensation',
            request_date=datetime.date(2026, 4, 1), proposed_last_working_day=datetime.date(2026, 5, 1), created_by=creator,
        )
        counts = attrition_by_reason()
        self.assertEqual(counts.get('compensation'), 2)


class ClearanceChecklistTests(TestCase):
    def test_clearance_completes_once_every_task_done(self):
        employee = _make_employee()
        creator = _make_employee()
        request = SeparationRequest.objects.create(
            employee=employee, separation_type='resignation', request_date=datetime.date(2026, 4, 1),
            proposed_last_working_day=datetime.date(2026, 5, 1), created_by=creator,
        )
        template = ChecklistTemplate.objects.create(code=_unique('CLR'), name='Clearance', checklist_type=ChecklistTemplate.TYPE_OFFBOARDING)
        ChecklistTaskTemplate.objects.create(template=template, title='Return assets', due_offset_days=0, order=0)

        link = start_clearance_checklist(request, template)
        self.assertFalse(clearance_complete(request))

        from apps.hrms.services_checklist import complete_task
        task = link.checklist_instance.tasks.first()
        complete_task(task, creator)
        self.assertTrue(clearance_complete(request))


class HelpDeskGapTests(TestCase):
    def test_suggest_articles_keyword_match(self):
        category = HelpDeskCategory.objects.create(code=_unique('CAT'), name='Payroll')
        KnowledgeBaseArticle.objects.create(category=category, title='How payslips are calculated', body='...')
        KnowledgeBaseArticle.objects.create(category=category, title='Leave policy overview', body='...')
        results = suggest_articles('why is my payslip wrong')
        self.assertEqual(len(results), 1)
        self.assertIn('payslip', results[0].title.lower())

    def test_satisfaction_requires_resolved_ticket(self):
        employee = _make_employee()
        ticket = HRHelpRequest.objects.create(submitted_by=employee, topic='other', message='x', status='open')
        with self.assertRaises(ValueError):
            record_satisfaction(ticket, 5)

        ticket.status = 'resolved'
        ticket.save()
        rating = record_satisfaction(ticket, 4, 'Quick response.')
        self.assertEqual(rating.rating, 4)

    def test_merge_moves_messages_to_primary_thread(self):
        employee = _make_employee()
        primary = HRHelpRequest.objects.create(submitted_by=employee, topic='other', message='Issue A')
        duplicate = HRHelpRequest.objects.create(submitted_by=employee, topic='other', message='Issue A again')
        merger = _make_employee()

        record = merge_tickets(primary, duplicate, merger)
        duplicate.refresh_from_db()
        self.assertEqual(duplicate.status, 'resolved')
        self.assertEqual(record.primary_ticket_id, primary.id)

    def test_round_robin_cycles_through_agents(self):
        category = HelpDeskCategory.objects.create(code=_unique('CAT'), name='General')
        agents = ['agent_a', 'agent_b', 'agent_c']
        assigned = [assign_round_robin(category, agents) for _ in range(4)]
        self.assertEqual(assigned, ['agent_a', 'agent_b', 'agent_c', 'agent_a'])
