"""Renders a real employment verification letter PDF for an employee, on demand (reportlab, not persisted to a FileField - same pattern as
the payroll app's services_payslip_pdf.render_payslip_pdf).

Layout (a classic business letter, black and navy on white): a double-rule page border; a letterhead with the company logo on the left
and the name, registered office, contact line and CIN beside it, closed by a rule; reference and date; a centred underlined title; the
letter text in a serif face; a simple ruled table of the employee's details; and a signature block with the authorised signatory and a
seal circle; a one-line footer on every page.

Everything about the company comes from the Company row filled in under Settings > Company (logo, name, address, phone, email, website,
CIN and the authorised signatory), and about the employee from their own record. Nothing is hardcoded (CLAUDE.md); a detail that is not
held is left out of the letter instead of being printed as "not on record".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial
from io import BytesIO

import requests
from django.utils import timezone
from reportlab.graphics.shapes import Circle, Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.accounts.models import Company, User

logger = logging.getLogger(__name__)

NAVY = colors.HexColor('#1F2A44')
INK = colors.HexColor('#111827')
GREY = colors.HexColor('#6B7280')
RULE = colors.HexColor('#9CA3AF')
LABEL_BG = colors.HexColor('#F3F4F6')
PAGE_WIDTH, PAGE_HEIGHT = A4
OUTER = 9 * mm            # outer border inset from the page edge
INNER = OUTER + 1.8 * mm  # inner (thin) border inset
CONTENT_MARGIN = 24 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * CONTENT_MARGIN
LOGO_BOX = 22 * mm
LOGO_FETCH_TIMEOUT_SECONDS = 5
MAX_LOGO_BYTES = 5 * 1024 * 1024
SERIF, SERIF_BOLD = 'Times-Roman', 'Times-Bold'


@dataclass(frozen=True)
class Signatory:
    """Who signs for the company: the authorised signatory set in the company settings, else a generic HR Operations block."""
    name: str
    designation: str


def _distinct(parts: list[str]) -> list[str]:
    """The non-blank parts in order, without repeating one (a city typed into both the address and city fields prints once)."""
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        text = (part or '').strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result


def _address_text(company: Company) -> str:
    """The registered office on one line. The address field often already ends with the city or state, so the parts are split at
    commas first and a repeated place name prints once ("Hyderabad, Telangana" + city "Hyderabad" -> "Hyderabad, Telangana")."""
    tokens = [token for part in (company.address, company.city, company.state, company.pin_code) for token in (part or '').split(',')]
    return ', '.join(_distinct(tokens))


def _company_letterhead_lines(company: Company | None) -> list[str]:
    """Registered office, contact line and CIN, one line per part the company settings hold - never a made-up address."""
    if not company:
        return []
    contact = ' | '.join(_distinct([company.official_phone, company.primary_email, company.website]))
    cin = f'CIN: {company.cin.strip()}' if (company.cin or '').strip() else ''
    return [line for line in (_address_text(company), contact, cin) if line]


def signatory_for(company: Company | None) -> Signatory:
    name = (company.signatory_full_name or '').strip() if company else ''
    designation = (company.signatory_designation or '').strip() if company else ''
    if name:
        return Signatory(name=name, designation=designation or 'Authorised Signatory')
    return Signatory(name='Authorised Signatory', designation='HR Operations')


def _employment_status_statement(employee: User) -> str:
    """A factual statement of current employment status - nothing beyond what the User row holds."""
    if not employee.is_active:
        return 'is no longer an active employee of the company as of the date of this letter'
    return f'is currently an active employee of the company, presently in {employee.get_employment_status_display()} status'


def _long_date(value) -> str:
    return value.strftime('%d %B %Y') if value else ''


def letter_detail_rows(employee: User) -> list[tuple[str, str]]:
    """The (label, value) rows of the details table; a detail the record does not hold is left out."""
    candidates = [
        ('Employee name', employee.full_name),
        ('Employee ID', employee.employee_id),
        ('Designation', employee.designation),
        ('Department', employee.department),
        ('Date of joining', _long_date(employee.date_of_joining)),
        ('Employment status', employee.get_employment_status_display() if employee.is_active else 'Not active'),
        ('Work location', employee.branch),
    ]
    return [(label, value.strip()) for label, value in candidates if value and str(value).strip()]


def letter_reference(employee: User, today) -> str:
    return f'EVL/{today:%Y}/{employee.employee_id or str(employee.pk)[:8]}/{today:%d%m%y}'


def _logo_bytes(company: Company) -> bytes:
    """The logo file's bytes. Local storage is read directly; remote storage (ImageKit, which Django cannot read back) is fetched
    from the logo's own URL."""
    try:
        with company.logo.open('rb') as handle:
            return handle.read()
    except NotImplementedError:
        response = requests.get(company.logo.url, timeout=LOGO_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
        if len(response.content) > MAX_LOGO_BYTES:
            raise ValueError('The company logo is too large to print on a letter.')
        return response.content


def _read_logo(company: Company | None) -> bytes | None:
    """The company logo's bytes, or None when there is none (or it cannot be fetched, or is not an image)."""
    if not company or not company.logo:
        return None
    try:
        data = _logo_bytes(company)
        ImageReader(BytesIO(data)).getSize()   # raises when the file is not an image
        return data
    except Exception:  # a missing or broken logo must never stop the letter from being issued
        logger.warning('Company logo could not be read for the employment letter.', exc_info=True)
        return None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()['Normal']
    return {
        'company': ParagraphStyle('Company', parent=base, fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=NAVY),
        'letterhead': ParagraphStyle('Letterhead', parent=base, fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=GREY),
        'meta': ParagraphStyle('Meta', parent=base, fontName=SERIF, fontSize=10.5, leading=14, textColor=INK),
        'title': ParagraphStyle('Title', parent=base, fontName=SERIF_BOLD, fontSize=13.5, leading=18, alignment=TA_CENTER, textColor=INK),
        'body': ParagraphStyle('Body', parent=base, fontName=SERIF, fontSize=11.5, leading=17, alignment=TA_JUSTIFY, spaceAfter=8, textColor=INK),
        'label': ParagraphStyle('Label', parent=base, fontName=SERIF_BOLD, fontSize=10.5, leading=14, textColor=INK),
        'value': ParagraphStyle('Value', parent=base, fontName=SERIF, fontSize=10.5, leading=14, textColor=INK),
        'sign': ParagraphStyle('Sign', parent=base, fontName=SERIF, fontSize=11, leading=15, textColor=INK),
    }


def _draw_page(canvas, doc, reference: str) -> None:
    """Page decoration: a thick outer and a thin inner border, and a one-line footer with the reference."""
    canvas.saveState()
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(1.6)
    canvas.rect(OUTER, OUTER, PAGE_WIDTH - 2 * OUTER, PAGE_HEIGHT - 2 * OUTER)
    canvas.setLineWidth(0.4)
    canvas.rect(INNER, INNER, PAGE_WIDTH - 2 * INNER, PAGE_HEIGHT - 2 * INNER)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(GREY)
    footer_y = INNER + 5 * mm
    canvas.drawString(CONTENT_MARGIN, footer_y, 'This is a system-generated letter and does not require a physical signature.')
    canvas.drawRightString(PAGE_WIDTH - CONTENT_MARGIN, footer_y, f'Ref: {reference}')
    canvas.restoreState()


def _letterhead(company: Company | None, company_name: str, logo: bytes | None, styles: dict[str, ParagraphStyle]) -> list:
    text = [Paragraph(company_name, styles['company'])] + [Paragraph(line, styles['letterhead']) for line in _company_letterhead_lines(company)]
    cells, widths = [text], [CONTENT_WIDTH]
    if logo:
        reader = ImageReader(BytesIO(logo))
        width, height = reader.getSize()
        scale = min(LOGO_BOX / width, LOGO_BOX / height)
        cells, widths = [Image(BytesIO(logo), width=width * scale, height=height * scale), text], [LOGO_BOX + 6 * mm, CONTENT_WIDTH - LOGO_BOX - 6 * mm]
    header = Table([cells], colWidths=widths)
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    rule = Table([['']], colWidths=[CONTENT_WIDTH], rowHeights=[3])
    rule.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), 1.4, NAVY), ('LINEBELOW', (0, 0), (-1, 0), 0.4, NAVY)]))
    return [header, rule]


