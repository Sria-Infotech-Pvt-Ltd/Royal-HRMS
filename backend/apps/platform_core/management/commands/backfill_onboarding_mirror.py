from django.core.management.base import BaseCommand

from apps.platform_core import services_onboarding_sync


class Command(BaseCommand):
    help = 'One-shot sync of existing OnboardingFieldConfig/OnboardingSection rows onto the forms.v2 mirror (idempotent, safe to re-run).'

    def handle(self, *args, **options):
        result = services_onboarding_sync.backfill_all()
        self.stdout.write(self.style.SUCCESS(
            f'Backfill complete. Sections synced={result["sections_synced"]} Fields synced={result["fields_synced"]}'
        ))
