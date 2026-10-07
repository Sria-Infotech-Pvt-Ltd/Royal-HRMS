# Scheduler — `apps/platform_core/services_scheduler.py`

## What this phase built

`JobType` (code-registered, `job_types_registry.py`, synced via
`sync_job_types`) — covers the 8 existing `CELERY_BEAT_SCHEDULE` jobs
(`config/settings.py`) with their current schedule recorded as
`default_schedule`, PLUS 3 new job types this phase needs:
`workflow_sla_processor`, `event_outbox_drainer`, `notification_digest_sender`
(`job_runners.py`).

`ScheduledJob` — admin-created instances: job type, cron/interval,
**per-job IANA timezone** (`timezone` field, default `Asia/Kolkata` — the
existing server default), parameters (validated against the job type's
own schema structurally, not yet enforced at save time — see "Deferred"),
legal-entity scope, enabled flag.

`JobRun` — start/end/status/`result_counts`/`error_summary` (never
sensitive data — a short string, never a full traceback with PII),
`triggered_by` (schedule/admin "run now"/system).

`services_scheduler.run_now(scheduled_job_id, ...)` — locks the
`ScheduledJob` row (`select_for_update()`), refuses to start if
`is_running=True` and the job type isn't marked
`safe_to_run_concurrently` (raises `SchedulerError`, never silently
queues or skips), always releases the lock in a `finally`-equivalent
path even when the job itself raises (`JobRun.status=failed`, lock
released) — proven by `tests_scheduler.SchedulerTests.test_run_now_records_failure_without_crashing`.

`overdue_scheduled_jobs(grace_minutes=30)` — Task G.3's missed-run
detection; returns the list of jobs whose `next_run_at` passed by more
than the grace period. Emitting an alert event for each is left to
whatever calls this (a future job of its own), kept as a pure query here.

## What's deliberately NOT built (stated plainly)

- **`django-celery-beat` was not installed, and `settings.CELERY_BEAT_SCHEDULE`
  was not replaced.** The 8 existing jobs keep running exactly as they do
  today, completely unaffected by anything in this phase — `ScheduledJob`/
  `JobRun` exist side by side as real, usable infrastructure, but nothing
  reads from them to decide what Celery Beat actually runs yet. Installing
  a new dependency and repointing the actual beat scheduler is a
  deployment-config change with its own rollback risk, out of scope for
  "build the engine" vs. "cut over the engine."
- **`run_now()` calls a job type's registered callable directly and
  synchronously** — not via a Celery task dispatch. Fine for admin
  "run now" (a human is waiting for the result anyway); NOT how a real
  cron-triggered run should work in production (that needs an actual
  Celery Beat schedule reading `ScheduledJob` rows, which is exactly the
  cutover named above).
- **Parameter validation against `JobType.parameter_schema`** isn't
  enforced when a `ScheduledJob` is saved — the schema is declared and
  stored but nothing checks a job's `parameters` against it yet.
- **`notification_digest_sender`** returns a zero-count no-op — real
  digest batching (group pending digest-mode `NotificationRule` matches
  per user per day) needs a staging table this phase didn't build.
- **Timezone-aware birthday/anniversary jobs** (Task G.5's "must use the
  employee's location timezone when ON") — not implemented; the existing
  `birthday_wishes` job type is registered with its current
  server-timezone schedule unchanged.

## Business-date correctness (Task G.5)

The `annual_leave_reset` job type's `parameter_schema` now declares a
`reset_date` parameter (defaulting to the current Jan-1 behavior) instead
of a hardcoded date — but this is the schema declaration only; no
`ScheduledJob` row was created wired to actually read it instead of the
hardcoded constant in `apps.hrms.tasks.reset_annual_leave` (that function
itself is untouched). Leave-year logic itself is unchanged, per the
prompt's own explicit instruction.
