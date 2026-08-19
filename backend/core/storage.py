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
import time

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


def expense_receipt_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/expenses/receipts/{filename}'


def separation_request_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/separation_documents/{filename}'


def separation_document_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/separation_documents/{filename}'


def leave_document_upload_path(instance, filename) -> str:
    return f'{_tenant_schema()}/leave_documents/{filename}'
