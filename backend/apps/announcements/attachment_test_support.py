"""Shared helpers for the announcement attachment and e-mail tests (not a test module itself).

Real image and PDF bytes are generated in memory, so the validators see genuine files. Storage is replaced by an in-memory fake:
these tests prove OUR code (validation, authorisation, rendering), not that ImageKit or SMTP work - that needs a real
integration run with real credentials.
"""
from __future__ import annotations

import io
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User

LIST_URL = '/api/announcements/'
SIGNED_PREFIX = 'https://signed.example/'
_seq = [0]


def unique(prefix: str) -> str:
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def image_bytes(fmt: str = 'PNG', size: tuple[int, int] = (40, 30), color=(200, 30, 30), mode: str = 'RGB') -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, format=fmt)
    return out.getvalue()


def pdf_bytes(extra: int = 0) -> bytes:
    return b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n' + b'%padding\n' * extra + b'%%EOF\n'


def upload_image(name: str = 'photo.png', fmt: str = 'PNG', content_type: str = 'image/png', **kwargs) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, image_bytes(fmt, **kwargs), content_type=content_type)


def upload_pdf(name: str = 'policy.pdf', extra: int = 0) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, pdf_bytes(extra), content_type='application/pdf')


def make_employee(**extra) -> User:
    user = make_user(f'{unique("emp")}@example.com', employee_id=unique('ANN'), **extra)
    User.objects.filter(pk=user.pk).update(onboarding_status='complete')
    user.refresh_from_db()
    return user


def make_poster(**extra) -> User:
    role = make_role(unique('poster'), permission_codenames=['announcements.create', 'announcements.edit', 'announcements.delete'])
    user = make_user(f'{unique("poster")}@example.com', role=role, employee_id=unique('ANN'), **extra)
    User.objects.filter(pk=user.pk).update(onboarding_status='complete')
    user.refresh_from_db()
    return user


class FakeStorageMixin:
    """Replaces the private ImageKit storage with a dictionary for the length of each test."""

    def setUp(self):
        super().setUp()
        self.stored: dict[str, bytes] = {}
        self.deleted: list[str] = []

        def fake_save(storage, name, content):
            name = name.replace('\\', '/')
            content.seek(0)
            self.stored[name] = content.read()
            return name

        def fake_delete(storage, name):
            self.deleted.append(name)
            self.stored.pop(name, None)

        patches = [
            mock.patch('core.storage.ImageKitStorage._save', fake_save),
            mock.patch('core.storage.ImageKitStorage.delete', fake_delete),
            mock.patch('core.storage.AuthenticatedImageKitStorage.url', lambda storage, name: f'{SIGNED_PREFIX}{name}?sig=2h'),
            mock.patch('apps.announcements.services_attachments.get_signed_url', lambda name, ttl=0: f'{SIGNED_PREFIX}{name}?sig={ttl}'),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
