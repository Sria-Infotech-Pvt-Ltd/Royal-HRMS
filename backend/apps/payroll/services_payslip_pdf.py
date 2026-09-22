"""Renders a real payslip PDF from an EmployeePayslip's actual stored
figures — no PDF generation existed anywhere in this codebase before this
(the `payslip_pdf` FileField was declared on the model but nothing ever
populated it), so "Download payslip" always returned a 404. This renders
on demand rather than persisting a file, since no cycle-run step exists
to build/cache one ahead of time.

Layout matches the reference salary-statement template: dark header band
(company/brand), section header bars, employee/attendance detail grids, a
two-column earnings/deductions table, a net-pay banner with the amount
spelled out in words, a YTD + employer-contributions section, and a
"CONFIDENTIAL" watermark — all drawn directly on the canvas for exact
control over each band's position, rather than a flowing Platypus layout.
"""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

from apps.accounts.models import Company
from apps.payroll.models import EmployeePayslip, PayrollSettings

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

NAVY_DARK = colors.HexColor('#141B3C')
NAVY_MID = colors.HexColor('#1E2650')
LAVENDER = colors.HexColor('#EEF0FB')
PURPLE_TEXT = colors.HexColor('#4C4F6B')
INK = colors.HexColor('#1A1A2E')
GREY = colors.HexColor('#767A94')
LINE = colors.HexColor('#E3E5F2')
NET_PAY_BAND = colors.HexColor('#241E52')


def _inr(amount) -> str:
    return f'{Decimal(amount or 0):,.2f}'


# ─── Indian-numbering amount-in-words ────────────────────────────────────────

_ONES = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
    'Seventeen', 'Eighteen', 'Nineteen',
]
_TENS = [
    '', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety',
]


def _two_digit_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (f'-{_ONES[n % 10]}' if n % 10 else '')).strip('-')


def _three_digit_words(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f'{_ONES[n // 100]} Hundred')
        n %= 100
    if n:
        parts.append(_two_digit_words(n))
    return ' '.join(parts)


def amount_in_words(amount) -> str:
    """Indian numbering (crore/lakh/thousand), rupees only — matches the
    reference payslip's "ONE LAKH TWENTY-EIGHT THOUSAND FOUR HUNDRED FIFTY
    ONLY" style output."""
    rupees = int(Decimal(amount or 0))
    if rupees == 0:
        return 'ZERO ONLY'
    crore, rem = divmod(rupees, 10_000_000)
    lakh, rem = divmod(rem, 100_000)
    thousand, rem = divmod(rem, 1_000)
    hundred_and_below = rem

    groups = []
    if crore:
        groups.append(f'{_three_digit_words(crore)} Crore')
    if lakh:
        groups.append(f'{_three_digit_words(lakh)} Lakh')
    if thousand:
        groups.append(f'{_three_digit_words(thousand)} Thousand')
    if hundred_and_below:
        groups.append(_three_digit_words(hundred_and_below))

    return (' '.join(groups) + ' Only').upper()


def _fmt_date(d) -> str:
    return d.strftime('%d %B %Y') if d else '-'


class _Ctx:
    """Small helper bundling everything the drawing functions need, so each
    section-drawing function stays short and focused (CLAUDE.md's 50-line
    function guideline)."""

    def __init__(self, c: pdfcanvas.Canvas, payslip: EmployeePayslip):
        self.c = c
        self.payslip = payslip
        self.employee = payslip.employee
        self.profile = getattr(self.employee, 'profile', None)
        self.cycle = payslip.cycle
        self.company = Company.objects.first()
        settings_obj = PayrollSettings.objects.first()
        self.gratuity_rate = settings_obj.gratuity_rate if settings_obj else Decimal('0')
        self.y = PAGE_H - 0  # cursor, set by header


def _draw_watermark(c: pdfcanvas.Canvas):
    c.saveState()
    c.setFont('Helvetica-Bold', 72)
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.06))
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, 'CONFIDENTIAL')
    c.restoreState()


def _draw_header(ctx: _Ctx) -> float:
    c = ctx.c
    company = ctx.company
    company_name = company.company_name if company else 'This company'
    city = company.city if company and company.city else ''
    state = company.state if company and company.state else ''
    location = ', '.join(filter(None, [city, state, 'India' if city or state else '']))

    c.setFillColor(NAVY_DARK)
    c.rect(0, PAGE_H - 62 * mm, PAGE_W, 62 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 20)
    c.drawString(MARGIN, PAGE_H - 18 * mm, 'AIRA')
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, PAGE_H - 23 * mm, 'ARTIFICIAL INTELLIGENCE RESOURCES ASSISTANCE')

    c.setFont('Helvetica-Bold', 13)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 18 * mm, 'SALARY STATEMENT')
    c.setFont('Helvetica', 10)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 23 * mm, ctx.cycle.cycle_start.strftime('%B %Y'))

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.9))
    c.setFont('Helvetica-Bold', 10)
    c.drawString(MARGIN, PAGE_H - 34 * mm, company_name.upper())
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, PAGE_H - 38.5 * mm, f'{location} | Payroll statement' if location else 'Payroll statement')

    return PAGE_H - 62 * mm


