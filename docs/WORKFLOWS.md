# Workflow/approval engine — `apps/platform_core/services_workflow.py`

## Concepts

- **`WorkflowDefinition`** — the design-time graph for one `EntityDefinition`
  (core or custom). `trigger` (on_submit/on_create/on_field_change/manual),
  `entry_condition` (a rule expression — `docs/RULES.md` format), `priority`
  (highest-priority matching definition wins; **ties among published
  definitions for the same entity are a publish-time error**, not a
  runtime ambiguity). Publishing pins nothing retroactively — an
  **in-flight `WorkflowInstance` keeps the `definition_version` it
  started with forever**, even if the definition is edited and
  republished later (`tests_workflow_engine.VersionPinningTests` proves
  this).
- **`WorkflowStep`** — ordered. Six declared types
  (`approval`/`review`/`notification_only`/`system_action`/
  `condition_branch`/`parallel_group`) — **`parallel_group` is rejected at
  publish time in this phase** (see "What's deferred" below); the other
  five all run for real.
- **Approver resolvers** (`approver_resolvers.py`) — a registry of named
  functions, not admin-supplied code. `specific_user`, `role_scoped`
  (global/branch/org_unit/legal_entity), `reporting_manager_level_n`,
  `dotted_line_manager`, `org_unit_chief` (calls
  `apps.accounts.services_approval.resolve_employee_org_unit_chief()`
  directly — not a reimplementation, so it can never silently drift from
  the legacy "department head" logic it reproduces), `hr_business_partner`
  (`employee.hr` — the other half of
  `services_approval.resolve_approver()`'s existing logic),
  `position_holder`, `record_field`, `rule_expression`. **Not
  implemented**: a dedicated `branch_admin` resolver (no single existing
  function defines "branch admin" unambiguously — see "What's deferred").
- **Quorum**: `any_one` / `all` / `n_of_m`. Meeting quorum expires any
  remaining pending sibling tasks for that step (they're never left
  dangling).
- **Skip/auto-approve/no-approver rules**: `skip_condition` (a rule
  expression — step is bypassed entirely, no task created),
  `auto_approve_condition` (step is marked auto-actioned and passed
  through, logged in `WorkflowHistory`), `no_approver_action`
  (`fallback_role` / `skip` / `block_and_alert` — **never silent**; `block`
  flips the instance to `STATUS_ERROR` and writes a history entry
  explaining why).
- **SLA**: `sla_due_in_hours` sets `WorkflowTask.due_at` when the task is
  created; `sla_escalation_after_hours`/`sla_escalation_resolver` are
  processed by the `workflow_sla_processor` scheduled job (Task G) —
  reminders at `sla_reminder_hours` and `sla_timeout_action`
  (auto-approve/auto-reject at final timeout) are modeled on
  `WorkflowStep` but **not yet acted on by the SLA processor job** (it
  currently only escalates once past due — see "What's deferred").

## Separation of duties (default: not allowed)

Enforced at TWO points, so a misconfiguration at one layer can't bypass
the other:
1. **Resolution time** — `skip_if_approver_is_requester` (default `True`)
   filters the requester out of a step's resolved approver list before
   any task is even created.
2. **Action time** (`services_workflow.act()`) — even if a task somehow
   ended up assigned to the requester (a misconfigured resolver,
   a delegation looping back), acting on it as `approve`/`reject`/etc.
   raises `WorkflowError` unconditionally. Separately, a user who already
   approved an EARLIER step of the SAME instance is blocked from
   approving a LATER step too, unless that later step's own
   `skip_if_same_as_previous_step=False` explicitly allows it.

## Delegation

`Delegation(from_user, to_user, scope_entities, start, end)` — applied at
task-resolution time (`_apply_overrides_and_delegation()`): an employee-
level `WorkflowApproverOverride` is applied FIRST (it changes WHO the
resolved approver is), THEN delegation is checked against whoever that
resolved approver turns out to be. `scope_entities` empty = all entities.
**Not yet implemented**: applying a delegation retroactively to tasks
already open when the delegation starts (`apply_to_already_open_tasks` is
a stored flag on the model, read by nothing yet — see "What's deferred").

## Idempotency and concurrency

`act()` is wrapped in `transaction.atomic()` with
`WorkflowTask.objects.select_for_update()` on the specific task row —
two different pending tasks on the same instance (a quorum step) can be
acted on concurrently without blocking each other, while two clicks on
the SAME task serialize: the second sees `status != pending` and either
returns the already-applied result (if the same `idempotency_key` was
supplied) or raises cleanly.

## Example: the "Vehicle Allocation" 2-step approval (Acceptance Criterion 2)

```python
definition = WorkflowDefinition.objects.create(
    code='vehicle_allocation_approval', entity=vehicle_allocation_entity, priority=0,
    status_field_code='approval_status',
    status_mapping={'approved': 'APPROVED', 'rejected': 'REJECTED'},
)
WorkflowStep.objects.create(
    definition=definition, code='manager_approval', order=0, step_type='approval',
    resolver='reporting_manager_level_n', resolver_params={'level': 1},
    sla_due_in_hours=48,
)
WorkflowStep.objects.create(
    definition=definition, code='finance_approval', order=1, step_type='approval',
    resolver='role_scoped', resolver_params={'role_id': finance_role.id, 'scope': 'global'},
)
services_workflow_definitions.publish(definition)
instance = services_workflow.start(record, requester=employee)
```
No code change — every piece above is admin-entered configuration data.

## What's real vs. deferred in this phase

- **Built and tested**: linear step progression (including
  `condition_branch`), quorum, skip/auto-approve conditions, no-approver
  handling, employee overrides, delegation redirection, separation of
  duties, withdraw/reassign/cancel/bulk-act, idempotency, version
  pinning, publish-time validation (cycles via branch-target existence
  checks, resolver validity, priority-tie rejection).
- **`parallel_group` steps are rejected at publish time** — the runtime
  engine only ever advances one step at a time. Building real fan-out/
  join semantics is a genuine design task (what does "quorum" mean
  across parallel branches that themselves have sub-quorums?) deferred
  to its own pass rather than guessed at.
- **SLA reminders and final-timeout auto-actions are not processed** —
  only escalation-after-due-date fires (via the `workflow_sla_processor`
  job, Task G). `sla_reminder_hours`/`sla_timeout_action` are stored but
  unread.
- **`Delegation.apply_to_already_open_tasks`** is stored but not acted
  on — a delegation only ever affects tasks created AFTER it starts.
- **Task C (migrating leave/WFH/attendance-correction/expense onto this
  engine) was not executed** — see `PHASE3B_REPORT.md` and
  `docs/MIGRATION_PLAN.md`. The engine itself was proven end-to-end
  against a Phase 2 custom entity instead (Acceptance Criterion 2), which
  needs no legacy-column compatibility work at all.
- **`system_action` steps** only support one action (`set_field`) —
  `set_status`/`create_record`/`call_webhook` are named by the prompt but
  not implemented.
