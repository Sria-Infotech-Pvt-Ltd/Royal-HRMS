"""
The sync layer around services_project_assignments: every attempt is logged (ProjectSyncLog), employees we can't match
are reported to admins instead of silently dropped, and the pulls (per-employee fallback, scheduled reconcile) live here.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

import requests
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache

from apps.accounts.models import User
from apps.hrms.models import ProjectAssignment, ProjectSyncLog
from apps.hrms.serializers_project_assignment import ProjectAssignmentRowSerializer
from apps.hrms.services_project_assignments import STATUS_COMPLETED, STATUS_REMOVED, apply_employee_snapshot

logger = logging.getLogger(__name__)

SOURCE_WEBHOOK = 'webhook'
SOURCE_PULL = 'pull'
SOURCE_RECONCILE = 'reconcile'
RECONCILE_ACTOR = 'scheduled_reconcile'
PULL_ACTOR = 'dashboard_fallback_pull'

PROJECT_ASSIGNMENTS_PATH = '/api/v1/project-assignments/'
RESOURCE_ASSIGNMENTS_PATH = '/api/v1/resource-assignments/'
# Per HTTP request to Project Budgeting: (connect, read). A host that cannot be reached at all (wrong network, firewall) is
# given up on after the 3 s connect timeout instead of 10 s; a host that answers slowly still gets 10 s to send its page.
PULL_CONNECT_TIMEOUT_SECONDS = 3
PULL_READ_TIMEOUT_SECONDS = 10
PULL_PAGE_SIZE = 100
PULL_MAX_PAGES = 200
# Total wall-clock budget for the one-employee fallback pull, checked before every page. Celery's own time limits are not
# enforced by the `solo` worker pool used on Windows, so this is what actually bounds the task there.
FALLBACK_PULL_BUDGET_SECONDS = 30
FALLBACK_COOLDOWN_SECONDS = 10 * 60
# How long a queued fallback pull may still be reported as running (see queue_employee_assignments_sync): task hard limit
# (60 s) + margin. If the worker never picks the job up, the page stops reporting sync_pending after this.
FALLBACK_RUNNING_SECONDS = 90
# If the task could not even be queued (broker down), retry on a later request after this short pause, not after the full
# cooldown, so an employee is not locked out of the fallback for ten minutes by a hiccup in the queue.
ENQUEUE_FAILURE_RETRY_SECONDS = 30
UNMATCHED_ALERT_COOLDOWN_SECONDS = 24 * 60 * 60

NOTIFICATION_TYPE_PROJECT_SYNC_ALERT = 'project_sync_alert'
NOTIFICATION_MODULE_SYSTEM = 'system'


class ProjectSyncError(Exception):
    """A whole-list pull from Project Budgeting couldn't be completed (so nothing was changed)."""


def alert_admins_unmatched(employee_code: str) -> None:
    """Tell every system admin that Project Budgeting sent projects for an employee_id we don't have. At most once per
    employee per day so a retrying sender can't flood them."""
    if not cache.add(f'project_sync_unmatched:{employee_code}', True, UNMATCHED_ALERT_COOLDOWN_SECONDS):
        return
    from core.access import users_with_permission
    from apps.notifications.signals import _notify

    admins = User.objects.filter(users_with_permission('settings.edit'), is_active=True).distinct()
    for admin in admins:
        _notify(
            admin,
            'Project assignment for unknown employee',
            f'Project Budgeting sent project assignments for employee ID "{employee_code}", which does not match any '
            'employee in AIRA HRMS. The data is stored and will appear once the employee exists. '
            'Check the ID in Project Budgeting.',
            NOTIFICATION_TYPE_PROJECT_SYNC_ALERT, NOTIFICATION_MODULE_SYSTEM, reference_id=employee_code,
        )


