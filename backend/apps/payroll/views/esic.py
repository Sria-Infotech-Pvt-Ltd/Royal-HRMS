"""
ESIC monthly contribution challan — an internal per-employee reconciliation
report (Client Name, ESIC No, Employee name, Attendance, Earn Basic,
Employee/Employer/Total Contribution), NOT the government's own Monthly
Contribution upload file. The actual ESIC Unified Portal upload format is
simpler (IP Number, IP Name, Days paid, Total Monthly Wages, Reason Code)
and needs no contribution figures at all — the portal computes those
itself from the wages you submit. This file exists because a company that
places its own employees at client sites (a staffing/contract-labor
business) needs its own record of what was contributed for each client's
placed workers, which the government file was never meant to show.

'Client Name' has no backing model in this codebase yet (no per-employee
"which client are they placed at" concept exists — see product decision
pending) — always blank until that's designed.
"""
import io
import logging
from decimal import Decimal

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error
from apps.payroll.models import EmployeePayslip, PayrollCycle
from .ecr import _get_authorized_cycle

logger = logging.getLogger(__name__)

_ZERO = Decimal('0')


def _compute_esic_rows(cycle: PayrollCycle) -> list:
    """
    One row per payslip that actually carries an ESI deduction. Eligibility
    and amounts are read from the payslip's own already-computed
    esi_employee/esi_employer fields (set during real payroll processing —
    per-state wage-ceiling, contribution-period continuity, and the
    sub-₹176/day employee-share exemption are all already applied there,
    see apps/payroll/views/cycles.py) rather than re-deriving any of that
    here, so this report can never disagree with what the actual payslip shows.
    """
    rows = []

    payslips = (
        EmployeePayslip.objects
        .filter(cycle=cycle)
        .select_related('employee', 'employee__profile')
        .order_by('employee__full_name')
    )

    for ps in payslips:
        if not (ps.esi_employee or ps.esi_employer):
            continue

        emp = ps.employee
        profile = getattr(emp, 'profile', None)
        # "Earn Basic" here means wages actually earned for days present —
        # gross_earnings on the payslip is deliberately the full un-prorated
        # monthly target (LOP is tracked as its own deduction line, standard
        # payroll convention, and left untouched everywhere else in this
        # system), so it's adjusted down by lop_deduction just for this
        # report's own column, without changing how ESI eligibility/
        # contribution amounts themselves are computed (apps/payroll/views/
        # cycles.py) — that's a separate, much bigger question about whether
        # the ESI wage-ceiling check itself should use actual-earned wages
        # instead of the full target gross, not decided here.
        earn_basic = (ps.gross_earnings or _ZERO) - (ps.lop_deduction or _ZERO)
        days_paid = max(0, int(ps.total_working_days or 0) - int((ps.lop_days or _ZERO)))
        esi_employee = int(ps.esi_employee or _ZERO)
        esi_employer = int(ps.esi_employer or _ZERO)

        rows.append({
            'client_name':        '',
            'esi_number':         (profile.esi_number if profile else '') or '',
            'employee_name':      emp.full_name or '',
            'employee_code':      emp.employee_id or '',
            'days_paid':          days_paid,
            'earn_basic':         int(earn_basic),
            'esi_employee':       esi_employee,
            'esi_employer':       esi_employer,
            'total_contribution': esi_employee + esi_employer,
        })

    return rows


def _build_esic_xlsx(rows: list) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ESIC Challan'

    header_fill  = PatternFill('solid', fgColor='1A3A6E')
    header_font  = Font(bold=True, color='FFFFFF', size=10)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin         = Side(border_style='thin', color='CCCCCC')
    cell_border  = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        'Client Name', 'ESIC No', 'Employee name', 'Attendance',
        'Earn Basic', 'Employee Contribution', 'Employer Contribution', 'Total Contribution',
    ]
    col_widths = [22, 16, 28, 12, 12, 18, 18, 16]

    ws.row_dimensions[1].height = 24
    for col, (title, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = center_align
        cell.border    = cell_border
        ws.column_dimensions[cell.column_letter].width = width

    num_font   = Font(size=10)
    num_align  = Alignment(horizontal='right', vertical='center')
    text_align = Alignment(horizontal='left',  vertical='center')

    totals = {k: 0 for k in ['days_paid', 'earn_basic', 'esi_employee', 'esi_employer', 'total_contribution']}

    for row_idx, row in enumerate(rows, start=2):
        values = [
            row['client_name'], row['esi_number'], row['employee_name'], row['days_paid'],
            row['earn_basic'], row['esi_employee'], row['esi_employer'], row['total_contribution'],
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border    = cell_border
            cell.font      = num_font
            cell.alignment = num_align if isinstance(value, (int, float, Decimal)) else text_align

        for key in totals:
            totals[key] += row[key]

    total_row  = len(rows) + 2
    total_fill = PatternFill('solid', fgColor='FFF9C4')
    total_font = Font(bold=True, size=10)

    total_values = [
        '', '', 'TOTAL', totals['days_paid'], totals['earn_basic'],
        totals['esi_employee'], totals['esi_employer'], totals['total_contribution'],
    ]
    for col, value in enumerate(total_values, start=1):
        cell = ws.cell(row=total_row, column=col, value=value)
        cell.font      = total_font
        cell.fill      = total_fill
        cell.border    = cell_border
        cell.alignment = num_align if isinstance(value, (int, float)) else text_align

    ws.freeze_panes = 'A2'

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class CycleESICDownloadView(APIView):
    """GET /payroll/cycles/<pk>/esic/ — ESIC Challan Excel report for a payroll cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        cycle, err = _get_authorized_cycle(request, cycle_pk, resource_label='ESIC Challan')
        if err:
            return err

        rows = _compute_esic_rows(cycle)
        if not rows:
            return error('No ESI-eligible employees found for this cycle.', http_status=404)

        missing_esi = [
            {'employee_name': r['employee_name'], 'employee_code': r['employee_code']}
            for r in rows if not r['esi_number']
        ]
        if missing_esi:
            names = ', '.join(m['employee_name'] for m in missing_esi)
            return error(
                f'{len(missing_esi)} ESI-eligible employee(s) have no ESI number on file — '
                f'add it before filing: {names}',
                data={'missing_esi_number': missing_esi},
                http_status=400,
            )

        xlsx_bytes = _build_esic_xlsx(rows)
        period = cycle.cycle_start.strftime('%m_%Y') if cycle.cycle_start else 'cycle'
        filename = f'ESIC_Challan_{period}.xlsx'

        response = HttpResponse(
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info('ESIC Challan downloaded for cycle %s by %s', cycle_pk, request.user.email)
        return response
