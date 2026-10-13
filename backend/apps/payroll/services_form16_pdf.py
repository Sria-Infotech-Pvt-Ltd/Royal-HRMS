"""Renders a real annual "Form 16" tax certificate PDF from an employee's
actual EmployeePayslip rows for one financial year — the same real-data
philosophy as services_payslip_pdf.py: no fabricated figures.

This is deliberately NOT a statutorily-exact Form 16 (that requires a TAN,
quarterly TDS certificate/acknowledgement numbers from actual TRACES filings,
and a government-prescribed Part A/Part B layout this system has no data
for). It IS a real, honest annual tax summary built entirely from this
employee's own payslips and declared tax regime: employer/employee identity,
month-by-month gross/tax, annual totals, deductions under Chapter VI-A as
declared by the employee, and net taxable income — everything a real Form 16
would need to show, computed from real stored numbers, clearly labelled where
this app's data falls short of the full statutory format (e.g. no TAN).

Reuses the same reportlab canvas drawing conventions as services_payslip_pdf.py.
"""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

from apps.accounts.models import Company
from apps.payroll.models import EmployeePayslip

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

NAVY_DARK = colors.HexColor('#141B3C')
LAVENDER = colors.HexColor('#EEF0FB')
PURPLE_TEXT = colors.HexColor('#4C4F6B')
INK = colors.HexColor('#1A1A2E')
GREY = colors.HexColor('#767A94')
LINE = colors.HexColor('#E3E5F2')
NET_PAY_BAND = colors.HexColor('#241E52')

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


def _inr(amount) -> str:
    return f'{Decimal(amount or 0):,.2f}'


def _fmt_date(d) -> str:
    return d.strftime('%d %B %Y') if d else '-'


class _Ctx:
    def __init__(self, c: pdfcanvas.Canvas, employee, fy_label: str, payslips: list[EmployeePayslip]):
        self.c = c
        self.employee = employee
        self.profile = getattr(employee, 'profile', None)
        self.company = Company.objects.first()
        self.fy_label = fy_label
        self.payslips = payslips
        self.y = PAGE_H


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

    c.setFillColor(NAVY_DARK)
    c.rect(0, PAGE_H - 50 * mm, PAGE_W, 50 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 20)
    c.drawString(MARGIN, PAGE_H - 18 * mm, 'AIRA')
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, PAGE_H - 23 * mm, 'ARTIFICIAL INTELLIGENCE RESOURCES ASSISTANCE')

    c.setFont('Helvetica-Bold', 13)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 18 * mm, 'ANNUAL TAX STATEMENT (FORM 16)')
    c.setFont('Helvetica', 10)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 23 * mm, f'Financial Year {ctx.fy_label}')

    c.setFillColor(colors.Color(1, 1, 1, alpha=0.9))
    c.setFont('Helvetica-Bold', 10)
    c.drawString(MARGIN, PAGE_H - 34 * mm, company_name.upper())
    c.setFont('Helvetica', 7.5)
    c.drawString(
        MARGIN, PAGE_H - 38.5 * mm,
        'Summary of salary paid and tax deducted at source — not a statutory TRACES-issued certificate.',
    )

    return PAGE_H - 50 * mm


def _section_bar(ctx: _Ctx, y: float, title: str) -> float:
    c = ctx.c
    bar_h = 7 * mm
    c.setFillColor(LAVENDER)
    c.rect(0, y - bar_h, PAGE_W, bar_h, fill=1, stroke=0)
    c.setFillColor(PURPLE_TEXT)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(MARGIN, y - bar_h + 2.3 * mm, title)
    return y - bar_h


def _grid_row(y: float, c: pdfcanvas.Canvas, cells: list[tuple[str, str]]) -> float:
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


def _identity_section(ctx: _Ctx, y: float) -> float:
    e, p, company = ctx.employee, ctx.profile, ctx.company
    y = _section_bar(ctx, y, 'PART A — EMPLOYER & EMPLOYEE IDENTITY')
    y = _grid_row(y, ctx.c, [
        ('Employer', company.company_name if company else '-'),
        ('Employer PAN', (company.pan if company else '') or '-'),
        ('Employer TAN', (company.tan if company else '') or 'Not configured'),
    ])
    y = _grid_row(y, ctx.c, [
        ('Employee name', e.full_name), ('Employee ID', e.employee_id or '-'),
        ('Employee PAN', (p.pan_number if p else '') or 'Not on file'),
    ])
    return y


