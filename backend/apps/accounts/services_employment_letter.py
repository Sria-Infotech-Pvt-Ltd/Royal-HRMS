"""Renders a real employment verification letter PDF for an employee, on demand (reportlab, not persisted to a FileField - same pattern as
the payroll app's services_payslip_pdf.render_payslip_pdf).

Layout: a double-line page border, a letterhead (company logo when one is uploaded, name, registered office and contact line), a
reference number and date, the letter text, a bordered table of the employee's details, and a signature block with a box for the
company stamp. Everything comes from the real Company singleton and the employee's own row - nothing is hardcoded (CLAUDE.md), and a
detail the record does not hold is left out of the letter instead of being printed as "not on record".
"""
from __future__ import annotations

import logging
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.accounts.models import Company, User

logger = logging.getLogger(__name__)

BRAND = colors.HexColor('#4C1D95')
BRAND_LIGHT = colors.HexColor('#EDE9FE')
RULE_GREY = colors.HexColor('#C4C4CC')
TEXT_GREY = colors.HexColor('#6B7280')
PAGE_WIDTH, PAGE_HEIGHT = A4
FRAME_MARGIN = 9 * mm
CONTENT_MARGIN = 20 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * CONTENT_MARGIN
LOGO_BOX = 22 * mm


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
    """Registered-office address and contact line, one line per non-blank part - never a made-up address."""
    if not company:
        return []
    address = _address_text(company)
    contact = ' | '.join(_distinct([company.official_phone, company.primary_email, company.website]))
    return [line for line in (address, contact) if line]


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


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()['Normal']
    return {
        'company': ParagraphStyle('Company', parent=base, fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=BRAND),
        'letterhead': ParagraphStyle('Letterhead', parent=base, fontSize=8.5, leading=11.5, textColor=TEXT_GREY),
        'meta': ParagraphStyle('Meta', parent=base, fontSize=9.5, leading=13),
        'title': ParagraphStyle('Title', parent=base, fontName='Helvetica-Bold', fontSize=13, leading=17, alignment=TA_CENTER, textColor=BRAND),
        'body': ParagraphStyle('Body', parent=base, fontSize=10.5, leading=16, alignment=TA_JUSTIFY, spaceAfter=8),
        'label': ParagraphStyle('Label', parent=base, fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=BRAND),
        'value': ParagraphStyle('Value', parent=base, fontSize=10, leading=13),
        'sign': ParagraphStyle('Sign', parent=base, fontSize=10, leading=14),
        'small': ParagraphStyle('Small', parent=base, fontSize=8, leading=11, textColor=TEXT_GREY, alignment=TA_CENTER),
    }


def _logo(company: Company | None):
    """The uploaded company logo scaled into a square box, or None when there is none (or it cannot be read)."""
    if not company or not company.logo:
        return None
    try:
        with company.logo.open('rb') as handle:
            data = handle.read()
        reader = ImageReader(BytesIO(data))
        width, height = reader.getSize()
        scale = min(LOGO_BOX / width, LOGO_BOX / height)
        return Image(BytesIO(data), width=width * scale, height=height * scale)
    except Exception:  # a missing or broken logo must never stop the letter from being issued
        logger.warning('Company logo could not be read for the employment letter.', exc_info=True)
        return None


def _letterhead(company: Company | None, company_name: str, styles: dict[str, ParagraphStyle]) -> list:
    lines = [Paragraph(company_name, styles['company'])] + [Paragraph(line, styles['letterhead']) for line in _company_letterhead_lines(company)]
    logo = _logo(company)
    header = Table([[logo, lines]] if logo else [[lines]], colWidths=[LOGO_BOX + 6 * mm, CONTENT_WIDTH - LOGO_BOX - 6 * mm] if logo else [CONTENT_WIDTH])
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    rule = Table([['']], colWidths=[CONTENT_WIDTH], rowHeights=[2])
    rule.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), 1.6, BRAND), ('LINEBELOW', (0, 0), (-1, 0), 0.4, BRAND)]))
    return [header, Spacer(1, 2 * mm), rule]


