from django.core.management.base import BaseCommand

from apps.platform_core import event_types_registry


class Command(BaseCommand):
    help = 'Idempotently sync code-registered EventType rows (Task E.1).'

    def handle(self, *args, **options):
        result = event_types_registry.sync()
        self.stdout.write(self.style.SUCCESS(
            f'Event types synced. Created={result["created"]} Unchanged={result["unchanged"]}'
        ))
