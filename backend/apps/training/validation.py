"""
Upload and link validation for training materials.

Files are checked by their actual content (magic bytes / container
structure), not their name or declared type. External video links are only
ever embedded or opened by the employee's browser — the server never
fetches them, so there is no server-side request to forge (SSRF) — and are
still restricted to https, public host names and known providers.
"""
from __future__ import annotations

import io
import ipaddress
import os
import re
import zipfile
from urllib.parse import parse_qs, urlparse

from django.conf import settings

MB = 1024 * 1024


def _limit(name: str, default_mb: int) -> int:
    return int(getattr(settings, name, default_mb)) * MB


# Browser uploads pass through the Next.js /api proxy, which forwards at most
# 10 MB of a request body (next.config proxyClientMaxBodySize) — the defaults
# stay under it. Larger files need that limit and nginx client_max_body_size
# raised first, then these settings. Long videos: use a YouTube / Vimeo link.
DOC_MAX_BYTES = _limit('TRAINING_DOCUMENT_MAX_MB', 9)
VIDEO_MAX_BYTES = _limit('TRAINING_VIDEO_MAX_MB', 9)
THUMB_MAX_BYTES = _limit('TRAINING_THUMBNAIL_MAX_MB', 2)

DOCUMENT_FORMATS = {
    '.pdf': 'pdf',
    '.pptx': 'pptx',
    '.docx': 'docx',
}
VIDEO_FORMATS = {
    '.mp4': 'mp4',
    '.m4v': 'mp4',
    '.webm': 'webm',
}
CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'mp4': 'video/mp4',
    'webm': 'video/webm',
    'png': 'image/png',
    'jpeg': 'image/jpeg',
}
_OOXML_MAIN = {'pptx': 'ppt/', 'docx': 'word/'}


class TrainingValidationError(Exception):
    def __init__(self, message: str, field: str = ''):
        super().__init__(message)
        self.field = field


def _ext(upload) -> str:
    return os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()


def _size(upload, max_bytes: int, label: str, field: str) -> None:
    size = getattr(upload, 'size', None) or 0
    if size <= 0:
        raise TrainingValidationError(f'The {label} is empty.', field)
    if size > max_bytes:
        raise TrainingValidationError(f'The {label} must be {max_bytes // MB} MB or smaller.', field)


def _head(upload, n: int = 4096) -> bytes:
    upload.seek(0)
    data = upload.read(n)
    upload.seek(0)
    return data


def detect_document_format(upload) -> str | None:
    head = _head(upload, 8)
    if head.startswith(b'%PDF-'):
        return 'pdf'
    if head.startswith(b'PK\x03\x04'):
        try:
            upload.seek(0)
            with zipfile.ZipFile(upload) as zf:
                names = zf.namelist()
        except zipfile.BadZipFile:
            return None
        finally:
            upload.seek(0)
        if '[Content_Types].xml' not in names:
            return None
        for fmt, folder in _OOXML_MAIN.items():
            if any(n.startswith(folder) for n in names):
                return fmt
    return None


def validate_document(upload) -> str:
    """PDF, PowerPoint (.pptx) or Word (.docx); returns the format."""
    if upload is None:
        raise TrainingValidationError('Choose a file to upload.', 'file')
    _size(upload, DOC_MAX_BYTES, 'document', 'file')
    expected = DOCUMENT_FORMATS.get(_ext(upload))
    if expected is None:
        raise TrainingValidationError('Upload a PDF, PowerPoint (.pptx) or Word (.docx) file.', 'file')
    actual = detect_document_format(upload)
    if actual != expected:
        raise TrainingValidationError('The file content does not match its type, or the file is damaged.', 'file')
    if actual == 'pdf':
        upload.seek(max(0, upload.size - 2048))
        tail = upload.read()
        upload.seek(0)
        if b'%%EOF' not in tail:
            raise TrainingValidationError('The PDF file is incomplete or damaged.', 'file')
    return actual


