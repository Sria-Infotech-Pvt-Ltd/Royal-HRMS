"""Phase 3B Task A+B — workflow engine tests, built against the
"Vehicle Allocation" custom entity from Phase 2 (Acceptance Criterion 2:
a 2-step approval configured entirely by an admin, no code change)."""
from __future__ import annotations

import datetime

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_workflow as wf
from apps.platform_core import services_workflow_definitions as wf_defs
from apps.platform_core import services_custom_objects as custom_objects
from apps.platform_core.models import (
    EntityDefinition, FieldDefinition, WorkflowApproverOverride, WorkflowDefinition,
    WorkflowHistory, WorkflowInstance, WorkflowStep, WorkflowTask,
)


class WorkflowEngineTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.entity = EntityDefinition.objects.create(
            code='vehicle_allocation', label='Vehicle Allocation', kind=EntityDefinition.KIND_CUSTOM,
            attributes_column='data',
        )
        FieldDefinition.objects.create(
            entity=self.entity, code='vehicle_number', label='Vehicle Number', data_type='text',
            status=FieldDefinition.STATUS_PUBLISHED, required=True,
        )
        custom_objects.publish_entity(self.entity)

        self.role = make_role('wf_role')
        self.requester = make_user('wf-requester@test.com', role=self.role)
        self.manager = make_user('wf-manager@test.com', role=self.role)
        self.finance = make_user('wf-finance@test.com', role=self.role)

        self.record = custom_objects.create_record(self.entity, {'vehicle_number': 'TS09AB1234'}, actor=self.requester)
        self.record.employee = self.requester  # resolvers read record.employee
        self.record.save()

    def _seat_held_by(self, user):
        import datetime as _dt
        from apps.accounts.models import OrgUnit, Placement, Position
        unit, _ = OrgUnit.objects.get_or_create(name='Workflow Test Unit')
        seat = Position.objects.create(org_unit=unit, title='Finance Approver', grade='L2')
        Placement.objects.create(position=seat, employee=user, effective_from=_dt.date(2020, 1, 1))
        return seat

    def _make_definition(self, *, priority=0):
        definition = WorkflowDefinition.objects.create(
            code='vehicle_allocation_approval', name='Vehicle Allocation Approval',
            entity=self.entity, priority=priority,
            status_field_code='approval_status',
            status_mapping={'approved': 'APPROVED', 'rejected': 'REJECTED'},
        )
        step1 = WorkflowStep.objects.create(
            definition=definition, code='manager_approval', label='Manager approval', order=0,
            step_type=WorkflowStep.TYPE_APPROVAL, resolver='specific_user',
            resolver_params={'user_id': self.manager.pk}, quorum=WorkflowStep.QUORUM_ANY_ONE,
        )
        step2 = WorkflowStep.objects.create(
            definition=definition, code='finance_approval', label='Finance approval', order=1,
            step_type=WorkflowStep.TYPE_APPROVAL, resolver='specific_user',
            resolver_params={'user_id': self.finance.pk}, quorum=WorkflowStep.QUORUM_ANY_ONE,
        )
        wf_defs.publish(definition)
        return definition, step1, step2


class TwoStepApprovalTests(WorkflowEngineTestBase):
    """Acceptance Criterion 2 — the full happy path end to end."""

    def test_start_creates_instance_and_first_task(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        self.assertEqual(instance.status, WorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(instance.current_step_codes, ['manager_approval'])
        task = WorkflowTask.objects.get(instance=instance)
        self.assertEqual(task.assignee, self.manager)

    def test_approving_both_steps_completes_the_instance(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task1.pk, user=self.manager, action='approve', remarks='looks good')
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_IN_PROGRESS)
        self.assertEqual(instance.current_step_codes, ['finance_approval'])

        task2 = WorkflowTask.objects.get(instance=instance, step__code='finance_approval')
        wf.act(task2.pk, user=self.finance, action='approve', remarks='ok')
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_APPROVED)
        self.assertIsNotNone(instance.completed_at)

    def test_approval_syncs_record_status_mapping(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task1.pk, user=self.manager, action='approve')
        task2 = WorkflowTask.objects.get(instance=instance, step__code='finance_approval')
        wf.act(task2.pk, user=self.finance, action='approve')
        self.record.refresh_from_db()
        self.assertEqual(self.record.data.get('approval_status'), 'APPROVED')

    def test_reject_at_second_step_completes_as_rejected(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task1.pk, user=self.manager, action='approve')
        task2 = WorkflowTask.objects.get(instance=instance, step__code='finance_approval')
        wf.act(task2.pk, user=self.finance, action='reject', remarks='too expensive')
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_REJECTED)
        self.record.refresh_from_db()
        self.assertEqual(self.record.data.get('approval_status'), 'REJECTED')

    def test_full_history_is_recorded(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task1.pk, user=self.manager, action='approve')
        task2 = WorkflowTask.objects.get(instance=instance, step__code='finance_approval')
        wf.act(task2.pk, user=self.finance, action='approve')
        actions = list(WorkflowHistory.objects.filter(instance=instance).values_list('action', flat=True))
        self.assertIn(WorkflowHistory.ACTION_STARTED, actions)
        self.assertIn(WorkflowHistory.ACTION_APPROVED, actions)
        self.assertIn(WorkflowHistory.ACTION_COMPLETED, actions)


