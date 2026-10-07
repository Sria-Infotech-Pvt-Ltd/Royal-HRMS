from django.core.management.base import BaseCommand

from apps.platform_core import job_types_registry


class Command(BaseCommand):
    help = 'Idempotently sync code-registered JobType rows (Task G.2).'

    def handle(self, *args, **options):
        result = job_types_registry.sync()
        self.stdout.write(self.style.SUCCESS(
            f'Job types synced. Created={result["created"]} Unchanged={result["unchanged"]}'
        ))