def detect_video_format(head: bytes) -> str | None:
    if len(head) >= 12 and head[4:8] == b'ftyp':
        return 'mp4'
    if head.startswith(b'\x1a\x45\xdf\xa3'):
        return 'webm'
    return None


def validate_video(upload) -> str:
    """MP4 or WebM; returns the format."""
    if upload is None:
        raise TrainingValidationError('Choose a video to upload.', 'file')
    _size(upload, VIDEO_MAX_BYTES, 'video', 'file')
    expected = VIDEO_FORMATS.get(_ext(upload))
    if expected is None:
        raise TrainingValidationError('Upload an MP4 or WebM video.', 'file')
    if detect_video_format(_head(upload, 16)) != expected:
        raise TrainingValidationError('The file is not a valid MP4 / WebM video.', 'file')
    return expected


def validate_thumbnail(upload) -> str:
    """PNG or JPEG image, checked by decoding it; returns 'png' or 'jpeg'."""
    if upload is None:
        raise TrainingValidationError('Choose an image.', 'thumbnail')
    _size(upload, THUMB_MAX_BYTES, 'thumbnail', 'thumbnail')
    expected = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG'}.get(_ext(upload))
    if expected is None:
        raise TrainingValidationError('Upload a PNG or JPG image.', 'thumbnail')
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            if img.format != expected:
                raise ValueError
            img.verify()
    except Exception:
        raise TrainingValidationError('The image is damaged or not a real PNG / JPG.', 'thumbnail') from None
    return expected.lower()


# ── External video links ──────────────────────────────────────────────────────

_YT_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
_YT_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com'}
_VIMEO_HOSTS = {'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'}
_DIRECT_EXTS = ('.mp4', '.webm', '.m4v')


def _public_host(host: str) -> bool:
    host = (host or '').lower().rstrip('.')
    if not host or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.lan')):
        return False
    try:
        ip = ipaddress.ip_address(host.strip('[]'))
    except ValueError:
        return '.' in host                      # a real domain name
    return ip.is_global                         # literal IPs only when public


def parse_external_video(url: str) -> dict:
    """{'url', 'provider', 'embed_id'} for a supported public video link, else TrainingValidationError."""
    url = (url or '').strip()
    if not url:
        raise TrainingValidationError('Paste the video link.', 'external_url')
    if len(url) > 1000:
        raise TrainingValidationError('The link is too long.', 'external_url')
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise TrainingValidationError('Only secure https:// links are allowed.', 'external_url')
    if parsed.username or parsed.password:
        raise TrainingValidationError('Links with a user name or password are not allowed.', 'external_url')
    host = (parsed.hostname or '').lower()
    if parsed.port not in (None, 443) or not _public_host(host):
        raise TrainingValidationError('The link must point to a public website.', 'external_url')

    if host in _YT_HOSTS or host == 'youtu.be':
        vid = ''
        if host == 'youtu.be':
            vid = parsed.path.strip('/').split('/')[0]
        elif parsed.path == '/watch':
            vid = (parse_qs(parsed.query).get('v') or [''])[0]
        else:
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) >= 2 and parts[0] in ('embed', 'shorts', 'live', 'v'):
                vid = parts[1]
        if not _YT_ID.match(vid or ''):
            raise TrainingValidationError('That YouTube link has no valid video id.', 'external_url')
        return {'url': f'https://www.youtube.com/watch?v={vid}', 'provider': 'youtube', 'embed_id': vid}

    if host in _VIMEO_HOSTS:
        parts = [p for p in parsed.path.split('/') if p]
        vid = next((p for p in parts if p.isdigit()), '')
        if not vid:
            raise TrainingValidationError('That Vimeo link has no video id.', 'external_url')
        return {'url': f'https://vimeo.com/{vid}', 'provider': 'vimeo', 'embed_id': vid}

    if parsed.path.lower().endswith(_DIRECT_EXTS):
        return {'url': url, 'provider': 'direct', 'embed_id': ''}

    raise TrainingValidationError(
        'Supported links: YouTube, Vimeo, or a direct https link to an .mp4 / .webm file.', 'external_url')
