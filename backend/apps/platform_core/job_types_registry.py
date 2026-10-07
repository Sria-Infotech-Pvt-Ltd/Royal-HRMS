"""
Phase 3B Task G.2/G.4 — job types registered in code. `JOB_CALLABLES`
maps a `JobType.task_path` to the actual Python callable `run_now()`
invokes — same "registered in code, used by admin configuration"
boundary as approver resolvers and rule data providers.

The 8 existing `CELERY_BEAT_SCHEDULE` jobs (config/settings.py) are
registered here with their CURRENT schedule as `default_schedule`
(Task G.1's "migrate the 8 jobs with identical schedules") for the seed
pack a fresh install reads — but `settings.CELERY_BEAT_SCHEDULE` itself
is NOT removed or repointed at these rows in this phase (see
models/scheduler.py's own docstring and PHASE3B_REPORT.md) — both exist
side by side; the static schedule keeps running everything exactly as
before, unaffected.
"""
from __future__ import annotations

EXISTING_CELERY_BEAT_JOBS = [
    {'code': 'missing_clockouts', 'name': 'Missing clock-outs', 'task_path': 'apps.attendance.tasks.flag_missing_clockouts', 'default_schedule': 'every 300s', 'safe_to_run_concurrently': False},
    {'code': 'absence_alerts', 'name': 'Absence alerts', 'task_path': 'apps.attendance.tasks.send_absence_alerts', 'default_schedule': '0 9 * * *', 'safe_to_run_concurrently': False},
    {'code': 'birthday_wishes', 'name': 'Birthday wishes', 'task_path': 'apps.accounts.tasks.send_birthday_wishes', 'default_schedule': '5 0 * * *', 'safe_to_run_concurrently': False},
    {'code': 'annual_leave_reset', 'name': 'Annual leave reset', 'task_path': 'apps.hrms.tasks.reset_annual_leave', 'default_schedule': '1 0 1 1 *', 'safe_to_run_concurrently': False, 'parameter_schema': {'type': 'object', 'properties': {'reset_date': {'type': 'string', 'format': 'date', 'description': 'Task G.5 — the hardcoded Jan 1 date, now a parameter. Leave-YEAR logic itself is unchanged (Phase 6).'}}}},
    {'code': 'monthly_leave_accrual', 'name': 'Monthly leave accrual', 'task_path': 'apps.hrms.tasks.accrue_monthly_leave', 'default_schedule': '1 0 1 * *', 'safe_to_run_concurrently': False},
    {'code': 'carry_forward_expiry', 'name': 'Carry-forward expiry', 'task_path': 'apps.hrms.tasks.expire_carry_forward', 'default_schedule': '10 0 * * *', 'safe_to_run_concurrently': False},
    {'code': 'payroll_approval_reminders', 'name': 'Payroll approval reminders', 'task_path': 'apps.payroll.tasks.send_approval_reminders', 'default_schedule': '0 10 * * *', 'safe_to_run_concurrently': True},
    {'code': 'review_cycle_closing', 'name': 'Review cycle closing', 'task_path': 'apps.performance.tasks.close_expired_review_cycles', 'default_schedule': '15 0 * * *', 'safe_to_run_concurrently': False},
    {'code': 'apply_scheduled_employment_actions', 'name': 'Apply scheduled employment actions', 'task_path': 'apps.accounts.tasks.apply_scheduled_employment_actions', 'default_schedule': '20 0 * * *', 'safe_to_run_concurrently': True},
]

NEW_JOB_TYPES = [
    {'code': 'workflow_sla_processor', 'name': 'Workflow SLA processor', 'task_path': 'apps.platform_core.job_runners.process_workflow_sla', 'default_schedule': 'every 300s', 'safe_to_run_concurrently': False},
    {'code': 'event_outbox_drainer', 'name': 'Event outbox drainer', 'task_path': 'apps.platform_core.job_runners.drain_event_outbox', 'default_schedule': 'every 60s', 'safe_to_run_concurrently': True},
    {'code': 'notification_digest_sender', 'name': 'Notification digest sender', 'task_path': 'apps.platform_core.job_runners.send_notification_digests', 'default_schedule': '0 8 * * *', 'safe_to_run_concurrently': False},
]

ALL_JOB_TYPES = EXISTING_CELERY_BEAT_JOBS + NEW_JOB_TYPES


def sync() -> dict:
    from apps.platform_core.models import JobType
    created = unchanged = 0
    for spec in ALL_JOB_TYPES:
        obj, was_created = JobType.objects.get_or_create(
            code=spec['code'],
            defaults={
                'name': spec['name'], 'task_path': spec['task_path'],
                'default_schedule': spec['default_schedule'],
                'safe_to_run_concurrently': spec.get('safe_to_run_concurrently', False),
                'parameter_schema': spec.get('parameter_schema', {}),
                'is_system': True,
            },
        )
        created += was_created
        unchanged += not was_created
    return {'created': created, 'unchanged': unchanged}
