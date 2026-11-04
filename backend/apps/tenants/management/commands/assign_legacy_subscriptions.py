"""
Put every existing company on a "Legacy / Enterprise" subscription that
keeps exactly the modules it has today. PREVIEW BY DEFAULT — nothing is
written unless --apply is passed.

  - Creates the internal LEGACY plan if missing (never public, not
    assignable by hand) with every module feature.
  - For each company without a subscription: modules it has switched off
    today stay off (recorded as removed_modules); the modules added with
    SaaS plans (documents, assets, wfh) are added, because those features
    were never gated before — so nothing a company can use today is lost.
  - No end date; source "legacy"; history entry per company.

Usage:
    python manage.py assign_legacy_subscriptions            # preview
    python manage.py assign_legacy_subscriptions --apply
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.tenants.models import ALL_MODULES, Client, CompanySubscription, SubscriptionPlan
from apps.tenants.modules import DISPLAY, FEATURES, LATE_GATED_MODULES, MODULE
from apps.tenants.subscriptions import assign_subscription, resolve_modules

LEGACY_CODE = 'legacy'


def legacy_plan(create: bool):
    plan = SubscriptionPlan.objects.filter(code=LEGACY_CODE).first()
    if plan is None and create:
        plan = SubscriptionPlan.objects.create(
            code=LEGACY_CODE, name='Legacy / Enterprise',
            description='Existing companies before SaaS plans — every module they already had.',
            features=[f['key'] for f in FEATURES if f['kind'] in (MODULE, DISPLAY)],
            status=SubscriptionPlan.STATUS_INACTIVE, is_public=False, is_legacy=True, display_order=999,
        )
    return plan


def plan_for(client: Client) -> dict:
    current = set(client.enabled_modules or [])
    gated_before = set(ALL_MODULES) - set(LATE_GATED_MODULES)
    removed = sorted(gated_before - current)
    features = [f['key'] for f in FEATURES if f['kind'] in (MODULE, DISPLAY)]
    after = resolve_modules(features, (), removed)
    return {'removed': removed, 'before': sorted(current), 'after': after,
            'lost': sorted(current - set(after)), 'added': sorted(set(after) - current)}


class Command(BaseCommand):
    help = 'Assign a Legacy / Enterprise subscription to every company that has none (preview unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the subscriptions (default: preview).')

    def handle(self, *args, **options):
        apply = options['apply']
        clients = list(Client.objects.exclude(schema_name='public').filter(subscription__isnull=True)
                       .order_by('company_code'))
        if not clients:
            self.stdout.write('Every company already has a subscription. Nothing to do.')
            return
        plan = legacy_plan(create=apply)
        for client in clients:
            p = plan_for(client)
            self.stdout.write(
                f'{client.company_code}: modules {len(p["before"])} -> {len(p["after"])}; '
                f'added {p["added"] or "-"}; kept off {p["removed"] or "-"}; lost {p["lost"] or "none"}'
            )
            if p['lost']:
                self.stdout.write(self.style.ERROR(f'  {client.company_code} would lose modules — skipped.'))
                continue
            if apply:
                assign_subscription(
                    client=client, plan=plan, starts_on=client.created_at.date() if client.created_at else date.today(),
                    ends_on=None, employee_count=None, source=CompanySubscription.SOURCE_LEGACY,
                    removed_modules=p['removed'], notes='Assigned by assign_legacy_subscriptions.',
                )
        if apply:
            self.stdout.write(self.style.SUCCESS(f'APPLIED to {len(clients)} company(ies).'))
        else:
            self.stdout.write(self.style.WARNING('PREVIEW ONLY — nothing written. Re-run with --apply.'))
