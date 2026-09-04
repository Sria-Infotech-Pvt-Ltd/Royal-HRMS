"""
Real file-content validation — every upload validator in this project
previously checked only `UploadedFile.content_type`, a header the client
sets on the multipart request and fully controls (`curl -F
"file=@payload.exe;type=image/png"` sails straight through). This checks
the file's actual first bytes against known format signatures instead.

Deliberately hand-rolled rather than adding `python-magic` — that package
wraps the native `libmagic` C library via ctypes, which isn't guaranteed
present on every dev machine or deploy target (notably Windows, where this
project's own dev environment runs) and would make a working install
dependent on a system package this project doesn't otherwise need. A small
signature table covers every format this project actually accepts.

Plain text and CSV have no reliable magic-byte signature at all — any byte
sequence can be "valid text" — so those two are intentionally left
unchecked here, same as before this validation existed.
"""
from __future__ import annotations


def _read_head(file, n: int = 512) -> bytes:
    pos = file.tell()
    try:
        file.seek(0)
        return file.read(n)
    finally:
        file.seek(pos)


def sniff_mime_type(file) -> str | None:
    """Returns the MIME type this file's actual content matches, based on
    its leading bytes, or None if it doesn't match any known signature
    (including genuinely unsniffable types like text/csv)."""
    head = _read_head(file, 16)

    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE':
        return 'audio/wav'
    if head.startswith(b'OggS'):
        return 'audio/ogg'
    if head.startswith(b'\x1a\x45\xdf\xa3'):
        # EBML header — shared by WebM and Matroska containers.
        return 'audio/webm'
    if head.startswith(b'%PDF-'):
        return 'application/pdf'
    if head.startswith(b'PK\x03\x04'):
        # Office Open XML (docx/xlsx/pptx) and plain ZIP are all this same
        # signature — a real ZIP-based Office file always starts this way,
        # which is what actually matters here: is this genuinely an
        # archive-format file, not a renamed executable/script.
        return 'application/zip'
    if head.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        # Legacy OLE2 compound format — covers .doc/.xls/.ppt alike; the
        # signature alone can't distinguish which, and doesn't need to.
        return 'application/x-ole-compound'

    # SVG is XML text, not a fixed binary signature — a real SVG can have an
    # XML declaration, DOCTYPE, and/or comments before the <svg> tag itself,
    # so this needs a wider window than the binary checks above. This only
    # confirms the upload is genuinely SVG/XML-shaped, not a renamed
    # executable — it does not sanitize embedded content (the logo is only
    # ever rendered via <img src=...>, which never executes a script
    # embedded in an SVG, unlike <object>/<embed>/inline rendering).
    wide_head = _read_head(file, 512).lstrip(b'\xef\xbb\xbf \t\r\n')
    if wide_head.startswith(b'<?xml') or wide_head[:200].lower().find(b'<svg') != -1:
        return 'image/svg+xml'
    return None


# The zip/OLE2 signatures above are shared by several distinct declared
# MIME types (all the Office Open XML formats are ZIPs; legacy .doc/.xls
# are both OLE2) — this maps each declared type to the signature family
# that's an acceptable match for it.
_ACCEPTABLE_SNIFFED_FOR = {
    'image/jpeg': {'image/jpeg'},
    'image/png':  {'image/png'},
    'image/gif':  {'image/gif'},
    'image/webp': {'image/webp'},
    'image/svg+xml': {'image/svg+xml'},
    'application/pdf': {'application/pdf'},
    'audio/wav': {'audio/wav'},
    'audio/x-wav': {'audio/wav'},
    'audio/ogg': {'audio/ogg'},
    'audio/webm': {'audio/webm'},
    'application/msword': {'application/x-ole-compound'},
    'application/vnd.ms-excel': {'application/x-ole-compound'},
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {'application/zip'},
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {'application/zip'},
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': {'application/zip'},
}
# Types with no reliable magic-byte signature — content is trusted based on
# the declared Content-Type alone, same as before this module existed.
_UNSNIFFABLE_TYPES = {'text/plain', 'text/csv'}


def validate_file_content(file, declared_content_type: str) -> str | None:
    """Checks `file`'s actual bytes are consistent with what
    `declared_content_type` claims. Returns None if it's fine (including
    every unsniffable type, which this can't meaningfully check), or an
    error message string if the content doesn't match the claim."""
    if declared_content_type in _UNSNIFFABLE_TYPES:
        return None
    acceptable = _ACCEPTABLE_SNIFFED_FOR.get(declared_content_type)
    if acceptable is None:
        # A declared type this table doesn't know about at all — the
        # existing content_type-in-ALLOWED_MIME_TYPES check elsewhere
        # already rejects anything not on that whitelist; nothing more to
        # verify here.
        return None
    sniffed = sniff_mime_type(file)
    if sniffed not in acceptable:
        return (
            "This file's content doesn't match its declared type "
            f"({declared_content_type}) — it may have been renamed or corrupted."
        )
    return None
