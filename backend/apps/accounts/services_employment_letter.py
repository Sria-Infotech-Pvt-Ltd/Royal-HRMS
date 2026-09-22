"""Renders a real employment verification letter PDF for an employee — no
document generator existed for this before (the ESS "Employment" tab's
verification-letter row was informational only, with no backing view; see
EmploymentTab.tsx). Mirrors the payroll app's
services_payslip_pdf.render_payslip_pdf: reportlab, rendered on demand, not
persisted to a FileField.

Company letterhead details are pulled from the real Company singleton row
(apps.accounts.models.Company) — never hardcoded, per CLAUDE.md.
"""
from io import BytesIO

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from apps.accounts.models import Company, User


def _company_letterhead_lines(company: Company | None) -> list[str]:
    """Registered-office address, one line per non-blank part — never a
    fabricated address when Company has not been configured yet."""
    if not company:
        return []
    address_parts = [company.address, company.city]
    if company.state:
        address_parts.append(company.state)
    if company.pin_code:
        address_parts.append(company.pin_code)
    lines = [', '.join(p for p in address_parts if p)]
    contact_bits = [b for b in (company.official_phone, company.primary_email, company.website) if b]
    if contact_bits:
        lines.append(' | '.join(contact_bits))
    return [line for line in lines if line]


def _employment_status_statement(employee: User) -> str:
    """A factual, real-data statement of current employment status — no
    fabricated tenure/role claims beyond what the User row actually holds."""
    if not employee.is_active:
        return 'is no longer an active employee of the company as of the date of this letter.'
    status_display = employee.get_employment_status_display()
    return f'is currently an active employee of the company, presently in {status_display} status.'


def render_employment_letter_pdf(employee: User) -> bytes:
    company = Company.objects.first()
    company_name = company.company_name if company else 'This company'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('LetterTitle', parent=styles['Heading1'], fontSize=15, spaceAfter=4)
    letterhead_style = ParagraphStyle('Letterhead', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
    body_style = ParagraphStyle('LetterBody', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=10)
    sub_style = ParagraphStyle('LetterSub', parent=styles['Normal'], fontSize=9, textColor=colors.grey)

    today_label = timezone.now().strftime('%d %B %Y')
    joining_label = employee.date_of_joining.strftime('%d %B %Y') if employee.date_of_joining else 'not on record'

    elements = [
        Paragraph(company_name, title_style),
    ]
    for line in _company_letterhead_lines(company):
        elements.append(Paragraph(line, letterhead_style))
    elements.append(Spacer(1, 12 * mm))
    elements.append(Paragraph(f'Date: {today_label}', body_style))
    elements.append(Paragraph('To Whom It May Concern,', body_style))
    elements.append(Paragraph('<b>Employment Verification Letter</b>', body_style))

    elements.append(Paragraph(
        f'This is to certify that <b>{employee.full_name}</b> '
        f'(Employee ID: <b>{employee.employee_id or "not on record"}</b>) '
        f'{_employment_status_statement(employee)}',
        body_style,
    ))
    elements.append(Paragraph(
        f'{employee.full_name} holds the designation of '
        f'<b>{employee.designation or "not on record"}</b> in the '
        f'<b>{employee.department or "not on record"}</b> department, '
        f'and joined the organisation on <b>{joining_label}</b>.',
        body_style,
    ))
    elements.append(Paragraph(
        'This letter is issued upon the employee\'s request for verification purposes such as '
        'banking, visa or tenancy applications, and may be relied upon accordingly.',
        body_style,
    ))
    elements.append(Spacer(1, 14 * mm))

    signature_rows = [
        ['For ' + company_name],
        [''],
        [''],
        ['HR Operations'],
    ]
    elements.append(Table(
        signature_rows,
        colWidths=[100 * mm],
        style=TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (0, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 1), (0, 2), 12),
        ]),
    ))
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        'This is a system-generated letter and does not require a physical signature.',
        sub_style,
    ))

    doc.build(elements)
    return buffer.getvalue()
