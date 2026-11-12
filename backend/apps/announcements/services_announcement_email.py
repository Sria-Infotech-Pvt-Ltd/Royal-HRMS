"""
The content of an announcement e-mail: the text, the pictures, the PDF links and the external links, as HTML plus a plain-text version.

- Pictures are embedded in the message itself (inline CID parts), so they show in the mail client without a public image address and
  without the reader being signed in. Each is shrunk first (at most 720 px wide, JPEG) so a message with five pictures stays small
  even though every BCC batch carries them.
- PDFs are NOT attached (SMTP size limits, and a company-wide mailing). Each is a link to the authorised download endpoint with a
  signed token that stops working after a week; the permanent storage address is never put in an e-mail.
- Everything the author typed is escaped: the e-mail can show markup as text but never run it.
"""
from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass, field
from email.mime.image import MIMEImage

import requests
from django.utils.html import escape, linebreaks

from apps.announcements.models import Announcement, AnnouncementAttachment
from apps.announcements.services_attachments import (
    MAX_FILE_BYTES, human_file_size, make_download_token, safe_http_url, signed_download_url,
)

logger = logging.getLogger(__name__)

EMAIL_IMAGE_MAX_WIDTH = 720
EMAIL_CONTENT_WIDTH = 520               # the white card is 600 px wide with 40 px padding each side
IMAGE_FETCH_TIMEOUT_SECONDS = 15
_BUTTON_STYLE = (
    'display:inline-block;background:#4f46e5;color:#ffffff;padding:10px 18px;border-radius:6px;'
    'text-decoration:none;font-size:14px;margin:4px 8px 4px 0;'
)
_HEADING_STYLE = 'font-size:13px;font-weight:700;color:#555555;text-transform:uppercase;letter-spacing:0.04em;margin:24px 0 8px;'


@dataclass(frozen=True)
class InlineImage:
    cid: str
    data: bytes
    subtype: str


@dataclass
class AnnouncementEmail:
    body_html: str                                    # goes inside the branded frame
    text: str                                         # the plain-text version
    images: list[InlineImage] = field(default_factory=list)
    skipped_images: int = 0


def _portal_origin() -> str:
    from apps.accounts.services_frontend_url import PortalUrlNotConfigured, frontend_origin

    try:
        return frontend_origin()
    except PortalUrlNotConfigured:
        return ''


def fetch_image_bytes(attachment: AnnouncementAttachment) -> bytes | None:
    """The stored picture's bytes, read through a short-lived signed URL. None when it cannot be read (logged)."""
    try:
        response = requests.get(signed_download_url(attachment, ttl=600), timeout=IMAGE_FETCH_TIMEOUT_SECONDS, stream=True)
        response.raise_for_status()
        data = response.raw.read(MAX_FILE_BYTES + 1, decode_content=True)
    except Exception:
        logger.exception('Could not read announcement image %s for the e-mail.', attachment.pk)
        return None
    return data if 0 < len(data) <= MAX_FILE_BYTES else None


def prepare_email_image(raw: bytes) -> tuple[bytes, int] | None:
    """Shrink a picture for e-mail: upright (EXIF), flattened onto white, at most 720 px wide, JPEG. Returns (bytes, width)."""
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGBA')
                flat = Image.new('RGB', image.size, (255, 255, 255))
                flat.paste(image, mask=image.getchannel('A'))
                image = flat
            else:
                image = image.convert('RGB')
            image.thumbnail((EMAIL_IMAGE_MAX_WIDTH, 2000))
            out = io.BytesIO()
            image.save(out, format='JPEG', quality=82, optimize=True)
            return out.getvalue(), image.width
    except Exception:
        logger.exception('Could not prepare an announcement image for the e-mail.')
        return None


def _image_block(announcement: Announcement, images: list[AnnouncementAttachment]) -> tuple[str, list[InlineImage], int]:
    html, inline, skipped = [], [], 0
    for number, attachment in enumerate(images, start=1):
        raw = fetch_image_bytes(attachment)
        prepared = prepare_email_image(raw) if raw else None
        if prepared is None:
            skipped += 1
            continue
        data, width = prepared
        cid = f'{uuid.uuid4().hex}@announcement'
        inline.append(InlineImage(cid=cid, data=data, subtype='jpeg'))
        alt = escape(f'{announcement.title} - image {number}')
        html.append(
            f'<div style="margin:16px 0;"><img src="cid:{cid}" alt="{alt}" width="{min(width, EMAIL_CONTENT_WIDTH)}" '
            f'style="display:block;max-width:100%;height:auto;border:0;border-radius:6px;" /></div>'
        )
    return ''.join(html), inline, skipped


