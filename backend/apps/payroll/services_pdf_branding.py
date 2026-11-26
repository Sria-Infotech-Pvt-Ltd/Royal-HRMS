"""The company's logo on the payslip and Form 16 PDFs.

Both statements are the COMPANY's documents (the employer's name leads, AIRA is named underneath as the software), so the header also
carries the logo uploaded in Settings > Company Info. The logo sits on a small white badge, so a dark or transparent logo stays readable on
the dark header band. It is optional by design: a missing file, an unreadable image or an unsupported format (an SVG, say) simply leaves
the logo out, and the statement is produced exactly as before. A PDF must never fail because of a logo.
"""
from __future__ import annotations

import logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)

# The badge the logo is fitted into (inside a 1.5 mm white margin), and the gap between the badge and the company name next to it.
BADGE_HEIGHT = 17 * mm
BADGE_MAX_WIDTH = 34 * mm
BADGE_PADDING = 1.5 * mm
GAP_AFTER_BADGE = 4 * mm
MAX_LOGO_BYTES = 5 * 1024 * 1024   # same ceiling as every other upload in the app


def _logo_reader(company) -> ImageReader | None:
    """The company's uploaded logo as something reportlab can draw, or None when there is none or it cannot be read."""
    logo = getattr(company, 'logo', None)
    if not logo:
        return None
    try:
        with logo.open('rb') as handle:
            data = handle.read(MAX_LOGO_BYTES + 1)
        if not data or len(data) > MAX_LOGO_BYTES:
            return None
        reader = ImageReader(BytesIO(data))
        reader.getSize()   # raises for a file reportlab cannot decode (an SVG, a corrupt image ...)
        return reader
    except Exception:   # noqa: BLE001 - any storage or image problem means "no logo", never a failed PDF
        logger.warning('The company logo could not be added to a PDF; leaving it out.', exc_info=True)
        return None


TITLE_FONT = 'Helvetica-Bold'
TITLE_SIZE = 17
TITLE_MIN_SIZE = 9


def draw_company_title(c, name: str, left: float, baseline: float, right_limit: float) -> float:
    """Writes the company's name as the statement's title, shrinking the letters (down to a minimum) and then cutting it with an ellipsis so it
    never runs into the title on the right (`right_limit` is where the name must end). Returns the font size used."""
    size = TITLE_SIZE
    text = name.strip()
    while size > TITLE_MIN_SIZE and c.stringWidth(text, TITLE_FONT, size) > right_limit - left:
        size -= 0.5
    if c.stringWidth(text, TITLE_FONT, size) > right_limit - left:
        # Still too wide at the smallest size: cut it and say so with an ellipsis (the full name is in Company Info and the rest of the page).
        while len(text) > 1 and c.stringWidth(text + '...', TITLE_FONT, size) > right_limit - left:
            text = text[:-1].rstrip()
        text += '...'
    c.setFont(TITLE_FONT, size)
    c.drawString(left, baseline, text)
    return size


def draw_company_logo(c, company, left: float, top: float) -> float:
    """Draws the logo on a white badge whose top-left corner is (left, top). Returns the width used, including the gap, so the caller can
    move the company name to the right of it; 0 when there is no logo to draw."""
    reader = _logo_reader(company)
    if reader is None:
        return 0.0
    image_width, image_height = reader.getSize()
    inner_height = BADGE_HEIGHT - 2 * BADGE_PADDING
    inner_width = BADGE_MAX_WIDTH - 2 * BADGE_PADDING
    scale = min(inner_width / image_width, inner_height / image_height)
    drawn_width, drawn_height = image_width * scale, image_height * scale
    badge_width = drawn_width + 2 * BADGE_PADDING

    c.saveState()
    c.setFillColor(colors.white)
    c.roundRect(left, top - BADGE_HEIGHT, badge_width, BADGE_HEIGHT, 2 * mm, fill=1, stroke=0)
    c.drawImage(
        reader, left + BADGE_PADDING, top - BADGE_HEIGHT + (BADGE_HEIGHT - drawn_height) / 2,
        width=drawn_width, height=drawn_height, mask='auto',
    )
    c.restoreState()
    return badge_width + GAP_AFTER_BADGE
