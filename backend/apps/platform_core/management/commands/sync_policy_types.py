from django.core.management.base import BaseCommand

from apps.platform_core import policy_types_registry


class Command(BaseCommand):
    help = 'Idempotently sync code-registered PolicyType rows (Task D.1).'

    def handle(self, *args, **options):
        result = policy_types_registry.sync()
        self.stdout.write(self.style.SUCCESS(
            f'Policy types synced. Created={result["created"]} Updated={result["updated"]} Unchanged={result["unchanged"]}'
        ))
