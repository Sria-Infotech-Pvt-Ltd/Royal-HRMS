"""
Merge org units from a mapping the business has approved. Dry run unless --apply.

    python manage.py merge_org_units --mapping approved.json            # preview only
    python manage.py merge_org_units --mapping approved.json --apply    # do it

approved.json:  [{"source": "<unit id or exact name>", "target": "<unit id or exact name>"}, ...]

Each source's positions (and so its employees), child units and chief seat move to the target; the source is deactivated, not
deleted, and one audit entry per merged unit is written. The whole mapping is validated first and applied in one transaction.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services_org_units import OrgUnitMergeError, merge_org_units


class Command(BaseCommand):
    help = 'Merge org units from an approved mapping (dry run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument('--mapping', required=True, help='JSON file with the approved source -> target pairs.')
        parser.add_argument('--apply', action='store_true', help='Actually merge (default is a dry run).')

    def handle(self, *args, **options):
        try:
            with open(options['mapping'], encoding='utf-8') as handle:
                pairs = [(item['source'], item['target']) for item in json.load(handle)]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError(f'Could not read the mapping file: {exc}') from exc
        try:
            steps = merge_org_units(pairs, actor=None, dry_run=not options['apply'])
        except OrgUnitMergeError as exc:
            raise CommandError(f'{exc} Nothing was changed.') from exc
        label = 'MERGED' if options['apply'] else 'DRY RUN, would merge'
        for step in steps:
            self.stdout.write(f'{label}: {step.summary()}')
        if not options['apply']:
            self.stdout.write('Nothing was changed. Re-run with --apply once the list above is approved.')
