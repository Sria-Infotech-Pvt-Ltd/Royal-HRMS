# Domain events and notifications

## Events (`apps/platform_core/services_events.py`)

`EventType` is a code-registered catalogue (`event_types_registry.py`,
synced via `sync_event_types`, also run on `post_migrate`). 14 core event
types registered in this phase (see `event_types_registry.CORE_EVENT_TYPES`),
e.g. `leave.submitted`, `workflow.task.assigned`, `employee.birthday`,
`attendance.missing_clockout`. Publishing a custom entity (Phase 2)
automatically gets 3 events — `custom.<entity_code>.created/updated/
status_changed` — via `event_types_registry.sync_custom_entity_events()`,
called from `services_custom_objects.publish_entity()`.

### Adding an event type as a developer

Add an entry to `CORE_EVENT_TYPES` in `event_types_registry.py` with a
`payload_schema` declaring every variable a template is allowed to read,
and whether each is `sensitive` (sensitive variables render as `***`
unless a specific template explicitly allows them — see "Sandboxed
rendering" below). Run `sync_event_types` (or wait for the next
`post_migrate`).

### Emission and the outbox

```python
from apps.platform_core import services_events as events
events.emit('leave.submitted', {'record': leave_request, 'amount': ...}, actor=employee)
```

`emit()` always writes an `EventOutbox` row inside the caller's own
transaction (a rollback un-emits it too) and schedules delivery via
`transaction.on_commit`. **Delivery in this phase is synchronous** — the
`on_commit` callback calls `drain_outbox()` inline, not a real Celery
task (same deferred-async reasoning as Phase 2's import/export and Phase
3A's policy resolution). The `EventOutbox` status machine
(`pending -> processing -> sent/failed`), guarded by
`select_for_update(skip_locked=True)`, means a crash mid-drain or a
scheduled-job drain racing an `on_commit` drain can never process the
same row twice — proven by
`tests_events_notifications.EventEmissionTests.test_drain_outbox_never_processes_the_same_row_twice`.
The `event_outbox_drainer` scheduled job (Task G) exists specifically to
recover any row left `pending` if the inline `on_commit` drain never ran
(process crash) — this is what "survives a Celery outage" means in this
phase's synchronous-delivery design: nothing is lost, it just waits for
the next drain.

## Notifications (`apps/platform_core/services_notifications.py`)

### Sandboxed rendering — read this before touching `render()`

Rendering is deliberately **plain `{{token}}` substitution**, not
Jinja2/Django templates. Both of those allow attribute traversal
(`{{ user.__class__.__mro__ }}`-style escapes) unless explicitly
sandboxed with extra configuration — a whitelist token substitution
*guarantees* "no attribute access to arbitrary objects, only declared
variables" by construction, rather than by configuring an off-the-shelf
engine correctly. `_TOKEN_RE` only matches a bare `{{var_name}}` (no
dots, no function calls, no filters) against the resolved context dict's
own keys:
- A token naming a key **not present** in context is left as literal
  text, unevaluated — never an error, never a crash.
- A token naming a **sensitive** variable (per `EventType.payload_schema`)
  renders as `***` unless the specific `MessageTemplate.allowed_sensitive_vars`
  lists it.
- `email`/`in_app` channels HTML-escape every substituted value
  (autoescape); `webhook` does not (it's a raw JSON payload, not HTML).

Proven directly: `tests_events_notifications.SandboxedRenderingTests.test_sandbox_escape_attempt_is_inert`
creates a template with `{{__class__}}{{name.__class__}}` and confirms
both render as inert literal text.

### `NotificationRule`

`event_type` + `condition` (a rule expression — only fires when true) +
`channels` (`["email", "in_app"]`, `webhook` built, `sms`/`whatsapp`/`push`
declared on `MessageTemplate.CHANNEL_CHOICES` but have **no provider
implementation** — calling `_send()` for one raises
`NotificationError` cleanly) + `recipient_type` (the record's employee /
the requester / a resolver — reuses `approver_resolvers.py`, same
registry workflows use / a lookup-defined distribution list / fixed
emails, admin-only) + `is_mandatory` (ignores mute preferences entirely)
+ `legal_entity` applicability + quiet hours (`quiet_hours_start`/`end`,
wraps correctly past midnight).

### Deduplication (Task F.3's "duplicate sends must be impossible")

`NotificationDelivery.dedup_key` = `sha256(rule_id:event_entry_id:
recipient_id:channel)`, with a DB-level `UniqueConstraint` on that column
— not just an application-level check. `dispatch_for_event()` checks for
an existing row with that key before ever rendering or sending; the
constraint is the actual backstop if two drains somehow race past that
check. Proven by
`tests_events_notifications.DispatchDedupMuteTests.test_same_event_never_double_sends_to_same_recipient`.

### Preferences (`UserNotificationPreference`)

Replaces the hardcoded `NotificationSettings` booleans — `(user,
event_category_or_type, channel, enabled)`, where `event_category_or_type`
is either a specific `EventType.code` (fine-grained) or an `EventType.module`
value (coarse, "mute everything from `hrms`"). **Not implemented in this
phase**: migrating the actual `NotificationSettings` boolean values into
this table, or keeping the old `NotificationSettings` read/write endpoint
working by mapping onto the new table (Task F.4's explicit ask) — see
`PHASE3B_REPORT.md`.

### Webhook signing

`sign_webhook_payload(payload, secret)` / `verify_webhook_signature(...)`
— real HMAC-SHA256, tested
(`tests_events_notifications.WebhookSignatureTests`). **No actual HTTP
POST is issued** — no webhook URL/secret configuration model was built
in this phase (`_send_webhook()` is a documented no-op); the signing
primitive itself is real and ready for whoever builds that configuration
layer.

## Migrating the legacy notification/email catalogue (Task F.5) — NOT done

The prompt's Task F.5 asks to convert **every** existing notification/
email trigger (the Section-2 catalogue) into seeded `NotificationRule` +
`MessageTemplate` rows behind flag `notifications.v2`, with parity tests
proving identical recipients/content OFF vs ON, and a test proving
old+new can never both fire. **None of this was executed in this
phase** — see `PHASE3B_REPORT.md`'s "Deferred" section for the full
reasoning (same risk class as Phase 3A's attendance consolidation: a
live-data cutover touching every existing notification call site needs
its own dedicated, parity-tested pass).
