import logging
from datetime import timedelta

from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from core.pagination import paginate, paginated_data
from apps.payroll.models import (
    PayrollCycle,
    EmployeePayslip,
    PayslipQuery,
    PayrollSettings,
)
from apps.payroll.serializers import EmployeePayslipSerializer, PayslipQuerySerializer

logger = logging.getLogger(__name__)

HR_ADMIN_ROLES = frozenset(['system_admin', 'hr_admin'])


def _is_hr_admin(user):
    return user.role and user.role.name in HR_ADMIN_ROLES


class CyclePayslipListView(APIView):
    """List all payslips in a cycle (HR view)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can view all payslips.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        payslips = cycle.payslips.select_related('employee').order_by('employee__full_name')

        page_obj, paginator = paginate(payslips, request)
        serializer = EmployeePayslipSerializer(page_obj.object_list, many=True)
        return success(
            'Payslips retrieved.',
            paginated_data(paginator, page_obj, serializer.data),
        )


class PayslipDetailView(APIView):
    """Get a single payslip. Employee can only see their own."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payslip = get_object_or_404(EmployeePayslip.objects.select_related('employee', 'cycle'), pk=pk)

        if not _is_hr_admin(request.user) and payslip.employee_id != request.user.id:
            return error('You can only view your own payslips.', http_status=403)

        return success('Payslip retrieved.', EmployeePayslipSerializer(payslip).data)


class UpdatePayslipReimbBonusView(APIView):
    """HR updates reimbursements and/or bonus on a draft payslip."""

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can update payslip reimbursements.', http_status=403)

        payslip = get_object_or_404(EmployeePayslip, pk=pk)
        if payslip.status != EmployeePayslip.STATUS_DRAFT:
            return error('Only draft payslips can be updated.')

        settings_obj = PayrollSettings.objects.first()

        updated_fields = ['updated_at']
        if 'reimbursements' in request.data and settings_obj and settings_obj.enable_reimbursements:
            payslip.reimbursements = request.data['reimbursements']
            updated_fields.append('reimbursements')

        if 'bonus' in request.data and settings_obj and settings_obj.enable_bonuses:
            payslip.bonus = request.data['bonus']
            updated_fields.append('bonus')

        if 'lop_days' in request.data:
            payslip.lop_days = request.data['lop_days']
            per_day = payslip.gross_earnings / payslip.total_working_days if payslip.total_working_days else 0
            payslip.lop_deduction = per_day * payslip.lop_days
            updated_fields.extend(['lop_days', 'lop_deduction'])

        # Recalculate totals
        payslip.gross_earnings = (
            payslip.basic + payslip.hra + payslip.special_allowance
            + sum(payslip.other_earnings.values())
            + payslip.reimbursements + payslip.bonus
        )
        payslip.total_deductions = (
            payslip.lop_deduction + payslip.pf_employee
            + payslip.esi_employee + payslip.pt_deduction + payslip.lwf_employee
        )
        payslip.net_pay = payslip.gross_earnings - payslip.total_deductions
        updated_fields.extend(['gross_earnings', 'total_deductions', 'net_pay'])

        payslip.save(update_fields=updated_fields)
        return success('Payslip updated.', EmployeePayslipSerializer(payslip).data)