def _details_table(employee: User, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[Paragraph(label, styles['label']), Paragraph(value, styles['value'])] for label, value in letter_detail_rows(employee)]
    table = Table(rows, colWidths=[48 * mm, CONTENT_WIDTH - 48 * mm])
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.9, NAVY), ('INNERGRID', (0, 0), (-1, -1), 0.4, RULE),
        ('BACKGROUND', (0, 0), (0, -1), LABEL_BG), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5), ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def _seal() -> Drawing:
    """A dashed circle marking where the company seal goes."""
    size = 30 * mm
    drawing = Drawing(size, size)
    drawing.add(Circle(size / 2, size / 2, size / 2 - 1, strokeColor=RULE, strokeWidth=0.8, strokeDashArray=[3, 3], fillColor=None))
    drawing.add(String(size / 2, size / 2 - 2, 'Company seal / stamp', fontSize=6.5, fillColor=RULE, textAnchor='middle'))
    return drawing


def _signature_block(company_name: str, signatory: Signatory, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    signer = [
        Paragraph(f'For <b>{company_name}</b>', styles['sign']),
        Spacer(1, 14 * mm),
        Paragraph('_______________________________', styles['sign']),
        Paragraph(f'<b>{signatory.name}</b>', styles['sign']),
        Paragraph(signatory.designation, styles['sign']),
    ]
    block = Table([[signer, _seal()]], colWidths=[CONTENT_WIDTH - 40 * mm, 40 * mm])
    block.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('LEFTPADDING', (0, 0), (0, 0), 0), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    return KeepTogether([block])


def render_employment_letter_pdf(employee: User) -> bytes:
    company = Company.objects.first()
    company_name = company.company_name if company else 'This company'
    styles = _styles()
    today = timezone.localtime().date()
    reference = letter_reference(employee, today)
    name = employee.full_name or employee.email

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=INNER + 12 * mm, bottomMargin=INNER + 16 * mm,
        leftMargin=CONTENT_MARGIN, rightMargin=CONTENT_MARGIN, title='Employment Verification Letter', author=company_name,
    )
    meta = Table(
        [[Paragraph(f'<b>Ref:</b> {reference}', styles['meta']), Paragraph(f'<b>Date:</b> {_long_date(today)}', styles['meta'])]],
        colWidths=[CONTENT_WIDTH * 0.62, CONTENT_WIDTH * 0.38],
    )
    meta.setStyle(TableStyle([('LEFTPADDING', (0, 0), (0, 0), 0), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))

    designation = f', holding the designation of <b>{employee.designation}</b>' if employee.designation else ''
    elements = [
        *_letterhead(company, company_name, _read_logo(company), styles),
        Spacer(1, 7 * mm), meta, Spacer(1, 9 * mm),
        Paragraph('<u>EMPLOYMENT VERIFICATION LETTER</u>', styles['title']),
        Spacer(1, 7 * mm),
        Paragraph('To Whom It May Concern,', styles['body']),
        Paragraph(f'This is to certify that <b>{name}</b> {_employment_status_statement(employee)}{designation}. '
                  'The employee\'s details, as held in the company\'s records, are given below.', styles['body']),
        Spacer(1, 2 * mm), _details_table(employee, styles), Spacer(1, 6 * mm),
        Paragraph('This letter is issued upon the employee\'s request for verification purposes such as banking, visa or tenancy '
                  'applications, and may be relied upon accordingly. It does not constitute a guarantee of continued employment.', styles['body']),
        Spacer(1, 9 * mm),
        _signature_block(company_name, signatory_for(company), styles),
    ]
    page = partial(_draw_page, reference=reference)
    doc.build(elements, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
