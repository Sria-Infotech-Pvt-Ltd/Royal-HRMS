"""
Announcement images, PDFs and links: validation, storage and download authorisation.

Uploads are untrusted input. Every file is checked on the server for its extension, its declared MIME type, its real content
signature (core.file_validation), its size and, for images, that it decodes as an image. Files are stored under a server-generated
name, never the uploaded one, in private storage, and are reached only through the authorised download endpoint or a short-lived
signed URL.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import uuid
from urllib.parse import urlsplit

from django.core import signing

from core.file_validation import validate_file_content
from core.storage import get_signed_url

logger = logging.getLogger(__name__)

MAX_IMAGES = 5
MAX_DOCUMENTS = 5
MAX_LINKS = 5
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000
LINK_TITLE_MAX = 100
LINK_URL_MAX = 500
FILENAME_MAX = 150

DOWNLOAD_URL_TTL_SECONDS = 300                 # the redirect target a download mints: just long enough to start the transfer
EMAIL_LINK_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # links in the announcement e-mail stop working after a week
_TOKEN_SALT = 'announcements.attachment-download'

IMAGE_RULES = {'image/jpeg': ('.jpg', '.jpeg'), 'image/png': ('.png',), 'image/webp': ('.webp',)}
DOCUMENT_RULES = {'application/pdf': ('.pdf',)}
_PIL_FORMAT = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
_CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')


class AttachmentError(ValueError):
    """Something about an uploaded file, link or attachment change is not acceptable; the message is shown to the user."""


# ─── Names ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def safe_original_filename(name: str) -> str:
    """The name to SHOW for an upload: no directories (either separator style), no control characters, no leading dots, a bounded
    length. It is display text only; the stored file gets a generated name."""
    name = unicodedata.normalize('NFKC', str(name or ''))
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    name = _CONTROL_CHARS.sub('', name).strip().lstrip('.').strip()
    if not name:
        return 'file'
    stem, ext = os.path.splitext(name)
    return stem[:max(1, FILENAME_MAX - len(ext))] + ext


def human_file_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.0f} KB'
    return f'{size / (1024 * 1024):.1f} MB'


# ─── Files ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _check_image_content(file, declared: str, label: str) -> None:
    from PIL import Image

    try:
        file.seek(0)
        with Image.open(file) as image:
            image.verify()
        file.seek(0)
        with Image.open(file) as image:
            width, height, image_format = image.width, image.height, image.format
    except Exception:  # Pillow raises many kinds of errors for a damaged or non-image file
        raise AttachmentError(f'"{label}" is not a readable image.') from None
    finally:
        file.seek(0)
    if image_format != _PIL_FORMAT[declared]:
        raise AttachmentError(f'"{label}" is not a real {_PIL_FORMAT[declared]} image.')
    if width * height > MAX_IMAGE_PIXELS:
        raise AttachmentError(f'"{label}" is too large in pixels. Please use a smaller image.')


def _check_pdf_content(file, label: str) -> None:
    file.seek(max(0, file.size - 2048))
    tail = file.read(2048)
    file.seek(0)
    if b'%%EOF' not in tail:
        raise AttachmentError(f'"{label}" is not a complete PDF (it may be damaged or cut off).')


def check_upload(file, kind: str) -> tuple[str, str]:
    """Validate one uploaded file for `kind` ('image' or 'document'). Returns (content type, safe display name) or raises
    AttachmentError. Never trusts the browser: the extension, the declared type and the real bytes must all agree."""
    from apps.announcements.models import AnnouncementAttachment

    rules = IMAGE_RULES if kind == AnnouncementAttachment.TYPE_IMAGE else DOCUMENT_RULES
    label = safe_original_filename(getattr(file, 'name', ''))
    allowed = 'JPG, PNG or WebP images' if rules is IMAGE_RULES else 'PDF files'
    if file.size == 0:
        raise AttachmentError(f'"{label}" is empty.')
    if file.size > MAX_FILE_BYTES:
        raise AttachmentError(f'"{label}" is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.')
    declared = (getattr(file, 'content_type', '') or '').split(';')[0].strip().lower()
    extension = os.path.splitext(label)[1].lower()
    if declared not in rules or extension not in rules[declared]:
        raise AttachmentError(f'"{label}" is not accepted. Only {allowed} can be uploaded here.')
    mismatch = validate_file_content(file, declared)
    if mismatch:
        raise AttachmentError(f'"{label}": {mismatch}')
    if rules is IMAGE_RULES:
        _check_image_content(file, declared, label)
    else:
        _check_pdf_content(file, label)
    return declared, label


def check_counts(existing: list, remove_ids: set, new_images: list, new_documents: list) -> None:
    """The announcement may not end up with more images, PDFs or unknown removals than the limits allow."""
    from apps.announcements.models import AnnouncementAttachment

    existing_ids = {attachment.id for attachment in existing}
    if remove_ids - existing_ids:
        raise AttachmentError('One of the attachments to remove does not belong to this announcement.')
    kept = [a for a in existing if a.id not in remove_ids]
    images = sum(a.attachment_type == AnnouncementAttachment.TYPE_IMAGE for a in kept) + len(new_images)
    documents = sum(a.attachment_type == AnnouncementAttachment.TYPE_DOCUMENT for a in kept) + len(new_documents)
    if images > MAX_IMAGES:
        raise AttachmentError(f'An announcement can have at most {MAX_IMAGES} images.')
    if documents > MAX_DOCUMENTS:
        raise AttachmentError(f'An announcement can have at most {MAX_DOCUMENTS} PDF attachments.')


def store_new_files(announcement, images: list, documents: list) -> list:
    """Upload and record the files (already validated). If anything fails midway, files already uploaded are removed again."""
    from apps.announcements.models import AnnouncementAttachment

    created, stored_names = [], []
    try:
        for kind, files in ((AnnouncementAttachment.TYPE_IMAGE, images), (AnnouncementAttachment.TYPE_DOCUMENT, documents)):
            for file in files:
                content_type, label = check_upload(file, kind)
                extension = os.path.splitext(label)[1].lower()
                attachment = AnnouncementAttachment(
                    announcement=announcement, attachment_type=kind, original_filename=label,
                    file_size=file.size, content_type=content_type,
                )
                attachment.file.save(f'{uuid.uuid4().hex}{extension}', file, save=False)
                stored_names.append(attachment.file.name)
                attachment.save()
                created.append(attachment)
    except Exception:
        delete_stored_files(stored_names)
        raise
    return created


def delete_stored_files(names: list[str]) -> None:
    """Best effort: a storage failure must never undo a save that already happened. A file that cannot be removed is logged."""
    from apps.announcements.models import AnnouncementAttachment

    storage = AnnouncementAttachment._meta.get_field('file').storage
    for name in names:
        try:
            storage.delete(name)
        except Exception:
            logger.exception('Could not delete announcement file %s from storage.', name)


# ─── Links ───────────────────────────────────────────────────────────────────────────────────────────────────────────────

def safe_http_url(value: str) -> str | None:
    """The URL if it is a plain http(s) address a person could safely open, else None (javascript:, data:, file:, credentials in
    the address, spaces and control characters are all refused)."""
    value = (value or '').strip()
    if not value or len(value) > LINK_URL_MAX or _CONTROL_CHARS.search(value) or re.search(r'\s', value):
        return None
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in ('http', 'https') or not hostname or parts.username or parts.password:
        return None
    return value


def clean_links(raw) -> list[dict]:
    """Validate the links sent with an announcement (a list, or a JSON string of one) and return [{'title', 'url'}, ...]."""
    if raw in (None, ''):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise AttachmentError('The links could not be read.') from None
    if not isinstance(raw, list):
        raise AttachmentError('The links must be a list.')
    if len(raw) > MAX_LINKS:
        raise AttachmentError(f'An announcement can have at most {MAX_LINKS} links.')
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            raise AttachmentError('Each link needs a title and a web address.')
        title = _CONTROL_CHARS.sub('', str(item.get('title') or '')).strip()
        url = safe_http_url(str(item.get('url') or ''))
        if not title:
            raise AttachmentError('Each link needs a title.')
        if len(title) > LINK_TITLE_MAX:
            raise AttachmentError(f'A link title can be at most {LINK_TITLE_MAX} characters.')
        if url is None:
            raise AttachmentError(f'"{title}": enter a valid web address starting with http:// or https://.')
        cleaned.append({'title': title, 'url': url})
    return cleaned


# ─── Authorised downloads ────────────────────────────────────────────────────────────────────────────────────────────────

def make_download_token(announcement_id: int, attachment_id) -> str:
    """A signed token for ONE attachment, put in the announcement e-mail link. It stops working after a week."""
    return signing.dumps({'a': int(announcement_id), 'f': str(attachment_id)}, salt=_TOKEN_SALT)


def download_token_is_valid(token: str, announcement_id: int, attachment_id) -> bool:
    try:
        payload = signing.loads(token, salt=_TOKEN_SALT, max_age=EMAIL_LINK_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return False
    return payload == {'a': int(announcement_id), 'f': str(attachment_id)}


def signed_download_url(attachment, ttl: int = DOWNLOAD_URL_TTL_SECONDS) -> str:
    """A short-lived signed URL for the stored file. The permanent storage address is never handed out."""
    return get_signed_url(attachment.file.name, ttl)
