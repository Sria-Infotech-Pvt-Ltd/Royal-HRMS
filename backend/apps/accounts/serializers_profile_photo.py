"""
Serializer for the self-service profile photo upload.

A plain displayable image (shown in the sidebar, header, and Profile page)
uploaded either from the device or captured live via the browser camera —
never a face-embedding vector. Unrelated to apps.attendance's face-ID
verification feature, which stores a numeric descriptor, never an image.
"""
from __future__ import annotations

import os

from rest_framework import serializers

from apps.accounts.models import User
from core.file_validation import validate_file_content as _validate_file_content


class ProfilePhotoUploadSerializer(serializers.Serializer):
    """POST /api/employees/me/photo/ — exactly one image file per request."""

    # Note: DRF's ImageField already opens the upload with Pillow to confirm
    # it's a genuinely decodable image before this validator even runs — a
    # renamed non-image file is already rejected by the field itself. The
    # magic-byte check below is for defense-in-depth/consistency with every
    # other upload validator in the project, not the primary guard here.
    photo = serializers.ImageField()

    def validate_photo(self, value):
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.content_type not in User.PROFILE_PHOTO_ALLOWED_MIME_TYPES:
            raise serializers.ValidationError('Only JPG, JPEG, and PNG files are allowed.')
        content_error = _validate_file_content(value, value.content_type)
        if content_error:
            raise serializers.ValidationError(content_error)
        if value.size < User.PROFILE_PHOTO_MIN_SIZE:
            raise serializers.ValidationError(
                f'Image is too small ({value.size / 1024:.0f} KB). Minimum size is 100 KB.'
            )
        if value.size > User.PROFILE_PHOTO_MAX_SIZE:
            raise serializers.ValidationError(
                f'Image is too large ({value.size / 1024:.0f} KB). Maximum size is 200 KB.'
            )
        value.name = os.path.basename(value.name).strip()
        return value