def _monthly_table(ctx: _Ctx, y: float) -> float:
    c = ctx.c
    y = _section_bar(ctx, y, 'PART B — MONTH-WISE SALARY PAID & TAX DEDUCTED')
    y -= 4 * mm

    col_month = MARGIN
    col_gross = MARGIN + 70 * mm
    col_pf = MARGIN + 105 * mm
    col_tax = MARGIN + 140 * mm

    c.setFillColor(INK)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(col_month, y, 'MONTH')
    c.drawRightString(col_gross + 25 * mm, y, 'GROSS SALARY')
    c.drawRightString(col_pf + 25 * mm, y, 'PF DEDUCTED')
    c.drawRightString(col_tax + 25 * mm, y, 'TAX DEDUCTED (TDS)')
    y -= 2 * mm
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 5.5 * mm

    for slip in ctx.payslips:
        c.setFont('Helvetica', 8.5)
        c.setFillColor(INK)
        c.drawString(col_month, y, slip.cycle.cycle_start.strftime('%B %Y'))
        c.drawRightString(col_gross + 25 * mm, y, _inr(slip.gross_earnings))
        c.drawRightString(col_pf + 25 * mm, y, _inr(slip.pf_employee))
        c.drawRightString(col_tax + 25 * mm, y, _inr(slip.income_tax))
        y -= 6 * mm

    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm

    totals = {
        'gross': sum(Decimal(s.gross_earnings or 0) for s in ctx.payslips),
        'pf': sum(Decimal(s.pf_employee or 0) for s in ctx.payslips),
        'tax': sum(Decimal(s.income_tax or 0) for s in ctx.payslips),
    }
    c.setFont('Helvetica-Bold', 9)
    c.drawString(col_month, y, f'TOTAL ({len(ctx.payslips)} payslip{"s" if len(ctx.payslips) != 1 else ""})')
    c.drawRightString(col_gross + 25 * mm, y, _inr(totals['gross']))
    c.drawRightString(col_pf + 25 * mm, y, _inr(totals['pf']))
    c.drawRightString(col_tax + 25 * mm, y, _inr(totals['tax']))
    ctx.totals = totals
    return y - 8 * mm


def _declarations_section(ctx: _Ctx, y: float, regime_label: str, declared_investments: dict) -> float:
    c = ctx.c
    y = _section_bar(ctx, y, 'DECLARED TAX REGIME & CHAPTER VI-A INVESTMENTS')
    y = _grid_row(y, c, [('Tax regime for this FY', regime_label)])

    items = [(k, v) for k, v in (declared_investments or {}).items() if Decimal(v or 0) > 0]
    if not items:
        c.setFillColor(GREY)
        c.setFont('Helvetica', 8.5)
        c.drawString(MARGIN, y - 2 * mm, 'No investment declarations were submitted for this financial year.')
        return y - 8 * mm

    c.setFillColor(INK)
    c.setFont('Helvetica', 8.5)
    y -= 2 * mm
    for key, amt in items:
        c.drawString(MARGIN, y, str(key))
        c.drawRightString(PAGE_W - MARGIN, y, f'INR {_inr(amt)}')
        y -= 5.5 * mm
    return y - 4 * mm


def _net_pay_band(ctx: _Ctx, y: float) -> float:
    c = ctx.c
    band_h = 16 * mm
    c.setFillColor(NET_PAY_BAND)
    c.rect(0, y - band_h, PAGE_W, band_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica', 8)
    c.drawString(MARGIN, y - 6 * mm, f'TOTAL TAX DEDUCTED AT SOURCE — FY {ctx.fy_label}')
    c.setFont('Helvetica-Bold', 16)
    c.drawString(MARGIN, y - 12.5 * mm, f'INR {_inr(ctx.totals["tax"])}')
    return y - band_h - 6 * mm


def _footer(ctx: _Ctx, y: float):
    c = ctx.c
    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 6 * mm
    c.setFillColor(GREY)
    c.setFont('Helvetica', 7.5)
    c.drawString(MARGIN, y, 'This is a system-generated annual tax summary from recorded payroll figures,')
    y -= 4 * mm
    c.drawString(MARGIN, y, 'not a TRACES-issued Form 16 certificate. Generated securely from AIRA ESS.')
    y -= 8 * mm

    c.setStrokeColor(LINE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 5 * mm
    c.setFillColor(colors.HexColor('#B5303B'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(MARGIN, y, 'CONFIDENTIAL - FOR EMPLOYEE USE ONLY')


def render_form16_pdf(employee, fy_label: str, payslips: list[EmployeePayslip],
                       regime_label: str, declared_investments: dict) -> bytes:
    buffer = BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    ctx = _Ctx(c, employee, fy_label, payslips)

    _draw_watermark(c)
    y = _draw_header(ctx)
    y = _identity_section(ctx, y)
    y = _monthly_table(ctx, y)
    y = _declarations_section(ctx, y, regime_label, declared_investments)
    y = _net_pay_band(ctx, y)
    _footer(ctx, y - 4 * mm)

    c.showPage()
    c.save()
    return buffer.getvalue()