def sync_employee_snapshot(employee_code: str, rows: list[dict], *, source: str, triggered_by: str) -> dict:
    """apply_employee_snapshot + sync log + unmatched-employee alert. A failure is logged and re-raised so the sender
    (or Celery) retries."""
    try:
        result = apply_employee_snapshot(employee_code, rows, source=source, triggered_by=triggered_by)
    except Exception as exc:
        logger.exception('Project assignments sync failed for %s', employee_code)
        ProjectSyncLog.objects.create(
            source=source, triggered_by=triggered_by, employee_code=employee_code,
            status=ProjectSyncLog.STATUS_FAILED, message=MSG_NOT_SAVED,
        )
        raise

    is_matched = User.objects.filter(employee_id=employee_code).exists()
    if not is_matched:
        logger.error('Project assignments synced for unknown employee_id %s; stored for later.', employee_code)
        alert_admins_unmatched(employee_code)
    ProjectSyncLog.objects.create(
        source=source, triggered_by=triggered_by, employee_code=employee_code,
        status=ProjectSyncLog.STATUS_SUCCESS if is_matched else ProjectSyncLog.STATUS_UNMATCHED,
        saved=result['saved'], changed=result['changed'], removed=result['removed'],
        message='' if is_matched else 'No employee in AIRA HRMS has this employee ID.',
    )
    return {**result, 'is_matched': is_matched}


def _credentials() -> tuple[str, str] | None:
    base_url = getattr(settings, 'PROJECT_BUDGET_API_BASE_URL', '')
    api_key = getattr(settings, 'PROJECT_BUDGET_API_KEY', '')
    return (base_url.rstrip('/'), api_key) if base_url and api_key else None


# Everything below is what an HR admin reads on the Project Budgeting sync page, so each ProjectSyncError and every stored
# failure message is one plain sentence: no exception names, setting names, field names or addresses. The technical detail
# goes to the server log next to where each is raised.
MSG_NOT_RESPONDING = 'Project Budgeting is not responding. Please check that it is running.'
MSG_TOO_SLOW = 'Project Budgeting is taking too long to respond.'
MSG_NOT_UNDERSTOOD = 'Project Budgeting sent information AIRA could not understand.'
MSG_NOT_SET_UP = 'The connection to Project Budgeting has not been set up yet.'
MSG_STOPPED_TOO_LONG = 'Checking Project Budgeting took too long and was stopped. It will be tried again.'
MSG_TOO_MUCH_DATA = 'Project Budgeting sent more information than AIRA can read in one check.'
MSG_BAD_DETAILS = 'Project Budgeting sent project details that were incomplete or not valid, so nothing was changed.'
MSG_NOT_SAVED = 'AIRA could not save this update. Please ask Project Budgeting to send it again.'


def _describe_pull_failure(exc: Exception) -> str:
    """The sentence for a failed pull. The raw exception text (connection-pool class names, memory addresses, the whole
    URL) stays in the server log; it is unreadable in a table and is not what an admin acts on."""
    if isinstance(exc, (requests.ConnectTimeout, requests.ConnectionError)):
        return MSG_NOT_RESPONDING
    if isinstance(exc, requests.Timeout):
        return MSG_TOO_SLOW
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        if code in (401, 403):
            return f"Project Budgeting did not accept AIRA's access key (code {code})."
        return f'Project Budgeting reported a problem (code {code}).'
    return MSG_NOT_UNDERSTOOD


