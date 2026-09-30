"""
Generates a new ExternalAPIKey for another internal system to call this
app's external/* endpoints — see authentication_external.py for how it's
verified. The raw key is printed to the terminal exactly once (this app
only ever stores its SHA-256 hash, never the raw value) — copy it
immediately, since there is no way to retrieve it again afterward. If
it's lost, generate a new key and revoke the old one.
"""
import hashlib
import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import ExternalAPIKey


class Command(BaseCommand):
    help = 'Generate a new API key for an external system (e.g. project_budget_tool).'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Identifier for the calling system, e.g. project_budget_tool')

    def handle(self, *args, **options):
        name = options['name'].strip()
        if not name:
            raise CommandError('name is required.')
        if ExternalAPIKey.objects.filter(name=name).exists():
            raise CommandError(
                f'A key named "{name}" already exists. Revoke it first (set is_active=False) '
                'before generating a replacement, so only one is ever active per system.'
            )

        raw_key = f'eak_{secrets.token_hex(32)}'
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        ExternalAPIKey.objects.create(name=name, key_hash=key_hash)

        self.stdout.write(self.style.SUCCESS(f'API key created for "{name}".'))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Copy this now — it will never be shown again:'))
        self.stdout.write(raw_key)
        self.stdout.write('')
        self.stdout.write('Send it in every request as the X-API-Key header.')
