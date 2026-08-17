"""
Management command: migrate_files_to_cloudinary

Uploads all locally stored Document and EmailTemplateAttachment files to
Cloudinary, then updates the database record so future URL lookups resolve
to the Cloudinary CDN instead of the local /media/ path.

Usage:
    python manage.py migrate_files_to_cloudinary
    python manage.py migrate_files_to_cloudinary --dry-run
"""

import os

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.accounts.models import Document, EmailTemplateAttachment


def _is_local_path(name: str) -> bool:
    """Return True if the stored file name is a local path (not a Cloudinary public_id that starts with http)."""
    return bool(name) and not name.startswith(('http://', 'https://'))


class Command(BaseCommand):
    help = 'Migrate locally stored Document and EmailTemplateAttachment files to Cloudinary.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be migrated without making any changes.',
        )

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        media_root = settings.MEDIA_ROOT

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN -no files will be uploaded or deleted.\n'))

        totals = {'migrated': 0, 'skipped': 0, 'missing': 0, 'failed': 0}

        self._migrate_model(
            queryset   = Document.objects.all(),
            field_name = 'file',
            label_fn   = lambda obj: f'Document #{obj.pk} "{obj.title}"',
            media_root = media_root,
            dry_run    = dry_run,
            totals     = totals,
        )

        self._migrate_model(
            queryset   = EmailTemplateAttachment.objects.all(),
            field_name = 'file',
            label_fn   = lambda obj: f'Attachment #{obj.pk} "{obj.filename}"',
            media_root = media_root,
            dry_run    = dry_run,
            totals     = totals,
        )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Done.  Migrated: {totals['migrated']}  "
            f"Skipped (already on Cloudinary): {totals['skipped']}  "
            f"Missing local file: {totals['missing']}  "
            f"Failed: {totals['failed']}"
        ))

    def _migrate_model(self, queryset, field_name, label_fn, media_root, dry_run, totals):
        for obj in queryset:
            field_file = getattr(obj, field_name)
            label      = label_fn(obj)

            if not field_file or not field_file.name:
                totals['skipped'] += 1
                continue

            if not _is_local_path(field_file.name):
                self.stdout.write(f'  SKIP   {label} -already on Cloudinary')
                totals['skipped'] += 1
                continue

            # Some old records were saved with a leading "media/" prefix by mistake.
            # Strip it so we don't double-up MEDIA_ROOT + "media/...".
            clean_name = field_file.name
            if clean_name.startswith('media/') or clean_name.startswith('media\\'):
                clean_name = clean_name[6:]

            local_path = os.path.join(media_root, clean_name)
            if not os.path.exists(local_path):
                self.stdout.write(
                    self.style.WARNING(f'  MISS   {label} -local file not found: {local_path}')
                )
                totals['missing'] += 1
                continue

            basename = os.path.basename(local_path)
            self.stdout.write(f'  UPLOAD {label} -{field_file.name}')

            if dry_run:
                totals['migrated'] += 1
                continue

            try:
                with open(local_path, 'rb') as fh:
                    # save() calls the storage backend (Cloudinary), updates field_file.name,
                    # and persists the model row in one atomic step.
                    field_file.save(basename, File(fh), save=True)

                os.remove(local_path)
                self.stdout.write(self.style.SUCCESS('         OK uploaded & local file removed'))
                totals['migrated'] += 1

            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  FAIL   {label} -{exc}'))
                totals['failed'] += 1
