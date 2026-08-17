"""
ESIC monthly contribution file — the ESI equivalent of ecr.py's PF/EPS ECR
file. Field layout follows ESIC's commonly documented bulk-upload format
(IP Number, IP Name, Days worked, Total monthly wages, Reason code); ESIC's
exact portal spec is less uniformly published than EPFO's and has changed
before, so — same caveat as the EPFO ECR text file — validate the first real
upload against the current ESIC portal spec before relying on it for a live
filing.
"""
import csv
import io
import logging
from decimal import Decimal

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error
from apps.payroll.models import EmployeePayslip, PayrollCycle

logger = logging.getLogger(__name__)

_ZERO = Decimal('0')


def _compute_esic_rows(cycle: PayrollCycle) -> list:
    """
    One row per payslip that actually carries an ESI deduction. Eligibility
    is read from the payslip's own already-computed esi_employee/esi_employer
    amounts (set during real payroll processing, per-state wage-ceiling rules
    already applied there — see apps/payroll/views/cycles.py) rather than
    re-deriving the ceiling here, so this file can never disagree with what
    the actual payslip shows.
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
        gross = ps.gross_earnings or _ZERO
        days_paid = max(0, int(ps.total_working_days or 0) - int((ps.lop_days or _ZERO)))

        rows.append({
            'employee_name': emp.full_name or '',
            'esi_number':    (profile.esi_number if profile else '') or '',
            'days_paid':     days_paid,
            'gross_wages':   int(gross),
            'esi_employee':  int(ps.esi_employee or _ZERO),
            'esi_employer':  int(ps.esi_employer or _ZERO),
        })

    return rows


def _build_esic_csv(rows: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'IP Number', 'IP Name', 'No of Days Paid', 'Total Monthly Wages',
        'Employee Contribution', 'Employer Contribution',
    ])
    for row in rows:
        writer.writerow([
            row['esi_number'], row['employee_name'], row['days_paid'],
            row['gross_wages'], row['esi_employee'], row['esi_employer'],
        ])
    return buf.getvalue()


class CycleESICDownloadView(APIView):
    """GET /payroll/cycles/<pk>/esic/ — ESIC monthly contribution file for a payroll cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not (_has_perm(request.user, 'payroll.view') or _has_perm(request.user, 'payroll.edit')):
            return error('You do not have permission to download the ESIC file.', http_status=403)

        try:
            cycle = PayrollCycle.objects.select_related('branch').get(pk=cycle_pk)
        except PayrollCycle.DoesNotExist:
            return error('Payroll cycle not found.', http_status=404)

        if not getattr(request.user, 'is_superuser', False):
            user_branch_id = getattr(request.user, 'branch_id', None)
            if cycle.branch_id and user_branch_id and cycle.branch_id != user_branch_id:
                return error('You do not have access to this payroll cycle.', http_status=403)

        if cycle.status not in ('payslips_generated', 'query_window_open', 'paid', 'closed'):
            return error('ESIC file is only available after payslips have been generated.', http_status=400)

        rows = _compute_esic_rows(cycle)
        if not rows:
            return error('No ESI-eligible employees found for this cycle.', http_status=404)

        missing_esi = [r['employee_name'] for r in rows if not r['esi_number']]
        if missing_esi:
            return error(
                'The following ESI-eligible employees have no ESI number on file — '
                'add it before filing: ' + ', '.join(missing_esi)
            )

        csv_text = _build_esic_csv(rows)
        period = cycle.cycle_start.strftime('%b_%Y') if cycle.cycle_start else 'cycle'
        filename = f'ESIC_{period}.csv'

        response = HttpResponse(csv_text, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info('ESIC file downloaded for cycle %s by %s', cycle_pk, request.user.email)
        return response