class SendBackAndWithdrawTests(WorkflowEngineTestBase):
    def test_send_back_returns_to_previous_step(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task1.pk, user=self.manager, action='approve')
        task2 = WorkflowTask.objects.get(instance=instance, step__code='finance_approval')
        wf.act(task2.pk, user=self.finance, action='send_back', remarks='need more info')
        instance.refresh_from_db()
        self.assertEqual(instance.current_step_codes, ['manager_approval'])
        new_manager_task = WorkflowTask.objects.filter(instance=instance, step__code='manager_approval', status=WorkflowTask.STATUS_PENDING).first()
        self.assertIsNotNone(new_manager_task)

    def test_requester_can_withdraw_while_in_progress(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        wf.withdraw(instance.pk, user=self.requester)
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_WITHDRAWN)

    def test_non_requester_cannot_withdraw(self):
        self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        with self.assertRaises(wf.WorkflowError):
            wf.withdraw(instance.pk, user=self.manager)


class SeparationOfDutiesTests(WorkflowEngineTestBase):
    def test_requester_is_never_assigned_their_own_approval(self):
        definition = WorkflowDefinition.objects.create(
            code='self_requester_test', name='Self', entity=self.entity, priority=1,
        )
        WorkflowStep.objects.create(
            definition=definition, code='step1', label='Step 1', order=0,
            step_type=WorkflowStep.TYPE_APPROVAL, resolver='specific_user',
            resolver_params={'user_id': self.requester.pk},  # misconfigured: approver == requester
            no_approver_action=WorkflowStep.NO_APPROVER_BLOCK,
        )
        wf_defs.publish(definition)
        instance = wf.start(self.record, requester=self.requester)
        # skip_if_approver_is_requester filters the requester out at
        # resolution time, so no approver remains -> BLOCK -> error status,
        # never a task silently assigned back to the requester.
        self.assertEqual(instance.status, WorkflowInstance.STATUS_ERROR)
        self.assertFalse(WorkflowTask.objects.filter(instance=instance, assignee=self.requester).exists())

    def test_same_approver_blocked_from_second_step_by_default(self):
        definition = WorkflowDefinition.objects.create(code='dual_step', name='Dual', entity=self.entity, priority=2)
        WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
        )
        WorkflowStep.objects.create(
            definition=definition, code='s2', label='S2', order=1, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
        )
        wf_defs.publish(definition)
        instance = wf.start(self.record, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance, step__code='s1')
        wf.act(task1.pk, user=self.manager, action='approve')
        task2 = WorkflowTask.objects.get(instance=instance, step__code='s2')
        with self.assertRaises(wf.WorkflowError):
            wf.act(task2.pk, user=self.manager, action='approve')


class QuorumAndSkipTests(WorkflowEngineTestBase):
    def test_quorum_any_one_completes_on_first_approval(self):
        definition = WorkflowDefinition.objects.create(code='quorum_any', name='Any', entity=self.entity, priority=3)
        step = WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='position_scoped', resolver_params={'position_id': str(self._seat_held_by(self.finance).pk), 'scope': 'global'},
            quorum=WorkflowStep.QUORUM_ANY_ONE,
        )
        wf_defs.publish(definition)
        instance = wf.start(self.record, requester=self.requester)
        tasks = list(WorkflowTask.objects.filter(instance=instance, step=step))
        self.assertGreaterEqual(len(tasks), 1)
        wf.act(tasks[0].pk, user=tasks[0].assignee, action='approve')
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_APPROVED)
        # Any sibling tasks should have been expired, not left pending forever.
        self.assertFalse(WorkflowTask.objects.filter(instance=instance, status=WorkflowTask.STATUS_PENDING).exists())

    def test_skip_condition_bypasses_a_step(self):
        definition = WorkflowDefinition.objects.create(code='skip_test', name='Skip', entity=self.entity, priority=4)
        WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
            skip_condition={'all': [{'field': 'vehicle_number', 'op': 'eq', 'value': 'TS09AB1234'}]},
        )
        wf_defs.publish(definition)
        instance = wf.start(self.record, requester=self.requester)
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_APPROVED)
        self.assertFalse(WorkflowTask.objects.filter(instance=instance).exists())

    def test_auto_approve_condition_completes_step_without_a_human(self):
        definition = WorkflowDefinition.objects.create(code='auto_test', name='Auto', entity=self.entity, priority=5)
        WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
            auto_approve_condition={'all': [{'field': 'vehicle_number', 'op': 'eq', 'value': 'TS09AB1234'}]},
        )
        wf_defs.publish(definition)
        instance = wf.start(self.record, requester=self.requester)
        instance.refresh_from_db()
        self.assertEqual(instance.status, WorkflowInstance.STATUS_APPROVED)
        history_actions = list(WorkflowHistory.objects.filter(instance=instance).values_list('action', flat=True))
        self.assertIn(WorkflowHistory.ACTION_AUTO_ACTIONED, history_actions)


