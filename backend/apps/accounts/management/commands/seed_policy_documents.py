"""
Management command: seed_policy_documents

Idempotently creates/updates the 4 company policy documents shown on the ESS
"Policies & assets" tab's "Company policies" card (Document Center rows with
category=Document.CATEGORY_POLICY). Uses get_or_create keyed on title so
re-running this command never creates duplicates — it only backfills
version/effective_date on the existing rows if they already exist.

Run:  python manage.py seed_policy_documents
"""
from __future__ import annotations

import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Document, User

# (title, version, effective_date, description)
POLICY_DOCUMENTS = [
    (
        'Leave & holidays policy', '3.2', datetime.date(2026, 4, 1),
        'Leave entitlements, carry-forward rules, and the annual holiday calendar.',
    ),
    (
        'Attendance & remote work', '2.4', datetime.date(2026, 6, 1),
        'Punch-in expectations, correction workflow, and remote/hybrid work guidelines.',
    ),
    (
        'Travel & expense policy', '2.1', datetime.date(2026, 1, 1),
        'Approved travel classes, per-diem limits, and expense claim documentation rules.',
    ),
    (
        'Code of conduct', '4.0', datetime.date(2026, 4, 1),
        'Workplace conduct, anti-harassment, and disciplinary standards for all employees.',
    ),
]


class Command(BaseCommand):
    help = 'Idempotently seeds/updates the 4 real ESS policy documents (version + effective_date).'

    @transaction.atomic
    def handle(self, *args, **options):
        uploader = User.objects.filter(is_superuser=True).order_by('id').first()
        for title, version, effective_date, description in POLICY_DOCUMENTS:
            doc = Document.objects.filter(title__iexact=title).first()
            if doc is None:
                doc = self._create_document(title, version, effective_date, description, uploader)
                self.stdout.write(f'Created policy document "{title}" (v{version}).')
            else:
                doc.version = version
                doc.effective_date = effective_date
                doc.category = Document.CATEGORY_POLICY
                doc.save(update_fields=['version', 'effective_date', 'category'])
                self.stdout.write(f'Updated policy document "{title}" (v{version}).')

    def _create_document(self, title, version, effective_date, description, uploader):
        file_name = title.lower().replace(' ', '-').replace('&', 'and') + '.pdf'
        # Minimal, valid, single-page PDF so the stored file opens cleanly —
        # actual policy text is out of scope for this backfill.
        content = _MINIMAL_PDF_BYTES
        doc = Document(
            title=title,
            description=description,
            category=Document.CATEGORY_POLICY,
            version=version,
            effective_date=effective_date,
            file_name=file_name,
            file_type='PDF',
            file_size=len(content),
            uploaded_by=uploader,
            is_active=True,
        )
        doc.file.save(file_name, ContentFile(content), save=False)
        doc.save()
        return doc


_MINIMAL_PDF_BYTES = (
    b'%PDF-1.4\n'
    b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
    b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
    b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n'
    b'xref\n0 4\n0000000000 65535 f \n'
    b'trailer<</Size 4/Root 1 0 R>>\n'
    b'startxref\n0\n%%EOF'
)
