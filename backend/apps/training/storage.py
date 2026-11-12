"""
Private storage for training files — reuses core.storage's authenticated
Cloudinary storage (nothing is ever public). Documents and thumbnails are
served through the API after an access check; uploaded videos are played
from a signed URL handed out only to users allowed to watch them.
"""
import time

import cloudinary.uploader
import cloudinary.utils
from django.utils.deconstruct import deconstructible

from core.storage import AuthenticatedRawMediaCloudinaryStorage, _short_upload_name, _tenant_schema


@deconstructible
class AuthenticatedVideoCloudinaryStorage(AuthenticatedRawMediaCloudinaryStorage):
    """Same as the raw authenticated storage, as a Cloudinary *video* resource
    (streamable, seekable). Large files go up in chunks."""
    RESOURCE_TYPE = 'video'

    def _upload(self, name, content):
        import os
        options = {
            'use_filename': True, 'resource_type': 'video', 'tags': self.TAG, 'type': 'authenticated',
            'chunk_size': 20 * 1024 * 1024,
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload_large(content, **options)

    def signed_playback_url(self, name, fmt: str = '') -> str:
        name = self._prepend_prefix(name)
        url, _options = cloudinary.utils.cloudinary_url(
            name, resource_type='video', type='authenticated', sign_url=True, secure=True,
            format=fmt or None, expires_at=int(time.time()) + 3600,
        )
        return url


def training_document_upload_path(instance, filename) -> str:
    return _short_upload_name(f'{_tenant_schema()}/training/docs', filename)


def training_video_upload_path(instance, filename) -> str:
    return _short_upload_name(f'{_tenant_schema()}/training/videos', filename)


def training_thumbnail_upload_path(instance, filename) -> str:
    return _short_upload_name(f'{_tenant_schema()}/training/thumbs', filename)
