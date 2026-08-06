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


class ProfilePhotoUploadSerializer(serializers.Serializer):
    """POST /api/employees/me/photo/ — exactly one image file per request."""

    photo = serializers.ImageField()

    def validate_photo(self, value):
        if not getattr(value, 'name', None):
            raise serializers.ValidationError('Uploaded file must have a name.')
        if value.content_type not in User.PROFILE_PHOTO_ALLOWED_MIME_TYPES:
            raise serializers.ValidationError('Only JPG, JPEG, and PNG files are allowed.')
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
