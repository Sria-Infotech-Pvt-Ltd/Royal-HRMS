"""
Celery application entry point for Royal HRMS.

Usage:
    Worker:  celery -A config worker -l info
    Beat:    celery -A config beat   -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    Or both: celery -A config worker -l info -B
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('hrms')

# Read Celery config from settings.py keys prefixed with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()
