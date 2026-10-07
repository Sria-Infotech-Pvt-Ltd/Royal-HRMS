"""
Phase 5A Task D.1 — seeds the India IdentityDocumentType pack. Every
value is marked `is_verified_format=False` ("verify before go-live" per
the task's own instruction for anything encoding a legal format) except
where the regex is genuinely well-established (PAN's format is a public,
stable government spec).
"""
from django.core.management.base import BaseCommand

INDIA_DOCUMENT_TYPES = [
    {'code': 'PAN', 'label': 'PAN', 'number_regex': r'^[A-Z]{5}[0-9]{4}[A-Z]$', 'unique_scope': 'global', 'normalisation': 'uppercase_strip_spaces', 'is_verified_format': True},
    {'code': 'AADHAAR', 'label': 'Aadhaar', 'number_regex': r'^\d{12}$', 'unique_scope': 'global', 'normalisation': 'strip_spaces', 'is_verified_format': False},
    {'code': 'UAN', 'label': 'UAN', 'number_regex': r'^\d{12}$', 'unique_scope': 'global', 'normalisation': 'strip_spaces', 'is_verified_format': False},
    {'code': 'ESI_NUMBER', 'label': 'ESI Number', 'number_regex': '', 'unique_scope': 'global', 'normalisation': 'strip_spaces', 'is_verified_format': False},
    {'code': 'PF_NUMBER', 'label': 'PF Number', 'number_regex': '', 'unique_scope': 'global', 'normalisation': 'strip_spaces', 'is_verified_format': False},
    {'code': 'PASSPORT', 'label': 'Passport', 'number_regex': r'^[A-Z][0-9]{7}$', 'unique_scope': 'none', 'normalisation': 'uppercase_strip_spaces', 'has_expiry': True, 'is_verified_format': False},
    {'code': 'VOTER_ID', 'label': 'Voter ID', 'number_regex': '', 'unique_scope': 'none', 'normalisation': 'uppercase_strip_spaces', 'is_verified_format': False},
    {'code': 'DRIVING_LICENCE', 'label': 'Driving Licence', 'number_regex': '', 'unique_scope': 'none', 'normalisation': 'uppercase_strip_spaces', 'has_expiry': True, 'is_verified_format': False},
    {'code': 'DISABILITY_CERTIFICATE', 'label': 'Disability Certificate', 'number_regex': '', 'unique_scope': 'none', 'normalisation': 'strip_spaces', 'is_sensitive': False, 'is_verified_format': False},
]


class Command(BaseCommand):
    help = 'Idempotently seed the India IdentityDocumentType pack (Phase 5A Task D.1).'

    def handle(self, *args, **options):
        from apps.accounts.models_identity_bank import IdentityDocumentType
        from apps.platform_core.models import Country

        india, _ = Country.objects.get_or_create(
            iso2='IN', defaults={'iso3': 'IND', 'name': 'India'},
        )
        created = unchanged = 0
        for spec in INDIA_DOCUMENT_TYPES:
            _, was_created = IdentityDocumentType.objects.get_or_create(
                code=spec['code'],
                defaults={
                    'country': india, 'label': spec['label'], 'number_regex': spec['number_regex'],
                    'unique_scope': spec['unique_scope'], 'normalisation': spec['normalisation'],
                    'has_expiry': spec.get('has_expiry', False), 'is_sensitive': spec.get('is_sensitive', True),
                    'requires_attachment': True, 'is_verified_format': spec.get('is_verified_format', False),
                },
            )
            created += was_created
            unchanged += not was_created
        self.stdout.write(self.style.SUCCESS(f'Identity document types seeded. Created={created} Unchanged={unchanged}'))
