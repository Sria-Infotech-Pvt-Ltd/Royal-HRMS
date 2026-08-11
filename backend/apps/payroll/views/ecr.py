import io
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import error
from core.permissions import has_perm as _has_perm
from apps.payroll.models import PayrollCycle, EmployeePayslip, PayrollSettings

logger = logging.getLogger(__name__)

_ZERO = Decimal('0')


def _round_int(value: Decimal) -> int:
    """Round a Decimal to the nearest integer using standard half-up rounding."""
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _compute_ecr_rows(cycle: PayrollCycle, settings: PayrollSettings) -> list:
    """Return one dict per employee payslip, with all ECR columns computed."""
    eps_rate        = settings.eps_rate        / 100
    edli_wage_ceil  = settings.edli_wage_ceiling
    rows = []

    payslips = (
        EmployeePayslip.objects
        .filter(cycle=cycle)
        .select_related('employee', 'employee__profile')
        .order_by('employee__full_name')
    )

    for idx, ps in enumerate(payslips, start=1):
        emp     = ps.employee
        profile = getattr(emp, 'profile', None)

        basic        = ps.basic or _ZERO
        gross        = ps.gross_earnings or _ZERO
        pf_wage      = min(basic, settings.edli_wage_ceiling)   # same ceiling for PF/EDLI/EPS
        epf_contrib  = ps.pf_employee or _ZERO                   # employee 12%
        eps_contrib  = (pf_wage * eps_rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        epf_diff     = max(_ZERO, epf_contrib - eps_contrib)
        ncp_days     = _round_int(ps.lop_days or _ZERO)

        rows.append({
            'sr_no':              idx,
            'employee_name':      emp.full_name or '',
            'uan':                (profile.uan_number        if profile else '') or '',
            'name_as_per_aadhar': (profile.name_as_per_aadhar if profile else '') or '',
            'gross_wages':        _round_int(gross),
            'basic_wages':        _round_int(basic),
            'pension_wages':      _round_int(pf_wage),
            'edli_wages':         _round_int(min(basic, edli_wage_ceil)),
            'epf_contribution':   _round_int(epf_contrib),
            'eps_contribution':   int(eps_contrib),
            'epf_eps_difference': _round_int(epf_diff),
            'ncp_days':           ncp_days,
        })

    return rows


def _build_ecr_xlsx(cycle: PayrollCycle, rows: list) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ECR'

    # ── Header ─────────────────────────────────────────────────────────────────
    header_fill   = PatternFill('solid', fgColor='1A3A6E')
    header_font   = Font(bold=True, color='FFFFFF', size=10)
    center_align  = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin          = Side(border_style='thin', color='CCCCCC')
    cell_border   = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        'Sr No', 'Employee Name', 'UAN',
        'Employee Name as per Aadhar',
        'Gross Wages', 'Basic Wages', 'Pension Wages', 'EDLI Wages',
        'EPF Contribution', 'EPS Contribution', 'EPF and EPS Difference', 'NCP',
    ]
    col_widths = [6, 28, 14, 30, 12, 12, 12, 12, 14, 14, 20, 6]

    ws.row_dimensions[1].height = 36
    for col, (title, width) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = center_align
        cell.border    = cell_border
        ws.column_dimensions[cell.column_letter].width = width

    # ── Data rows ──────────────────────────────────────────────────────────────
    num_font    = Font(size=10)
    num_align   = Alignment(horizontal='right', vertical='center')
    text_align  = Alignment(horizontal='left',  vertical='center')

    totals = {k: 0 for k in [
        'gross_wages', 'basic_wages', 'pension_wages', 'edli_wages',
        'epf_contribution', 'eps_contribution', 'epf_eps_difference', 'ncp_days',
    ]}

    for row_idx, row in enumerate(rows, start=2):
        values = [
            row['sr_no'], row['employee_name'], row['uan'],
            row['name_as_per_aadhar'],
            row['gross_wages'], row['basic_wages'], row['pension_wages'], row['edli_wages'],
            row['epf_contribution'], row['eps_contribution'], row['epf_eps_difference'], row['ncp_days'],
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border    = cell_border
            cell.font      = num_font
            cell.alignment = num_align if isinstance(value, (int, float, Decimal)) else text_align

        for key in totals:
            totals[key] += row[key]

    # ── Totals row ─────────────────────────────────────────────────────────────
    total_row = len(rows) + 2
    total_fill = PatternFill('solid', fgColor='FFF9C4')
    total_font = Font(bold=True, size=10)

    total_values = [
        '', 'TOTAL', '', '',
        totals['gross_wages'], totals['basic_wages'], totals['pension_wages'], totals['edli_wages'],
        totals['epf_contribution'], totals['eps_contribution'], totals['epf_eps_difference'], totals['ncp_days'],
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


class CycleECRDownloadView(APIView):
    """GET /payroll/cycles/<pk>/ecr/  — download ECR Excel for a payroll cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not (_has_perm(request.user, 'payroll.view') or _has_perm(request.user, 'payroll.edit')):
            return error('You do not have permission to download the ECR file.', http_status=403)

        try:
            cycle = PayrollCycle.objects.select_related('branch').get(pk=cycle_pk)
        except PayrollCycle.DoesNotExist:
            return error('Payroll cycle not found.', http_status=404)

        # Branch-scoped access: a non-superuser can only download ECR for their own branch.
        # Users with no branch assigned (global admins) may access any cycle.
        if not getattr(request.user, 'is_superuser', False):
            user_branch_id = getattr(request.user, 'branch_id', None)
            if cycle.branch_id and user_branch_id and cycle.branch_id != user_branch_id:
                return error('You do not have access to this payroll cycle.', http_status=403)

        if cycle.status not in ('payslips_generated', 'query_window_open', 'paid', 'closed'):
            return error(
                'ECR is only available after payslips have been generated.',
                http_status=400,
            )

        settings_obj = PayrollSettings.objects.first()
        if settings_obj is None:
            settings_obj = PayrollSettings()

        rows = _compute_ecr_rows(cycle, settings_obj)
        if not rows:
            return error('No payslips found for this cycle.', http_status=404)

        try:
            xlsx_bytes = _build_ecr_xlsx(cycle, rows)
        except Exception as exc:
            logger.error('ECR xlsx generation failed for cycle %s: %s', cycle_pk, exc)
            return error('Failed to generate ECR file. Please try again.', http_status=500)

        period = cycle.cycle_start.strftime('%b_%Y') if cycle.cycle_start else 'cycle'
        try:
            branch_name = cycle.branch.branch_name if cycle.branch_id else 'All'
        except Exception:
            branch_name = 'All'
        branch = branch_name.replace(' ', '_')
        filename = f'ECR_{period}_{branch}.xlsx'

        response = HttpResponse(
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info('ECR downloaded for cycle %s by %s', cycle_pk, request.user.email)
        return response
