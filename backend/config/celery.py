"""
Celery application entry point for Royal HRMS.

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

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('hrms')

# Read Celery config from settings.py keys prefixed with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()