def _get_all_pages(path: str, params: dict, *, budget_seconds: float | None = None) -> list[dict]:
    """Every row from a paginated Project Budgeting list, or ProjectSyncError (callers must not act on partial data).

    `budget_seconds` caps the whole pull (not one request): once it is spent the pull stops with ProjectSyncError before
    asking for another page. None (the scheduled reconcile) means no overall cap, only the per-request timeouts."""
    credentials = _credentials()
    if credentials is None:
        raise ProjectSyncError(MSG_NOT_SET_UP)
    base_url, api_key = credentials
    deadline = None if budget_seconds is None else time.monotonic() + budget_seconds
    rows: list[dict] = []
    for page in range(1, PULL_MAX_PAGES + 1):
        if deadline is not None and time.monotonic() >= deadline:
            logger.warning('Pull of %s ran out of its %gs time budget before page %s.', path, budget_seconds, page)
            raise ProjectSyncError(MSG_STOPPED_TOO_LONG)
        try:
            response = requests.get(
                f'{base_url}{path}', params={**params, 'page': page, 'page_size': PULL_PAGE_SIZE},
                headers={'X-API-Key': api_key}, timeout=(PULL_CONNECT_TIMEOUT_SECONDS, PULL_READ_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            data = response.json()['data']
            rows.extend(data['results'])
            total_pages = int(data['total_pages'])
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning('Pull of %s failed on page %s: %s', path, page, exc)
            raise ProjectSyncError(_describe_pull_failure(exc)) from exc
        if page >= total_pages:
            return rows
    logger.warning('Pull of %s exceeded %s pages.', path, PULL_MAX_PAGES)
    raise ProjectSyncError(MSG_TOO_MUCH_DATA)


def _validated_rows(raw_rows: list[dict]) -> list[dict]:
    serializer = ProjectAssignmentRowSerializer(data=raw_rows, many=True)
    if not serializer.is_valid():
        logger.warning('Invalid assignment rows from Project Budgeting: %s', serializer.errors)
        raise ProjectSyncError(MSG_BAD_DETAILS)
    return serializer.validated_data


def _state_key(employee_code: str) -> str:
    """One cache key per employee does both jobs, so there is no gap between "claimed" and "marked running":
    its existence is the cooldown, and its VALUE is the time until which a queued pull may still be running
    (0 = finished, failed, or never queued). The key name is the one the earlier synchronous version used (value True);
    a leftover True reads as "not pending", so a deploy over the old version is safe."""
    return f'project_assignments_pull:{employee_code}'


def _is_pending(state) -> bool:
    return isinstance(state, (int, float)) and not isinstance(state, bool) and state > time.time()


def _tasks_run_eagerly() -> bool:
    """True when Celery runs tasks inline in the calling process (CELERY_TASK_ALWAYS_EAGER, which settings.py turns on when
    no REDIS_URL is configured). Read from the live Celery app, which is what actually decides it."""
    from celery import current_app
    return bool(current_app.conf.task_always_eager)


def queue_employee_assignments_sync(employee_code: str) -> bool:
    """Dashboard fallback: when we hold no rows for an employee, ask for ONE pull from Project Budgeting in the background.

    Never waits for Project Budgeting and never raises, so a slow or unreachable service cannot hold up the employee's
    dashboard. Returns `sync_pending`: True only while a queued pull is still expected to finish, so the caller can
    refresh once afterwards. It is False when there is nothing to do, when a pull has already been tried within the
    cooldown, when queueing failed, and when tasks run eagerly (see below).

    Exactly one request per employee per cooldown window gets to queue the task: `cache.add` is atomic (Redis SET NX), so
    the dashboard and Work Status loading at the same moment cannot queue it twice. The pull itself only ever runs for an
    employee with NO stored rows, and never overwrites rows that have arrived since (see run_employee_assignments_pull).
    """
    if not employee_code or _credentials() is None:
        return False
    if ProjectAssignment.objects.filter(employee_code=employee_code).exists():
        return False
    # The atomic gate. The value says "a pull may be running until <this time>" from the very first instant it exists.
    if not cache.add(_state_key(employee_code), time.time() + FALLBACK_RUNNING_SECONDS, FALLBACK_COOLDOWN_SECONDS):
        # Someone queued (or ran) a pull within the cooldown. It is "pending" only while that task may still be running.
        return _is_pending(cache.get(_state_key(employee_code)))

    if _tasks_run_eagerly():
        # NOT asynchronous: with no broker configured Celery would execute the task right here, inside this request, so the
        # pull is simply run inline. It is still bounded (3 s connect / 10 s read per page, 30 s total) and cannot raise,
        # but the request does wait for it. The result is already stored by the time the caller reads the assignments, so
        # nothing is pending.
        # It calls the function directly instead of task.apply(): config/celery.py runs close_old_connections() before and
        # after every task, eager ones included, and that would close THIS request's database connection in the middle of
        # the request (with CONN_MAX_AGE=0 it always does, and inside a transaction it breaks the rest of the request).
        try:
            run_employee_assignments_pull(employee_code)
        except Exception:  # noqa: BLE001 — the dashboard must still load.
            logger.exception('Eager fallback pull crashed for %s', employee_code)
        return False

    from apps.hrms.tasks import pull_employee_assignments

    try:
        # retry=False: fail at once if the broker is unreachable instead of retrying inside the request.
        pull_employee_assignments.apply_async(args=[employee_code], retry=False)
    except Exception:  # noqa: BLE001 — a queue problem must never break the dashboard.
        logger.warning('Could not queue the project-assignments pull for %s', employee_code, exc_info=True)
        # Nothing is running, and shorten the cooldown instead of leaving the employee behind a ten-minute one for
        # something that never ran.
        cache.set(_state_key(employee_code), 0, ENQUEUE_FAILURE_RETRY_SECONDS)
        return False
    return True


def _log_failed_pull(employee_code: str, message: str) -> None:
    try:
        ProjectSyncLog.objects.create(
            source=SOURCE_PULL, triggered_by=PULL_ACTOR, employee_code=employee_code,
            status=ProjectSyncLog.STATUS_FAILED, message=message[:1000],
        )
    except Exception:  # noqa: BLE001 — failing to write the log row must not mask the original problem.
        logger.exception('Could not record the failed fallback pull for %s', employee_code)


def run_employee_assignments_pull(employee_code: str) -> None:
    """Body of the queued fallback task (apps.hrms.tasks.pull_employee_assignments). Never raises.

    * If rows exist by now (a Project Budgeting push or the scheduled reconcile got there first) it does nothing, so it
      can never overwrite them with an older pull.
    * A failed or slow pull (service unreachable, timeout, out of budget, invalid rows) changes nothing that is stored: the
      list is fetched and validated completely BEFORE anything is written. The failure is logged in ProjectSyncLog.
    * There is no Celery retry: the next dashboard visit after the cooldown and the 30-minute scheduled reconcile are the
      bounded retries, and neither can pile up.
    * It always marks the state "not running" so the page stops reporting sync_pending (the cooldown restarts from the
      moment the attempt finished)."""
    try:
        if ProjectAssignment.objects.filter(employee_code=employee_code).exists():
            return
        rows = _validated_rows(_get_all_pages(
            PROJECT_ASSIGNMENTS_PATH, {'employee_id': employee_code, 'status': 'all'}, budget_seconds=FALLBACK_PULL_BUDGET_SECONDS,
        ))
        sync_employee_snapshot(employee_code, rows, source=SOURCE_PULL, triggered_by=PULL_ACTOR)
    except (ProjectSyncError, SoftTimeLimitExceeded) as exc:
        logger.warning('Fallback pull failed for %s: %s', employee_code, exc)
        _log_failed_pull(employee_code, MSG_STOPPED_TOO_LONG if isinstance(exc, SoftTimeLimitExceeded) else str(exc))
    except Exception:  # noqa: BLE001 — sync_employee_snapshot already logged it.
        logger.exception('Fallback pull crashed for %s', employee_code)
    finally:
        cache.set(_state_key(employee_code), 0, FALLBACK_COOLDOWN_SECONDS)


def reconcile_all_employees() -> dict:
    """Scheduled safety net for missed pushes: pull EVERY employee assignment (including removed ones) and re-apply
    each employee's list. Employees we hold open assignments for who are absent from the pull are treated as having no
    projects (their rows get closed, not deleted). Raises ProjectSyncError, leaving everything untouched, if any page of
    the pull fails — a partial list must never be read as "these people were removed"."""
    if _credentials() is None:
        return {'skipped': True}
    try:
        raw_rows = _get_all_pages(RESOURCE_ASSIGNMENTS_PATH, {'resource_type': 'employee', 'status': 'all'})
        by_code: dict[str, list[dict]] = defaultdict(list)
        for raw in raw_rows:
            if raw.get('resource_code'):
                by_code[raw['resource_code']].append(raw)
        validated = {code: _validated_rows(rows) for code, rows in by_code.items()}
    except ProjectSyncError as exc:
        ProjectSyncLog.objects.create(
            source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR, status=ProjectSyncLog.STATUS_FAILED,
            message=str(exc)[:1000],
        )
        raise

    held_codes = set(
        ProjectAssignment.objects
        .exclude(assignment_status__in=(STATUS_REMOVED, STATUS_COMPLETED))
        .values_list('employee_code', flat=True)
    )
    failed = 0
    for code in sorted(set(validated) | held_codes):
        try:
            sync_employee_snapshot(code, validated.get(code, []), source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR)
        except Exception:  # noqa: BLE001 — logged per employee inside sync_employee_snapshot; keep going.
            failed += 1
    summary = {'employees': len(set(validated) | held_codes), 'failed': failed}
    ProjectSyncLog.objects.create(
        source=SOURCE_RECONCILE, triggered_by=RECONCILE_ACTOR,
        status=ProjectSyncLog.STATUS_FAILED if failed else ProjectSyncLog.STATUS_SUCCESS,
        saved=len(raw_rows), message=(f'Checked {summary["employees"]} employees.' if not failed else f'Checked {summary["employees"]} employees; {failed} could not be saved.'),
    )
    return summary