class DispatchPayslipsView(APIView):
    """Mark all draft payslips in a cycle as sent and open the query window."""

    permission_classes = [IsAuthenticated]

    def post(self, request, cycle_pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can dispatch payslips.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        if cycle.status != PayrollCycle.STATUS_PAYSLIPS_GENERATED:
            return error('Payslips must be generated before dispatching.')

        settings_obj = PayrollSettings.objects.first()
        window_hours = settings_obj.employee_query_window_hours if settings_obj else 24

        now = timezone.now()
        deadline = now + timedelta(hours=window_hours)

        cycle.payslips.filter(status=EmployeePayslip.STATUS_DRAFT).update(
            status=EmployeePayslip.STATUS_SENT,
            sent_at=now,
            query_deadline=deadline,
        )
        cycle.status = PayrollCycle.STATUS_QUERY_WINDOW_OPEN
        cycle.query_window_closes_at = deadline
        cycle.save(update_fields=['status', 'query_window_closes_at', 'updated_at'])

        logger.info(
            'Payslips dispatched for cycle %s by %s. Query window closes %s',
            cycle_pk, request.user.email, deadline,
        )
        return success(
            f'Payslips dispatched. Employee query window closes at {deadline.strftime("%Y-%m-%d %H:%M UTC")}.',
            {'query_deadline': deadline},
        )


class MyPayslipsView(APIView):
    """Employee view — list their own payslips."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payslips = EmployeePayslip.objects.filter(
            employee=request.user,
        ).select_related('cycle').order_by('-cycle__cycle_start')

        page_obj, paginator = paginate(payslips, request)
        serializer = EmployeePayslipSerializer(page_obj.object_list, many=True)
        return success(
            'Your payslips retrieved.',
            paginated_data(paginator, page_obj, serializer.data),
        )


class AcknowledgePayslipView(APIView):
    """Employee acknowledges their payslip (no query)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payslip = get_object_or_404(EmployeePayslip, pk=pk, employee=request.user)
        if payslip.status != EmployeePayslip.STATUS_SENT:
            return error('Payslip is not in a state that can be acknowledged.')

        payslip.status = EmployeePayslip.STATUS_ACKNOWLEDGED
        payslip.save(update_fields=['status', 'updated_at'])
        return success('Payslip acknowledged.')


class PayslipQueryListView(APIView):
    """Employee raises a query / HR lists all open queries."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _is_hr_admin(request.user):
            queries = PayslipQuery.objects.filter(
                status=PayslipQuery.STATUS_OPEN,
            ).select_related('payslip', 'payslip__employee', 'raised_by').order_by('-created_at')
        else:
            queries = PayslipQuery.objects.filter(
                raised_by=request.user,
            ).select_related('payslip').order_by('-created_at')

        serializer = PayslipQuerySerializer(queries, many=True)
        return success('Queries retrieved.', serializer.data)

    def post(self, request):
        payslip_id = request.data.get('payslip')
        description = request.data.get('description', '').strip()

        if not payslip_id or not description:
            return error('payslip and description are required.')

        payslip = get_object_or_404(EmployeePayslip, pk=payslip_id, employee=request.user)

        if payslip.status not in [EmployeePayslip.STATUS_SENT, EmployeePayslip.STATUS_ACKNOWLEDGED]:
            return error('Queries can only be raised on sent payslips.')

        if payslip.query_deadline and timezone.now() > payslip.query_deadline:
            return error('The query window for this payslip has closed.')

        query = PayslipQuery.objects.create(
            payslip=payslip,
            raised_by=request.user,
            description=description,
        )
        payslip.status = EmployeePayslip.STATUS_QUERIED
        payslip.save(update_fields=['status', 'updated_at'])

        logger.info('Payslip query raised by %s on payslip %s', request.user.email, payslip_id)
        return success('Query raised.', PayslipQuerySerializer(query).data, http_status=201)


class PayslipQueryResolveView(APIView):
    """HR resolves an open payslip query."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can resolve queries.', http_status=403)

        query = get_object_or_404(PayslipQuery, pk=pk, status=PayslipQuery.STATUS_OPEN)
        resolution_note = request.data.get('resolution_note', '').strip()
        if not resolution_note:
            return error('resolution_note is required.')

        query.status = PayslipQuery.STATUS_RESOLVED
        query.resolved_by = request.user
        query.resolution_note = resolution_note
        query.save(update_fields=['status', 'resolved_by', 'resolution_note', 'updated_at'])

        query.payslip.status = EmployeePayslip.STATUS_RESOLVED
        query.payslip.save(update_fields=['status', 'updated_at'])

        logger.info('Query %s resolved by %s', pk, request.user.email)
        return success('Query resolved.', PayslipQuerySerializer(query).data)