class OverrideAndDelegationTests(WorkflowEngineTestBase):
    def test_employee_override_replaces_resolved_approver(self):
        definition, step1, _ = self._make_definition()
        override_user = make_user('override-approver@test.com', role=self.role)
        WorkflowApproverOverride.objects.create(
            employee=self.requester, definition=definition, step_code='manager_approval',
            user=override_user, effective_from=datetime.date(2020, 1, 1),
        )
        instance = wf.start(self.record, requester=self.requester)
        task = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        self.assertEqual(task.assignee, override_user)

    def test_delegation_redirects_assignment(self):
        from apps.platform_core.models import Delegation
        definition, step1, _ = self._make_definition()
        delegate = make_user('delegate@test.com', role=self.role)
        Delegation.objects.create(from_user=self.manager, to_user=delegate, start=datetime.date(2020, 1, 1))
        instance = wf.start(self.record, requester=self.requester)
        task = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        self.assertEqual(task.assignee, delegate)


class VersionPinningTests(WorkflowEngineTestBase):
    def test_in_flight_instance_keeps_its_started_version(self):
        definition, _, _ = self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        self.assertEqual(instance.definition_version, definition.version)

        definition.version = 2
        definition.save(update_fields=['version'])
        instance.refresh_from_db()
        self.assertEqual(instance.definition_version, 1)  # unaffected by the definition's own version bump


class PublishValidationTests(WorkflowEngineTestBase):
    def test_publish_rejects_parallel_group_steps(self):
        definition = WorkflowDefinition.objects.create(code='bad_parallel', name='Bad', entity=self.entity, priority=6)
        WorkflowStep.objects.create(definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_PARALLEL_GROUP)
        with self.assertRaises(wf_defs.WorkflowValidationError):
            wf_defs.publish(definition)

    def test_publish_rejects_unknown_resolver(self):
        definition = WorkflowDefinition.objects.create(code='bad_resolver', name='Bad', entity=self.entity, priority=7)
        WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='nonexistent_resolver',
        )
        with self.assertRaises(wf_defs.WorkflowValidationError):
            wf_defs.publish(definition)

    def test_publish_rejects_duplicate_priority_for_same_entity(self):
        self._make_definition(priority=10)
        definition2 = WorkflowDefinition.objects.create(code='dup_priority', name='Dup', entity=self.entity, priority=10)
        WorkflowStep.objects.create(
            definition=definition2, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
        )
        with self.assertRaises(wf_defs.WorkflowValidationError):
            wf_defs.publish(definition2)


class BulkActionTests(WorkflowEngineTestBase):
    def test_bulk_act_partial_success(self):
        definition = WorkflowDefinition.objects.create(code='bulk_test', name='Bulk', entity=self.entity, priority=8)
        WorkflowStep.objects.create(
            definition=definition, code='s1', label='S1', order=0, step_type=WorkflowStep.TYPE_APPROVAL,
            resolver='specific_user', resolver_params={'user_id': self.manager.pk},
        )
        wf_defs.publish(definition)
        record2 = custom_objects.create_record(self.entity, {'vehicle_number': 'TS09CD5678'}, actor=self.requester)
        record2.employee = self.requester
        record2.save()

        instance1 = wf.start(self.record, requester=self.requester)
        instance2 = wf.start(record2, requester=self.requester)
        task1 = WorkflowTask.objects.get(instance=instance1)
        task2 = WorkflowTask.objects.get(instance=instance2)

        result = wf.bulk_act([task1.pk, task2.pk], user=self.manager, action='approve')
        self.assertEqual(len(result['succeeded']), 2)
        self.assertEqual(len(result['failed']), 0)

        # Re-running the same bulk action now fails cleanly for both (already decided).
        result2 = wf.bulk_act([task1.pk, task2.pk], user=self.manager, action='approve')
        self.assertEqual(len(result2['failed']), 2)


class IdempotencyTests(WorkflowEngineTestBase):
    def test_same_idempotency_key_applied_once(self):
        definition, step1, _ = self._make_definition()
        instance = wf.start(self.record, requester=self.requester)
        task = WorkflowTask.objects.get(instance=instance, step__code='manager_approval')
        wf.act(task.pk, user=self.manager, action='approve', idempotency_key='req-123')
        result_task = wf.act(task.pk, user=self.manager, action='approve', idempotency_key='req-123')
        self.assertEqual(result_task.status, WorkflowTask.STATUS_APPROVED)
