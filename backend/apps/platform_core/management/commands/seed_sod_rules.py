from django.core.management.base import BaseCommand

from apps.platform_core import services_sod


class Command(BaseCommand):
    help = 'Idempotently seed suggested (inactive) SoD rules (Task F.3). Owner must activate them explicitly.'

    def handle(self, *args, **options):
        result = services_sod.seed_suggested_rules()
        self.stdout.write(self.style.SUCCESS(
            f'SoD suggested rules seeded. Created={result["created"]} Unchanged={result["unchanged"]}'
        ))
