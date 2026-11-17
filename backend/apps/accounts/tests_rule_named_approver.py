"""An approval rule can name one person as its L1 or L2 approver (no database needed)."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts.models import ApprovalWorkflowRule, User
from apps.accounts.serializers import ApprovalWorkflowRuleUpdateSerializer
from apps.accounts.services_approval import resolve_rule_approver, rule_stage_label
from apps.accounts.services_approver_assignment import WORKFLOW_APPROVE_PERMISSION, rule_person_refusal
from apps.accounts.views.approval_workflow import _named_approvers

PERSON = 'person'
RELATIONSHIP_LABELS = {'reporting_manager': 'Reporting manager', 'hr': 'HR partner'}


def user(pk, *, active=True, name='Kabir Rao', employee_id='E1'):
    return SimpleNamespace(pk=pk, is_active=active, full_name=name, email=f'{pk}@example.com', employee_id=employee_id)


def rule(l1_kind='reporting_manager', l2_kind='hr', l1_user=None, l2_user=None):
    return SimpleNamespace(
        l1_approver_kind=l1_kind, l2_approver_kind=l2_kind, l1_approver_user_id=l1_user, l2_approver_user_id=l2_user,
        get_l1_approver_kind_display=lambda: RELATIONSHIP_LABELS.get(l1_kind, ''),
        get_l2_approver_kind_display=lambda: RELATIONSHIP_LABELS.get(l2_kind, ''),
    )


def finds(person):
    """Make User.objects.filter(...).first() return `person`."""
    manager = mock.MagicMock()
    manager.filter.return_value.first.return_value = person
    return mock.patch.object(User, 'objects', manager)


class SerializerTests(SimpleTestCase):
    base = {'workflow_type': 'leave', 'l1_approver_kind': 'reporting_manager'}

    def test_a_person_kind_needs_a_person(self):
        serializer = ApprovalWorkflowRuleUpdateSerializer(data={**self.base, 'l1_approver_kind': PERSON})
        self.assertFalse(serializer.is_valid())
        self.assertIn('l1_approver_user', serializer.errors)

    def test_a_person_kind_with_a_person_is_valid(self):
        serializer = ApprovalWorkflowRuleUpdateSerializer(data={
            **self.base, 'l2_approver_kind': PERSON, 'l2_approver_user': '11111111-1111-1111-1111-111111111111',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_the_existing_kinds_need_no_person(self):
        serializer = ApprovalWorkflowRuleUpdateSerializer(data={**self.base, 'l2_approver_kind': 'hr'})
        self.assertTrue(serializer.is_valid(), serializer.errors)


class ResolveRuleApproverTests(SimpleTestCase):
    employee = user('emp', name='Employee', employee_id='E9')

    def test_the_named_person_approves(self):
        kabir = user('kabir')
        with finds(kabir):
            self.assertIs(resolve_rule_approver(rule(l1_kind=PERSON, l1_user='kabir'), 'l1', self.employee), kabir)
            self.assertIs(resolve_rule_approver(rule(l2_kind=PERSON, l2_user='kabir'), 'l2', self.employee), kabir)

    def test_an_inactive_or_missing_named_person_resolves_to_nobody(self):
        with finds(user('kabir', active=False)):
            self.assertIsNone(resolve_rule_approver(rule(l1_kind=PERSON, l1_user='kabir'), 'l1', self.employee))
        with finds(None):
            self.assertIsNone(resolve_rule_approver(rule(l2_kind=PERSON, l2_user='gone'), 'l2', self.employee))

    def test_no_person_chosen_resolves_to_nobody(self):
        self.assertIsNone(resolve_rule_approver(rule(l1_kind=PERSON, l1_user=None), 'l1', self.employee))

    def test_a_named_l1_who_is_the_requester_falls_back_to_their_reporting_manager(self):
        manager = user('manager')
        with finds(self.employee), mock.patch('apps.accounts.services_approval.resolve_approver', return_value=manager) as fallback:
            self.assertIs(resolve_rule_approver(rule(l1_kind=PERSON, l1_user='emp'), 'l1', self.employee), manager)
            fallback.assert_called_once_with('reporting_manager', self.employee)

    def test_a_named_l2_who_is_the_requester_resolves_to_nobody_so_the_hr_fallback_runs(self):
        with finds(self.employee):
            self.assertIsNone(resolve_rule_approver(rule(l2_kind=PERSON, l2_user='emp'), 'l2', self.employee))

    def test_the_relationship_kinds_still_resolve_by_relationship(self):
        with mock.patch('apps.accounts.services_approval.resolve_approver', return_value='resolved') as resolver:
            self.assertEqual(resolve_rule_approver(rule(), 'l1', self.employee), 'resolved')
            self.assertEqual(resolve_rule_approver(rule(), 'l2', self.employee), 'resolved')
        self.assertEqual([call.args[0] for call in resolver.call_args_list], ['reporting_manager', 'hr'])


class LabelTests(SimpleTestCase):
    def test_a_named_person_is_labelled_with_their_name(self):
        with finds(user('kabir', name='Kabir Rao')):
            self.assertEqual(rule_stage_label(rule(l1_kind=PERSON, l1_user='kabir'), 'l1'), 'Kabir Rao')

    def test_a_person_kind_without_a_person_says_so(self):
        self.assertEqual(rule_stage_label(rule(l1_kind=PERSON), 'l1'), 'A specific person (not chosen)')

    def test_the_relationship_kinds_keep_their_labels(self):
        self.assertEqual(rule_stage_label(rule(), 'l1'), 'Reporting manager')
        self.assertEqual(rule_stage_label(rule(), 'l2'), 'HR partner')


class WhoMayBeNamedTests(SimpleTestCase):
    def test_each_workflow_uses_its_own_approve_capability(self):
        self.assertEqual(WORKFLOW_APPROVE_PERMISSION['leave'], 'leave.approve')
        self.assertEqual(WORKFLOW_APPROVE_PERMISSION['expense'], 'expenses.approve')
        asked = []
        with mock.patch('apps.accounts.services_approver_assignment.has_perm', side_effect=lambda person, code: asked.append(code) or True):
            self.assertIsNone(rule_person_refusal(user('kabir'), 'expense'))
        self.assertEqual(asked, ['expenses.approve'])

    def test_inactive_people_and_people_without_a_record_or_the_capability_are_refused(self):
        self.assertIn('inactive', rule_person_refusal(user('a', active=False), 'leave'))
        self.assertIn('no employee record', rule_person_refusal(user('a', employee_id=''), 'leave'))
        with mock.patch('apps.accounts.services_approver_assignment.has_perm', return_value=False):
            self.assertIn('leave.approve', rule_person_refusal(user('a'), 'leave'))

    def test_saving_a_rule_refuses_someone_who_may_not_approve_it(self):
        data = {'workflow_type': 'expense', 'l1_approver_kind': PERSON, 'l1_approver_user': 'kabir', 'l2_approver_kind': ''}
        with finds(user('kabir')), mock.patch('apps.accounts.services_approver_assignment.has_perm', return_value=False):
            named, refusal = _named_approvers(data)
        self.assertEqual(named, {})
        self.assertIn('expenses.approve', refusal)

    def test_saving_a_rule_with_an_unknown_person_is_refused(self):
        data = {'workflow_type': 'leave', 'l1_approver_kind': PERSON, 'l1_approver_user': 'nobody'}
        with finds(None):
            self.assertEqual(_named_approvers(data), ({}, 'The selected person was not found.'))

    def test_saving_a_rule_with_a_valid_person_returns_them_and_ignores_other_levels(self):
        kabir = user('kabir')
        data = {'workflow_type': 'leave', 'l1_approver_kind': PERSON, 'l1_approver_user': 'kabir', 'l2_approver_kind': 'hr', 'l2_approver_user': 'ignored'}
        with finds(kabir), mock.patch('apps.accounts.services_approver_assignment.has_perm', return_value=True):
            named, refusal = _named_approvers(data)
        self.assertEqual((named, refusal), ({'l1': kabir}, ''))

    def test_the_new_kind_is_one_of_the_rule_choices(self):
        self.assertIn(PERSON, [value for value, _label in ApprovalWorkflowRule.APPROVER_CHOICES])