def _section_bar(ctx: _Ctx, y: float, title: str) -> float:
    c = ctx.c
    bar_h = 7 * mm
    c.setFillColor(LAVENDER)
    c.rect(0, y - bar_h, PAGE_W, bar_h, fill=1, stroke=0)
    c.setFillColor(PURPLE_TEXT)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGIN, y - bar_h + 2.3 * mm, title)
    return y - bar_h


def _grid_row(ctx: _Ctx, y: float, cells: list[tuple[str, str]]) -> float:
    """Draws one row of (label, value) pairs evenly spaced across the page
    width, label small/grey above the bold value — the "EMPLOYEE & PAYROLL
    DETAILS" / "ATTENDANCE & PAYMENT" style grid."""
    c = ctx.c
    usable_w = PAGE_W - 2 * MARGIN
    col_w = usable_w / len(cells)
    for i, (label, value) in enumerate(cells):
        x = MARGIN + i * col_w
        c.setFillColor(GREY)
        c.setFont('Helvetica', 6.5)
        c.drawString(x, y - 5 * mm, label.upper())
        c.setFillColor(INK)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(x, y - 9.5 * mm, value or '-')
    return y - 14 * mm


def _employee_details_grid(ctx: _Ctx, y: float) -> float:
    e, p = ctx.employee, ctx.profile
    y = _section_bar(ctx, y, 'EMPLOYEE & PAYROLL DETAILS')
    y = _grid_row(ctx, y, [
        ('Employee name', e.full_name), ('Employee ID', e.employee_id or '-'),
        ('Designation', e.designation or '-'), ('Department', e.department or '-'),
    ])
    y = _grid_row(ctx, y, [
        ('Work location', e.work_location or e.branch or '-'),
        ('Date of joining', _fmt_date(e.date_of_joining)),
        ('PF number', (p.pf_number if p else '') or '-'),
        ('Pay date', _fmt_date(ctx.cycle.pay_date)),
    ])
    return y


def _attendance_grid(ctx: _Ctx, y: float) -> float:
    slip, p = ctx.payslip, ctx.profile
    paid_days = Decimal(slip.total_working_days or 0) - Decimal(slip.lop_days or 0)
    bank_masked = f'XXXX{p.account_number[-4:]}' if (p and p.account_number and len(p.account_number) >= 4) else '-'
    y = _section_bar(ctx, y, 'ATTENDANCE & PAYMENT')
    y = _grid_row(ctx, y, [
        ('Calendar days', str(slip.total_working_days or 0)),
        ('Paid days', f'{paid_days:.2f}'),
        ('LOP days', f'{Decimal(slip.lop_days or 0):.2f}'),
        ('Bank', (p.bank_name if p else '') or '-'),
        ('Account', bank_masked),
    ])
    return y


def _earnings_deductions(ctx: _Ctx, y: float) -> float:
    c, slip = ctx.c, ctx.payslip
    y = _section_bar(ctx, y, 'EARNINGS & DEDUCTIONS')
    y -= 4 * mm

    earnings = [('Basic salary', slip.basic), ('House rent allowance', slip.hra)]
    if slip.special_allowance:
        earnings.append(('Special allowance', slip.special_allowance))
    for name, amt in (slip.other_earnings or {}).items():
        if Decimal(amt or 0):
            earnings.append((name, amt))

    deductions = [('Provident fund', slip.pf_employee), ('Professional tax', slip.pt_deduction)]
    if slip.income_tax:
        deductions.append(('Income tax (TDS)', slip.income_tax))
    other_ded = Decimal(slip.lwf_employee or 0) + Decimal(slip.adjustments_deduction or 0)
    if other_ded:
        deductions.append(('Other deductions', other_ded))

    col_l_x, col_r_x = MARGIN, PAGE_W / 2 + 4 * mm
    col_w = PAGE_W / 2 - MARGIN - 4 * mm
    amt_offset = col_w - 8 * mm

    c.setFillColor(INK)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(col_l_x, y, 'EARNINGS')
    c.drawRightString(col_l_x + col_w, y, 'AMOUNT (INR)')
    c.drawString(col_r_x, y, 'DEDUCTIONS')
    c.drawRightString(col_r_x + col_w, y, 'AMOUNT (INR)')
    y -= 2 * mm
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 5 * mm

    rows = max(len(earnings), len(deductions))
    row_top = y
    for i in range(rows):
        ry = row_top - i * 6.5 * mm
        c.setFont('Helvetica', 8.5)
        c.setFillColor(INK)
        if i < len(earnings):
            label, amt = earnings[i]
            c.drawString(col_l_x, ry, label)
            c.drawRightString(col_l_x + col_w, ry, _inr(amt))
        if i < len(deductions):
            label, amt = deductions[i]
            c.drawString(col_r_x, ry, label)
            c.drawRightString(col_r_x + col_w, ry, _inr(amt))
    y = row_top - rows * 6.5 * mm - 2 * mm

    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(col_l_x, y, 'GROSS EARNINGS')
    c.drawRightString(col_l_x + col_w, y, _inr(ctx.payslip.gross_earnings))
    c.drawString(col_r_x, y, 'TOTAL DEDUCTIONS')
    c.drawRightString(col_r_x + col_w, y, _inr(ctx.payslip.total_deductions))
    return y - 8 * mm


