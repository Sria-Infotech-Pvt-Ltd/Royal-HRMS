"""
Serializer for the self-service profile photo upload.

A plain displayable image (shown in the sidebar, header, and Profile page)
uploaded either from the device or captured live via the browser camera —
never a face-embedding vector. Unrelated to apps.attendance's face-ID
verification feature, which stores a numeric descriptor, never an image.
"""
from __future__ import annotations

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image
from rest_framework import serializers

from apps.accounts.models import User
from core.file_validation import validate_file_content as _validate_file_content

# JPEG quality steps tried, highest first, when compressing an oversized
# upload down to PROFILE_PHOTO_MAX_SIZE — most phone/camera photos (several
# MB, well over the 200 KB ceiling) fit within the first couple of steps;
# only very high-resolution originals ever need the resize-and-retry
# fallback in _fit_to_size_band below.
_COMPRESS_QUALITIES = (85, 75, 65, 55, 45, 35, 25)
# Never resize a photo's shorter edge below this — well above what an ID
# card/report thumbnail actually needs, so resizing only kicks in for
# genuinely huge originals, never degrades a normal selfie into mush.
_MIN_EDGE_PX = 300


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)
    return buf.getvalue()


def _fit_to_size_band(image_bytes: bytes, min_bytes: int, max_bytes: int) -> bytes:
    """Re-encodes `image_bytes` as JPEG so its size lands inside
    [min_bytes, max_bytes] wherever that's achievable without inventing
    data: compresses/resizes a too-large upload down, or re-encodes a
    too-small one at max quality (usually enough to push a genuine photo
    back over the floor). If it still doesn't fit either bound, returns the
    best attempt rather than blocking the upload outright — the whole point
    is "make a reasonable photo work", not enforce an exact byte count."""
    with Image.open(BytesIO(image_bytes)) as img:
        working = img.convert('RGB')
        data = _encode_jpeg(working, 90)

        if len(data) > max_bytes:
            for quality in _COMPRESS_QUALITIES:
                data = _encode_jpeg(working, quality)
                if len(data) <= max_bytes:
                    break
            # Still too large even at the lowest quality step — the
            # resolution itself is the problem, not just JPEG quality.
            # Scale down and retry until it fits, or until shrinking
            # further would drop below _MIN_EDGE_PX.
            while len(data) > max_bytes and min(working.size) > _MIN_EDGE_PX:
                working = working.resize(
                    (max(1, int(working.width * 0.85)), max(1, int(working.height * 0.85))),
                    Image.LANCZOS,
                )
                data = _encode_jpeg(working, 70)
        elif len(data) < min_bytes:
            data = _encode_jpeg(working, 95)

    return data


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

        # Rather than rejecting an upload for landing outside the
        # [PROFILE_PHOTO_MIN_SIZE, PROFILE_PHOTO_MAX_SIZE] band — the common
        # case is a modern phone/camera photo at several MB, well over the
        # 200 KB ceiling — re-encode/resize it to fit that band instead.
        # "Pick any reasonable photo, it just works" matters more here than
        # enforcing an exact byte range on the user.
        value.seek(0)
        base_name = os.path.splitext(os.path.basename(value.name).strip())[0]
        try:
            fitted = _fit_to_size_band(
                value.read(), User.PROFILE_PHOTO_MIN_SIZE, User.PROFILE_PHOTO_MAX_SIZE,
            )
        except Exception:
            # Decodable-but-unprocessable edge case (e.g. an exotic color
            # mode Pillow can open but not convert) — fall back to the
            # original bytes rather than blocking the upload outright.
            value.seek(0)
            fitted = value.read()

        new_file = ContentFile(fitted, name=f'{base_name}.jpg')
        new_file.content_type = 'image/jpeg'
        return new_file