def _document_block(announcement: Announcement, documents: list[AnnouncementAttachment], origin: str) -> tuple[str, str]:
    if not documents:
        return '', ''
    html = [f'<div style="{_HEADING_STYLE}">Attachments</div>']
    text = ['', 'Attachments:']
    for attachment in documents:
        label = f'{attachment.original_filename} ({human_file_size(attachment.file_size)})'
        if origin:
            token = make_download_token(announcement.id, attachment.pk)
            url = f'{origin}/api/announcements/{announcement.id}/attachments/{attachment.pk}/download/?token={token}'
            html.append(f'<div style="margin:4px 0;"><a href="{escape(url)}" style="color:#4f46e5;">{escape(label)}</a></div>')
            text.append(f'- {label}: {url}')
        else:
            html.append(f'<div style="margin:4px 0;">{escape(label)}</div>')
            text.append(f'- {label}')
    if not origin:
        html.append('<div style="font-size:12px;color:#888888;margin-top:6px;">Sign in to AIRA HRMS to download the attachments.</div>')
        text.append('Sign in to AIRA HRMS to download the attachments.')
    return ''.join(html), '\n'.join(text)


def _link_block(links: list) -> tuple[str, str]:
    safe = [(str(item.get('title', '')), safe_http_url(str(item.get('url', '')))) for item in links or []]
    safe = [(title, url) for title, url in safe if title and url]
    if not safe:
        return '', ''
    html = [f'<div style="{_HEADING_STYLE}">Links</div><div>']
    html += [f'<a href="{escape(url)}" style="{_BUTTON_STYLE}">{escape(title)}</a>' for title, url in safe]
    html.append('</div>')
    text = ['', 'Links:'] + [f'- {title}: {url}' for title, url in safe]
    return ''.join(html), '\n'.join(text)


def build_announcement_email(announcement: Announcement) -> AnnouncementEmail:
    """Everything the e-mail shows for `announcement`."""
    origin = _portal_origin()
    attachments = list(announcement.attachments.all())
    images = [a for a in attachments if a.attachment_type == AnnouncementAttachment.TYPE_IMAGE]
    documents = [a for a in attachments if a.attachment_type == AnnouncementAttachment.TYPE_DOCUMENT]

    image_html, inline, skipped = _image_block(announcement, images)
    document_html, document_text = _document_block(announcement, documents, origin)
    link_html, link_text = _link_block(announcement.links)

    html = linebreaks(announcement.body, autoescape=True) + image_html + document_html + link_html
    text = announcement.body + document_text + link_text
    if skipped and origin:
        note = 'Some pictures could not be included here. Open the announcement in AIRA HRMS to see them.'
        html += f'<div style="font-size:12px;color:#888888;margin-top:12px;">{note}</div>'
    if origin and (images or documents or announcement.links):
        url = f'{origin}/dashboard/announcements?open={announcement.id}'
        html += f'<div style="margin-top:20px;"><a href="{escape(url)}" style="color:#4f46e5;">Open this announcement in AIRA HRMS</a></div>'
        text += f'\n\nOpen this announcement in AIRA HRMS: {url}'
    return AnnouncementEmail(body_html=html, text=text, images=inline, skipped_images=skipped)


def attach_inline_images(message, images: list[InlineImage]) -> None:
    """Put the pictures into `message` as inline parts the HTML refers to by Content-ID. Build fresh parts for every message."""
    if not images:
        return
    message.mixed_subtype = 'related'
    for number, item in enumerate(images, start=1):
        part = MIMEImage(item.data, _subtype=item.subtype)
        part.add_header('Content-ID', f'<{item.cid}>')
        part.add_header('Content-Disposition', 'inline', filename=f'image{number}.jpg')
        message.attach(part)