def _details_table(employee: User, styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[Paragraph(label, styles['label']), Paragraph(value, styles['value'])] for label, value in letter_detail_rows(employee)]
    table = Table(rows, colWidths=[48 * mm, CONTENT_WIDTH - 48 * mm])
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, BRAND),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, RULE_GREY),
        ('BACKGROUND', (0, 0), (0, -1), BRAND_LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def _signature_block(company_name: str, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    stamp = Table([['Company seal / stamp']], colWidths=[55 * mm], rowHeights=[28 * mm])
    stamp.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, RULE_GREY), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8), ('TEXTCOLOR', (0, 0), (-1, -1), RULE_GREY),
    ]))
    signer = [
        Paragraph(f'<b>For {company_name}</b>', styles['sign']),
        Spacer(1, 16 * mm),
        Paragraph('_______________________________', styles['sign']),
        Paragraph('<b>Authorised Signatory</b>', styles['sign']),
        Paragraph('HR Operations', styles['sign']),
    ]
    block = Table([[signer, stamp]], colWidths=[CONTENT_WIDTH - 60 * mm, 60 * mm])
    block.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('LEFTPADDING', (0, 0), (0, 0), 0)]))
    return KeepTogether([block])


def _draw_page_frame(canvas, doc) -> None:
    """A thick outer and a thin inner border on every page, and the footer line."""
    canvas.saveState()
    canvas.setStrokeColor(BRAND)
    canvas.setLineWidth(2.2)
    canvas.rect(FRAME_MARGIN, FRAME_MARGIN, PAGE_WIDTH - 2 * FRAME_MARGIN, PAGE_HEIGHT - 2 * FRAME_MARGIN)
    canvas.setLineWidth(0.5)
    canvas.rect(FRAME_MARGIN + 2.2 * mm, FRAME_MARGIN + 2.2 * mm, PAGE_WIDTH - 2 * (FRAME_MARGIN + 2.2 * mm), PAGE_HEIGHT - 2 * (FRAME_MARGIN + 2.2 * mm))
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(TEXT_GREY)
    canvas.drawCentredString(PAGE_WIDTH / 2, FRAME_MARGIN + 6 * mm, 'This is a system-generated letter and does not require a physical signature.')
    canvas.restoreState()


def render_employment_letter_pdf(employee: User) -> bytes:
    company = Company.objects.first()
    company_name = company.company_name if company else 'This company'
    styles = _styles()
    now = timezone.localtime()
    today = now.date()
    name = employee.full_name or employee.email

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, topMargin=22 * mm, bottomMargin=24 * mm, leftMargin=CONTENT_MARGIN, rightMargin=CONTENT_MARGIN,
        title='Employment Verification Letter', author=company_name,
    )
    meta = Table(
        [[Paragraph(f'<b>Ref:</b> {letter_reference(employee, today)}', styles['meta']), Paragraph(f'<b>Date:</b> {_long_date(today)}', styles['meta'])]],
        colWidths=[CONTENT_WIDTH * 0.62, CONTENT_WIDTH * 0.38],
    )
    meta.setStyle(TableStyle([('LEFTPADDING', (0, 0), (0, 0), 0), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))

    designation = f', holding the designation of <b>{employee.designation}</b>' if employee.designation else ''
    elements = [
        *_letterhead(company, company_name, styles),
        Spacer(1, 7 * mm), meta, Spacer(1, 8 * mm),
        Paragraph('EMPLOYMENT VERIFICATION LETTER', styles['title']),
        Spacer(1, 6 * mm),
        Paragraph('To Whom It May Concern,', styles['body']),
        Paragraph(f'This is to certify that <b>{name}</b> {_employment_status_statement(employee)}{designation}. '
                  'The employee\'s details, as held in the company\'s records, are given below.', styles['body']),
        Spacer(1, 2 * mm), _details_table(employee, styles), Spacer(1, 6 * mm),
        Paragraph('This letter is issued upon the employee\'s request for verification purposes such as banking, visa or tenancy '
                  'applications, and may be relied upon accordingly. It does not constitute a guarantee of continued employment.', styles['body']),
        Spacer(1, 12 * mm),
        _signature_block(company_name, styles),
    ]
    doc.build(elements, onFirstPage=_draw_page_frame, onLaterPages=_draw_page_frame)
    return buffer.getvalue()
