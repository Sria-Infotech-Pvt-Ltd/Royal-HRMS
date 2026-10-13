"""
Access-controlled, tenant-scoped Cloudinary storage for sensitive per-employee
documents (expense receipts, separation documents, leave documents).

Two independent gaps existed before this:

1. The project's global DEFAULT_FILE_STORAGE (RawMediaCloudinaryStorage)
   never passes `type=` to Cloudinary, so every upload defaults to
   `type='upload'` — a permanently public resource. Anyone who obtains or
   guesses the URL can fetch the file with no session, no signature, no
   expiry, regardless of which company's data it belongs to.
2. `upload_to='expenses/receipts/'` (and the separation/leave equivalents)
   are static, tenant-agnostic folders shared by every company on this
   single Cloudinary account — nothing in the stored path identifies which
   tenant a file belongs to.

AuthenticatedRawMediaCloudinaryStorage fixes (1) by uploading with
`type='authenticated'` and only ever handing out a short-lived signed URL
(mirrors the expiring-link pattern already used by
EmailTemplateAttachmentSerializer.get_url). tenant scoped upload_to
functions below fix (2) by prefixing the stored path with the active
schema name, the same way apps.accounts.models._employee_doc_path already
namespaces EmployeeDocument by employee_id.
"""
import os
import re
import time
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from cloudinary_storage.storage import RawMediaCloudinaryStorage
from django.db import connection

SIGNED_URL_TTL_SECONDS = 7200  # 2 hours


class AuthenticatedRawMediaCloudinaryStorage(RawMediaCloudinaryStorage):
    """
    Same as RawMediaCloudinaryStorage but every upload is stored as
    type='authenticated'. The bare, unsigned res.cloudinary.com/.../raw/
    upload/... URL that a plain RawMediaCloudinaryStorage would build for
    the same public_id will 401 for these files — only a freshly generated
    signed URL from _get_url() below can fetch them.
    """

    def _upload(self, name, content):
        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'tags': self.TAG,
            'type': 'authenticated',
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def delete(self, name):
        response = cloudinary.uploader.destroy(
            name,
            invalidate=True,
            resource_type=self._get_resource_type(name),
            type='authenticated',
        )
        return response['result'] == 'ok'

    def _get_url(self, name):
        name = self._prepend_prefix(name)
        url, _options = cloudinary.utils.cloudinary_url(
            name,
            resource_type=self._get_resource_type(name),
            type='authenticated',
            sign_url=True,
            secure=True,
            expires_at=int(time.time()) + SIGNED_URL_TTL_SECONDS,
        )
        return url


def _tenant_schema() -> str:
    return getattr(connection, 'schema_name', None) or 'public'


# Stored names must fit the ImageField's varchar(100). The default Cloudinary
# storage saves the public_id it gets back, which is longer than the path
# built here: it prepends the 'media/' prefix (MEDIA_URL) and appends a
# 7-character '_xxxxxx' uniqueness suffix. So the original filename is never
# used — only its extension — and the random part shrinks to fit. Tenant
# schemas are 'tenant_' + a company_code of at most 50 characters (<= 57),
# which leaves at least 9 random hex characters even under 'profile_photos'.
_IMAGE_NAME_MAX_LENGTH       = 100
_CLOUDINARY_NAME_OVERHEAD    = len('media/') + len('_xxxxxx')
_UPLOAD_EXTENSION_RE         = re.compile(r'\.[a-z0-9]{1,5}')


def _short_upload_name(directory: str, filename: str) -> str:
    ext = os.path.splitext(filename or '')[1].lower()
    if not _UPLOAD_EXTENSION_RE.fullmatch(ext):
        ext = ''
    room = _IMAGE_NAME_MAX_LENGTH - _CLOUDINARY_NAME_OVERHEAD - len(directory) - 1 - len(ext)
    return f'{directory}/{uuid.uuid4().hex[:max(8, min(16, room))]}{ext}'


def expense_receipt_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/expenses/receipts/{filename}'


def separation_request_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/separation_documents/{filename}'


def separation_document_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/separation_documents/{filename}'


def leave_document_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/leave_documents/{filename}'


def document_center_upload_path(instance, filename) -> str:
    # Matches the year/month partitioning the old upload_to='documents/%Y/%m/'
    # string gave for free — a callable upload_to doesn't get Django's
    # automatic strftime substitution, so it's done by hand here.
    from django.utils import timezone
    stamp = timezone.now().strftime('%Y/%m')
    return f'{_tenant_schema()}/documents/{stamp}/{filename}'


def email_template_attachment_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/email_template_attachments/{filename}'


def profile_photo_upload_path(instance, filename) -> str:
    # Public-by-design (rendered as a plain <img src>, shown in employee
    # directories) — unlike the categories above this deliberately keeps
    # the default public storage rather than AuthenticatedRawMediaCloudinaryStorage,
    # since a signed/expiring URL would break long-lived <img> caching. Only
    # the path gets tenant-scoped, closing the cross-tenant path-collision
    # gap without changing who can view a photo.
    return _short_upload_name(f'{_tenant_schema()}/profile_photos', filename)


def company_logo_upload_path(instance, filename) -> str:
    # Same reasoning as profile_photo_upload_path — a company logo is
    # intentionally public (shown pre-login) via PublicCompanyBrandingView;
    # only the path needs tenant-scoping.
    return _short_upload_name(f'{_tenant_schema()}/company', filename)


def id_card_upload_path(instance, filename) -> str:
    # ID card reference PDF and authorised-signature image — private
    # (AuthenticatedRawMediaCloudinaryStorage), served only via signed URLs.
    return f'{_tenant_schema()}/id_card/{filename}'
