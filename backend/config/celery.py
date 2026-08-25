"""
Celery application entry point for Aira HRMS.

CELERY_BEAT_SCHEDULE (config/settings.py) is a plain dict, read by Celery's
built-in default scheduler — django-celery-beat is NOT installed in this
project, so do not pass --scheduler django_celery_beat.schedulers:DatabaseScheduler;
that module doesn't exist here and the command will fail. The default
scheduler persists its state locally in backend/celerybeat-schedule.dat/.dir.

Usage (Linux/macOS):
    Worker:  celery -A config worker -l info
    Beat:    celery -A config beat   -l info
    Or both: celery -A config worker -l info -B

Usage (Windows) — run worker and beat as two separate processes; -B (embedded
beat) is rejected by the CLI on Windows, and add --pool=solo to the worker.
Celery's default prefork pool (billiard) relies on POSIX fork/signal
semantics Windows doesn't support properly, and crashes with "OSError:
[WinError 6] The handle is invalid" during normal worker pool bookkeeping.
--pool=solo runs everything single-threaded in the main process, avoiding
the incompatibility entirely:

    celery -A config worker -l info --pool=solo   (terminal 1)
    celery -A config beat   -l info                (terminal 2)
"""
import os

from celery import Celery
from celery.signals import task_postrun, task_prerun

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('hrms')

# Read Celery config from settings.py keys prefixed with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()


# Both the worker and (on Windows, since -B/embedded-beat isn't supported
# here — see the module docstring) the standalone `celery beat` process are
# long-running processes that sit idle between tasks, sometimes for minutes.
# Django's usual "close a connection past CONN_MAX_AGE" cleanup is wired to
# the request_finished signal, which never fires outside an HTTP
# request/response cycle — so a connection opened by an earlier task run (or
# by Celery Beat's own scheduling query, e.g. sweep_stale_provisioning) can
# sit idle long enough for Neon (or any managed Postgres with its own idle
# timeout) to close it server-side, while Django's Python-level connection
# object has no way to know that until the next query fails outright with
# "connection already closed". close_old_connections() actively probes and
# closes anything unusable, forcing a fresh connection on the very next
# query — this is the standard Django+Celery fix for exactly this failure,
# and it runs for both a real worker dispatch and Celery's eager (in-process)
# execution path, since task_prerun/task_postrun fire either way.
@task_prerun.connect
@task_postrun.connect
def _close_stale_db_connections(**kwargs):
    from django.db import close_old_connections
    close_old_connections()