def _net_pay_band(ctx: _Ctx, y: float) -> float:
    c, slip = ctx.c, ctx.payslip
    band_h = 16 * mm
    c.setFillColor(NET_PAY_BAND)
    c.rect(0, y - band_h, PAGE_W, band_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, y - 6 * mm, 'NET PAY')
    c.setFont('Helvetica-Bold', 16)
    c.drawString(MARGIN, y - 12.5 * mm, f'INR {_inr(slip.net_pay)}')
    c.setFont('Helvetica', 8)
    words = amount_in_words(slip.net_pay)
    c.drawRightString(PAGE_W - MARGIN, y - 7 * mm, words[:len(words) // 2] if len(words) > 45 else words)
    if len(words) > 45:
        c.drawRightString(PAGE_W - MARGIN, y - 11 * mm, words[len(words) // 2:])
    return y - band_h - 6 * mm


def _ytd_and_employer(ctx: _Ctx, y: float) -> float:
    slip = ctx.payslip
    gratuity = (Decimal(slip.basic or 0) * ctx.gratuity_rate / 100) if ctx.gratuity_rate else Decimal('0')
    employer_total = Decimal(slip.pf_employer or 0) + Decimal(slip.esi_employer or 0) + gratuity

    y = _section_bar(ctx, y, 'YEAR-TO-DATE & EMPLOYER CONTRIBUTIONS')
    y = _grid_row(ctx, y, [
        ('YTD gross', f'INR {_inr(ctx.ytd_gross)}'),
        ('YTD income tax', f'INR {_inr(ctx.ytd_income_tax)}'),
        ('YTD net pay', f'INR {_inr(ctx.ytd_net)}'),
        ('Payroll periods', str(ctx.ytd_periods)),
    ])
    y = _grid_row(ctx, y, [
        ('Employer PF', f'INR {_inr(slip.pf_employer)}'),
        ('Gratuity provision', f'INR {_inr(gratuity)}'),
        ('Insurance premium', f'INR {_inr(slip.esi_employer)}'),
        ('Total contribution', f'INR {_inr(employer_total)}'),
    ])
    return y


def _footer(ctx: _Ctx, y: float):
    c = ctx.c
    company = ctx.company
    support_email = (company.primary_email if company and company.primary_email else '') or 'support@company.local'

    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm
    c.setFillColor(GREY)
    c.setFont('Helvetica', 7.5)
    c.drawString(MARGIN, y, 'This computer-generated payslip does not require a physical signature.')
    y -= 4 * mm
    c.drawString(MARGIN, y, 'Generated securely from AIRA ESS. Access and downloads are audit logged.')
    y -= 8 * mm

    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 5 * mm
    c.setFillColor(colors.HexColor('#B5303B'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(MARGIN, y, 'CONFIDENTIAL - FOR EMPLOYEE USE ONLY')
    c.setFillColor(GREY)
    c.setFont('Helvetica', 7)
    generated = ctx.payslip.updated_at.strftime('%d %B %Y') if ctx.payslip.updated_at else ''
    c.drawRightString(PAGE_W - MARGIN, y, support_email)
    y -= 4 * mm
    c.drawString(MARGIN, y, f'Generated {generated} | AIRA Payroll | Page 1 of 1')


def render_payslip_pdf(payslip: EmployeePayslip, ytd: dict | None = None) -> bytes:
    """`ytd` (optional) = {'gross': Decimal, 'net': Decimal, 'income_tax':
    Decimal, 'periods': int} for the YTD section — when omitted, this
    payslip's own figures are used as a single-period fallback so the PDF
    still renders sensibly on its own."""
    buffer = BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    ctx = _Ctx(c, payslip)
    ytd = ytd or {
        'gross': payslip.gross_earnings, 'net': payslip.net_pay,
        'income_tax': payslip.income_tax, 'periods': 1,
    }
    ctx.ytd_gross = ytd['gross']
    ctx.ytd_net = ytd['net']
    ctx.ytd_income_tax = ytd['income_tax']
    ctx.ytd_periods = ytd['periods']

    _draw_watermark(c)
    y = _draw_header(ctx)
    y = _employee_details_grid(ctx, y)
    y = _attendance_grid(ctx, y)
    y = _earnings_deductions(ctx, y)
    y = _net_pay_band(ctx, y)
    y = _ytd_and_employer(ctx, y)
    _footer(ctx, y - 4 * mm)

    c.showPage()
    c.save()
    return buffer.getvalue()
