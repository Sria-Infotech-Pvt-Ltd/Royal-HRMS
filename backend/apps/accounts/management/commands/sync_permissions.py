from django.core.management.base import BaseCommand

from apps.accounts import permissions_registry


class Command(BaseCommand):
    help = 'Idempotently sync entity-generated Permission rows (Task A.2) and the default permission templates.'

    def handle(self, *args, **options):
        result = permissions_registry.sync()
        self.stdout.write(self.style.SUCCESS(
            f'Permissions synced. Created={result["created"]} Unchanged={result["unchanged"]}'
        ))
        # After the permissions, so the templates can link to every codename they list (timesheet.approve is code-defined).
        templates = permissions_registry.sync_default_permission_templates()
        self.stdout.write(self.style.SUCCESS(
            f'Permission templates synced. Created={templates["created"]} Unchanged={templates["unchanged"]}'
        ))
