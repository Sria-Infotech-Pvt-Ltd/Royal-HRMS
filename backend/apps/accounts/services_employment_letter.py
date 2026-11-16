"""Renders a real employment verification letter PDF for an employee, on demand (reportlab, not persisted to a FileField - same pattern as
the payroll app's services_payslip_pdf.render_payslip_pdf).

Layout: a double page border with corner accents and a faint company-name watermark; a coloured header banner with the company logo,
name, registered office, contact line and CIN; a reference number, date and subject bar; the letter text; a bordered table of the
employee's details; a signature block (the authorised signatory from the company settings) with a company-seal circle; and a colour
footer strip on every page.

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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.accounts.models import Company, User

logger = logging.getLogger(__name__)

BRAND = colors.HexColor('#4C1D95')
BRAND_LIGHT = colors.HexColor('#EDE9FE')
GOLD = colors.HexColor('#B8932E')
RULE_GREY = colors.HexColor('#C4C4CC')
TEXT_GREY = colors.HexColor('#6B7280')
PAGE_WIDTH, PAGE_HEIGHT = A4
OUTER = 8 * mm            # outer border inset from the page edge
INNER = OUTER + 2.4 * mm  # inner border inset
CONTENT_MARGIN = 22 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * CONTENT_MARGIN
BANNER_HEIGHT = 32 * mm
LOGO_BOX = 21 * mm
FOOTER_HEIGHT = 8 * mm
LOGO_FETCH_TIMEOUT_SECONDS = 5
MAX_LOGO_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class Letterhead:
    """What the page decoration needs from the Company row (read once, so drawing never touches the database)."""
    name: str
    lines: tuple[str, ...]
    logo: bytes | None = None


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
        'meta': ParagraphStyle('Meta', parent=base, fontSize=9.5, leading=13),
        'subject': ParagraphStyle('Subject', parent=base, fontName='Helvetica-Bold', fontSize=11.5, leading=15, alignment=TA_CENTER, textColor=BRAND),
        'subject_small': ParagraphStyle('SubjectSmall', parent=base, fontSize=9, leading=12, alignment=TA_CENTER, textColor=TEXT_GREY),
        'body': ParagraphStyle('Body', parent=base, fontSize=10.5, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=7),
        'head': ParagraphStyle('Head', parent=base, fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white),
        'label': ParagraphStyle('Label', parent=base, fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, textColor=BRAND),
        'value': ParagraphStyle('Value', parent=base, fontSize=10, leading=12.5),
        'sign': ParagraphStyle('Sign', parent=base, fontSize=10, leading=14),
    }


def _draw_page(canvas, doc, letterhead: Letterhead, reference: str, is_first: bool) -> None:
    """Page decoration: watermark, double border with corner accents, header banner (first page) and footer strip."""
    canvas.saveState()
    _draw_watermark(canvas, letterhead.name)
    _draw_border(canvas)
    if is_first:
        _draw_banner(canvas, letterhead)
    _draw_footer(canvas, reference)
    canvas.restoreState()


def _draw_watermark(canvas, name: str) -> None:
    canvas.saveState()
    canvas.setFillColor(BRAND)
    canvas.setFillAlpha(0.05)
    canvas.setFont('Helvetica-Bold', 54)
    canvas.translate(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)
    canvas.rotate(38)
    canvas.drawCentredString(0, 0, name.upper()[:28])
    canvas.restoreState()


def _draw_border(canvas) -> None:
    canvas.setStrokeColor(BRAND)
    canvas.setLineWidth(2.4)
    canvas.rect(OUTER, OUTER, PAGE_WIDTH - 2 * OUTER, PAGE_HEIGHT - 2 * OUTER)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.8)
    canvas.rect(INNER, INNER, PAGE_WIDTH - 2 * INNER, PAGE_HEIGHT - 2 * INNER)
    canvas.setFillColor(GOLD)
    size = 2.4 * mm
    for x in (INNER, PAGE_WIDTH - INNER - size):
        for y in (INNER, PAGE_HEIGHT - INNER - size):
            canvas.rect(x, y, size, size, stroke=0, fill=1)


def _draw_banner(canvas, letterhead: Letterhead) -> None:
    """Coloured header inside the inner border: the logo (if any) on the left, company name and details in white."""
    left, width = INNER + 1.2 * mm, PAGE_WIDTH - 2 * (INNER + 1.2 * mm)
    top = PAGE_HEIGHT - INNER - 1.2 * mm
    bottom = top - BANNER_HEIGHT
    canvas.setFillColor(BRAND)
    canvas.rect(left, bottom, width, BANNER_HEIGHT, stroke=0, fill=1)
    canvas.setFillColor(GOLD)
    canvas.rect(left, bottom - 1.2 * mm, width, 1.2 * mm, stroke=0, fill=1)
    text_left = left + 7 * mm
    if letterhead.logo:
        box_size = LOGO_BOX + 4 * mm
        box_left, box_bottom = left + 5 * mm, bottom + (BANNER_HEIGHT - box_size) / 2
        canvas.setFillColor(colors.white)
        canvas.roundRect(box_left, box_bottom, box_size, box_size, 2 * mm, stroke=0, fill=1)
        canvas.drawImage(ImageReader(BytesIO(letterhead.logo)), box_left + 2 * mm, box_bottom + 2 * mm, LOGO_BOX, LOGO_BOX,
                         preserveAspectRatio=True, anchor='c', mask='auto')
        text_left = box_left + box_size + 6 * mm
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 17)
    detail_lines = len(letterhead.lines)
    name_y = bottom + BANNER_HEIGHT / 2 + (detail_lines * 2.1 * mm) - 1 * mm if detail_lines else bottom + BANNER_HEIGHT / 2 - 3
    canvas.drawString(text_left, name_y, letterhead.name)
    canvas.setFont('Helvetica', 8.5)
    canvas.setFillColor(colors.HexColor('#E4DAFF'))
    for index, line in enumerate(letterhead.lines):
        canvas.drawString(text_left, name_y - 6 * mm - index * 4.2 * mm, line)


def _draw_footer(canvas, reference: str) -> None:
    left, width = INNER + 1.2 * mm, PAGE_WIDTH - 2 * (INNER + 1.2 * mm)
    bottom = INNER + 1.2 * mm
    canvas.setFillColor(BRAND)
    canvas.rect(left, bottom, width, FOOTER_HEIGHT, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(left + 4 * mm, bottom + 2.9 * mm, 'This is a system-generated letter and does not require a physical signature.')
    canvas.drawRightString(left + width - 4 * mm, bottom + 2.9 * mm, f'Ref: {reference}')


def _subject_bar(name: str, employee_id: str, styles: dict[str, ParagraphStyle]) -> Table:
    detail = f'{name} (Employee ID: {employee_id})' if employee_id else name
    bar = Table(
        [[Paragraph('EMPLOYMENT VERIFICATION LETTER', styles['subject'])], [Paragraph(f'Subject: Verification of employment of {detail}', styles['subject_small'])]],
        colWidths=[CONTENT_WIDTH],
    )
    bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_LIGHT), ('LINEABOVE', (0, 0), (-1, 0), 1.2, BRAND), ('LINEBELOW', (0, -1), (-1, -1), 1.2, BRAND),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return bar


def _details_table(employee: User, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[Paragraph('EMPLOYEE DETAILS', styles['head']), '']]
    rows += [[Paragraph(label, styles['label']), Paragraph(value, styles['value'])] for label, value in letter_detail_rows(employee)]
    table = Table(rows, colWidths=[48 * mm, CONTENT_WIDTH - 48 * mm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), BRAND),
        ('BOX', (0, 0), (-1, -1), 1, BRAND), ('INNERGRID', (0, 1), (-1, -1), 0.4, RULE_GREY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BRAND_LIGHT, colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5), ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def _seal() -> Drawing:
    """A dashed circle marking where the company seal goes."""
    size = 30 * mm
    drawing = Drawing(size, size)
    drawing.add(Circle(size / 2, size / 2, size / 2 - 1, strokeColor=RULE_GREY, strokeWidth=0.8, strokeDashArray=[3, 3], fillColor=None))
    drawing.add(String(size / 2, size / 2 - 2, 'Company seal / stamp', fontSize=6.5, fillColor=RULE_GREY, textAnchor='middle'))
    return drawing


def _signature_block(company_name: str, signatory: Signatory, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    signer = [
        Paragraph(f'<b>For {company_name}</b>', styles['sign']),
        Spacer(1, 13 * mm),
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
    letterhead = Letterhead(name=company_name, lines=tuple(_company_letterhead_lines(company)), logo=_read_logo(company))
    styles = _styles()
    today = timezone.localtime().date()
    reference = letter_reference(employee, today)
    name = employee.full_name or employee.email

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=INNER + BANNER_HEIGHT + 10 * mm, bottomMargin=INNER + FOOTER_HEIGHT + 8 * mm,
        leftMargin=CONTENT_MARGIN, rightMargin=CONTENT_MARGIN, title='Employment Verification Letter', author=company_name,
    )
    meta = Table(
        [[Paragraph(f'<b>Ref:</b> {reference}', styles['meta']), Paragraph(f'<b>Date:</b> {_long_date(today)}', styles['meta'])]],
        colWidths=[CONTENT_WIDTH * 0.62, CONTENT_WIDTH * 0.38],
    )
    meta.setStyle(TableStyle([('LEFTPADDING', (0, 0), (0, 0), 0), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))

    designation = f', holding the designation of <b>{employee.designation}</b>' if employee.designation else ''
    elements = [
        meta, Spacer(1, 5 * mm),
        _subject_bar(name, employee.employee_id or '', styles), Spacer(1, 5 * mm),
        Paragraph('To Whom It May Concern,', styles['body']),
        Paragraph(f'This is to certify that <b>{name}</b> {_employment_status_statement(employee)}{designation}. '
                  'The employee\'s details, as held in the company\'s records, are given below.', styles['body']),
        Spacer(1, 1 * mm), _details_table(employee, styles), Spacer(1, 5 * mm),
        Paragraph('This letter is issued upon the employee\'s request for verification purposes such as banking, visa or tenancy '
                  'applications, and may be relied upon accordingly. It does not constitute a guarantee of continued employment.', styles['body']),
        Spacer(1, 7 * mm),
        _signature_block(company_name, signatory_for(company), styles),
    ]
    doc.build(
        elements,
        onFirstPage=partial(_draw_page, letterhead=letterhead, reference=reference, is_first=True),
        onLaterPages=partial(_draw_page, letterhead=letterhead, reference=reference, is_first=False),
    )
    return buffer.getvalue()
