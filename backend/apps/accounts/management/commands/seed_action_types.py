"""
Phase 5B Task E.1 — seeds the action types this phase actually built
working effect handlers for: Confirmation (probation -> confirmed) and
Promotion/Transfer (both a placement change, differing only in reason/
category — a real transfer-by-position-change, unlike the legacy
PromotionRecord's text-only audit log). The prompt's full built-in list
(Hire, Rehire, Probation Extension, Demotion, Suspension, Reinstatement,
Long Leave, Separation, Death in Service...) is NOT seeded here — each
would need its own effect handler (or, for Hire/Separation, a real
integration with the existing wizard/separation module) that this pass
does not build. See PHASE5B_REPORT.md.
"""
from django.core.management.base import BaseCommand

ACTION_TYPES = [
    {
        'code': 'CONFIRMATION', 'name': 'Confirmation', 'category': 'status',
        'effects': [{'handler': 'set_employment_status', 'status': 'confirmed'}],
        'allowed_from_statuses': ['probation'], 'resulting_status': 'confirmed',
        'allow_backdating': True, 'max_backdate_days': 30, 'allow_future_dating': False,
    },
    {
        'code': 'PROMOTION', 'name': 'Promotion', 'category': 'movement',
        'effects': [{'handler': 'set_placement'}],
        'allowed_from_statuses': [], 'resulting_status': '',
        'allow_backdating': True, 'max_backdate_days': 90, 'allow_future_dating': True,
    },
    {
        'code': 'TRANSFER_POSITION', 'name': 'Transfer (Org Unit / Position)', 'category': 'movement',
        'effects': [{'handler': 'set_placement'}],
        'allowed_from_statuses': [], 'resulting_status': '',
        'allow_backdating': True, 'max_backdate_days': 30, 'allow_future_dating': True,
    },
]


class Command(BaseCommand):
    help = 'Idempotently seed the built-in action types with real effect handlers (Phase 5B Task E.1).'

    def handle(self, *args, **options):
        from apps.accounts.models_actions import ActionType

        created = unchanged = 0
        for spec in ACTION_TYPES:
            _, was_created = ActionType.objects.get_or_create(
                code=spec['code'], defaults={**{k: v for k, v in spec.items() if k != 'code'}, 'is_system': True},
            )
            created += was_created
            unchanged += not was_created
        self.stdout.write(self.style.SUCCESS(f'Action types seeded. Created={created} Unchanged={unchanged}'))
