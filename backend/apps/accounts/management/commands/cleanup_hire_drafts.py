"""
One-off cleanup of leftover hire-wizard drafts (stale ones and ones that match someone who already is an employee).

    python manage.py cleanup_hire_drafts                      # dry run: only prints the list, changes nothing
    python manage.py cleanup_hire_drafts --apply --ids ID,ID  # discards exactly the drafts a person approved

Nothing is ever deleted from a list the command made itself: the person reads the dry-run output, picks the ids, and passes
them back. Discarding releases each draft's reserved employee number when that is safe and writes an audit entry.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import HireAction
from apps.accounts.services_hire_drafts import discard_draft, draft_expiry_days, existing_employee_match, find_stale_drafts


class Command(BaseCommand):
    help = 'List leftover hire drafts (dry run); discard only the ids you approve with --apply --ids.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actually discard the drafts named in --ids.')
        parser.add_argument('--ids', default='', help='Comma-separated draft ids approved for discarding.')

    def handle(self, *args, **options):
        if options['apply']:
            return self._apply(options['ids'])
        self._report()

    def _describe(self, draft: HireAction, reason: str) -> str:
        data = draft.draft_data or {}
        name = f'{data.get("first_name", "")} {data.get("last_name", "")}'.strip() or '(no name yet)'
        reserved = draft.reserved_employee_id or 'no number reserved'
        return f'{draft.id}  {name}  | {draft.position.title}  | {reserved}  | last touched {draft.updated_at:%Y-%m-%d}  | {reason}'

    def _report(self):
        listed = {}
        for draft in find_stale_drafts().select_related('position'):
            listed[draft.id] = (draft, f'stale (older than {draft_expiry_days()} days)')
        for draft in HireAction.objects.select_related('position').filter(status=HireAction.STATUS_DRAFT):
            reason = existing_employee_match(draft)
            if reason:
                previous = listed.get(draft.id)
                listed[draft.id] = (draft, f'{previous[1]}; {reason}' if previous else reason)
        if not listed:
            self.stdout.write('No leftover drafts found.')
            return
        self.stdout.write(f'{len(listed)} draft(s) are candidates (DRY RUN, nothing changed):')
        for draft, reason in listed.values():
            self.stdout.write('  ' + self._describe(draft, reason))
        self.stdout.write('To discard some of them: --apply --ids <id>,<id> (only the ids you approve).')

    def _apply(self, ids_raw: str):
        ids = [value.strip() for value in ids_raw.split(',') if value.strip()]
        if not ids:
            raise CommandError('--apply needs --ids with the draft ids a person approved. Run without --apply first for the list.')
        drafts = HireAction.objects.filter(pk__in=ids, status=HireAction.STATUS_DRAFT)
        missing = set(ids) - {str(draft.pk) for draft in drafts}
        if missing:
            raise CommandError(f'Not open drafts (nothing was changed): {", ".join(sorted(missing))}')
        for draft in drafts:
            is_released = discard_draft(draft, actor=None, reason='cleanup')
            self.stdout.write(f'Discarded {draft.id} (number released: {is_released}).')
