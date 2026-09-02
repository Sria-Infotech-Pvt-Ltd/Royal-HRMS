"""
Access-controlled ImageKit storage for sensitive per-employee documents
(expense receipts, separation documents, leave documents, email template
attachments, employee documents, custom-field files).

The project's global default storage (ImageKitStorage) uploads every file as
public — anyone with the URL can fetch it, no session/signature/expiry
required. AuthenticatedImageKitStorage fixes this for sensitive documents by
uploading with is_private_file=True and only ever handing out a short-lived
signed URL (mirrors the expiring-link pattern already used by
EmailTemplateAttachmentSerializer.get_url).

ImageKit's delete API takes a file_id, not a path — unlike Django's
Storage.delete(name), there's no delete-by-path endpoint. _resolve_file_id()
looks the file up by its exact name within its folder first.
"""
from __future__ import annotations

import logging
import os
import time

from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from imagekitio import ImageKit

logger = logging.getLogger(__name__)

SIGNED_URL_TTL_SECONDS = 7200  # 2 hours

# ImageKit's search/list index is eventually consistent — a file uploaded
# moments ago (e.g. replacing a profile photo right after first setting it)
# can briefly 404 out of assets.list() even though the upload itself already
# succeeded. Retried with backoff so delete() doesn't silently no-op and
# orphan the file on a fast upload-then-replace.
_RESOLVE_RETRY_DELAYS = (0, 0.5, 1.5)

_client: ImageKit | None = None


def _get_client() -> ImageKit:
    global _client
    if _client is None:
        _client = ImageKit(private_key=settings.IMAGEKIT_PRIVATE_KEY)
    return _client


def get_signed_url(name: str, ttl: int = SIGNED_URL_TTL_SECONDS) -> str:
    """Signed, expiring URL for a private file's stored path — shared by
    AuthenticatedImageKitStorage.url() and every view/serializer that mints
    its own signed link for a document (see apps.accounts.views/serializers)."""
    return _get_client().helper.build_url(
        url_endpoint=settings.IMAGEKIT_URL_ENDPOINT,
        src=f'/{name}',
        signed=True,
        expires_in=ttl,
    )


def _resolve_file_id(name: str) -> str | None:
    # Django's Storage.generate_filename() runs `name` through
    # os.path.normpath() before it ever reaches here — on Windows that turns
    # the forward-slash paths every upload_to function below returns (e.g.
    # "documents/2026/09/file.csv") into backslash paths, which ImageKit's
    # API rejects outright ("invalid value for folder parameter"). ImageKit
    # paths are always forward-slash, on every OS — normalize unconditionally
    # rather than only on Windows, so this can't regress if it's ever run
    # somewhere the separator handling differs.
    name = name.replace('\\', '/')
    folder = os.path.dirname(name)
    file_name = os.path.basename(name)
    client = _get_client()
    for delay in _RESOLVE_RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        results = client.assets.list(
            path=f'/{folder}' if folder else '/',
            search_query=f'name="{file_name}"',
            type='file',
            limit=1,
        )
        if results:
            return results[0].file_id
    return None


@deconstructible
class ImageKitStorage(Storage):
    """Public-by-default — matches how RawMediaCloudinaryStorage behaved for
    profile photos / company logos, where a plain permanent URL is needed for
    long-lived <img> caching."""

    is_private_file = False

    def _save(self, name, content):
        # See _resolve_file_id()'s comment above — same normpath-on-Windows
        # issue applies here, at the point of upload rather than delete.
        name = name.replace('\\', '/')
        folder = os.path.dirname(name)
        file_name = os.path.basename(name)
        content.seek(0)
        response = _get_client().files.upload(
            file=content.read(),
            file_name=file_name,
            folder=f'/{folder}' if folder else '/',
            is_private_file=self.is_private_file,
        )
        return response.file_path.lstrip('/')

    def exists(self, name):
        # ImageKit assigns a unique filename on collision itself
        # (use_unique_file_name defaults to True) — Django doesn't need to
        # pre-check, matching how the Cloudinary backend behaved.
        return False

    def get_available_name(self, name, max_length=None):
        return name

    def delete(self, name):
        file_id = _resolve_file_id(name)
        if file_id:
            _get_client().files.delete(file_id)
        else:
            logger.warning('Could not resolve an ImageKit file_id for %r — nothing deleted (orphaned on ImageKit).', name)

    def url(self, name):
        return _get_client().helper.build_url(
            url_endpoint=settings.IMAGEKIT_URL_ENDPOINT,
            src=f'/{name}',
        )

    def size(self, name):
        raise NotImplementedError('ImageKitStorage does not support size() — not needed anywhere in this codebase.')

    def _open(self, name, mode='rb'):
        raise NotImplementedError('ImageKitStorage does not support reading files back into Django — use .url() to fetch them.')


class AuthenticatedImageKitStorage(ImageKitStorage):
    """Every upload is stored with is_private_file=True — the plain
    ik.imagekit.io/.../name URL 401s for these; only a freshly generated
    signed URL from url() below can fetch them."""

    is_private_file = True

    def url(self, name):
        return get_signed_url(name)


# Historical migrations (accounts 0079-0082, hrms 0023) reference this name
# directly in their field= kwargs — Django imports every migration to build
# its graph, even already-applied ones, so this alias must stay importable
# until those migrations are squashed. Not dead code despite the name.
AuthenticatedRawMediaCloudinaryStorage = AuthenticatedImageKitStorage


def expense_receipt_upload_path(instance, filename) -> str:
    return f'expenses/receipts/{filename}'


def separation_request_upload_path(instance, filename) -> str:
    return f'separation_documents/{filename}'


def separation_document_upload_path(instance, filename) -> str:
    return f'separation_documents/{filename}'


def leave_document_upload_path(instance, filename) -> str:
    return f'leave_documents/{filename}'


def document_center_upload_path(instance, filename) -> str:
    # Matches the year/month partitioning the old upload_to='documents/%Y/%m/'
    # string gave for free — a callable upload_to doesn't get Django's
    # automatic strftime substitution, so it's done by hand here.
    from django.utils import timezone
    stamp = timezone.now().strftime('%Y/%m')
    return f'documents/{stamp}/{filename}'


def email_template_attachment_upload_path(instance, filename) -> str:
    return f'email_template_attachments/{filename}'


def profile_photo_upload_path(instance, filename) -> str:
    # Public-by-design (rendered as a plain <img src>, shown in employee
    # directories) — unlike the categories above this deliberately keeps
    # the default public storage rather than AuthenticatedImageKitStorage,
    # since a signed/expiring URL would break long-lived <img> caching.
    return f'profile_photos/{filename}'


def company_logo_upload_path(instance, filename) -> str:
    # Same reasoning as profile_photo_upload_path — a company logo is
    # intentionally public (shown pre-login) via PublicCompanyBrandingView.
    return f'company/{filename}'
