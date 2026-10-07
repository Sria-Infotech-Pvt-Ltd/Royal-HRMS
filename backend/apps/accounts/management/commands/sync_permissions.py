from django.core.management.base import BaseCommand

from apps.accounts import permissions_registry


class Command(BaseCommand):
    help = 'Idempotently sync entity-generated Permission rows (Task A.2).'

    def handle(self, *args, **options):
        result = permissions_registry.sync()
        self.stdout.write(self.style.SUCCESS(
            f'Permissions synced. Created={result["created"]} Unchanged={result["unchanged"]}'
        ))
