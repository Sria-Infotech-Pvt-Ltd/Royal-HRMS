# Make Celery app available as a module-level symbol so Django's app registry
# loads it early enough for @shared_task decorators to register correctly.
from .celery import app as celery_app  # noqa: F401

__all__ = ('celery_app',)
