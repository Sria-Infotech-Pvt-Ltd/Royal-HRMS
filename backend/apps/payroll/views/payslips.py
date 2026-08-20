import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import models as django_models
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from apps.branch.models import Branch
from apps.payroll.models import (
    PayrollCycle,
    EmployeePayslip,
    PayslipQuery,
    PayrollSettings,
)
from apps.payroll.serializers import EmployeePayslipSerializer, PayslipQuerySerializer

logger = logging.getLogger(__name__)


def _resolve_user_branch(user):
    """Return the Branch object for a non-org-wide user's assigned branch, or None."""
    if not user.branch:
        return None
    return Branch.objects.filter(branch_name=user.branch, status=Branch.STATUS_ACTIVE).first()


class CyclePayslipListView(APIView):
    """List all payslips in a cycle (HR view)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view all payslips.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        # Same branch scoping as every other payroll list (cycles.py) — a
        # non-org-wide user (e.g. Branch Admin, who has payroll.view but not
        # settings.edit) could otherwise list every branch's payslips just by
        # knowing/guessing a cycle id from another branch.
        if not _has_perm(request.user, 'settings.edit'):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.id:
                return error('Payroll cycle not found.', http_status=404)
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

        if not _has_perm(request.user, 'payroll.view') and payslip.employee_id != request.user.id:
            return error('You can only view your own payslips.', http_status=403)

        return success('Payslip retrieved.', EmployeePayslipSerializer(payslip).data)


def _apply_expense_ids(payslip, expense_ids):
    """Link expense records to a payslip and return their total amount."""
    from apps.hrms.models import Expense
    # Unlink any expenses previously linked to this payslip
    Expense.objects.filter(disbursed_in_payslip=payslip).update(disbursed_in_payslip=None)
    if not expense_ids:
        return 0
    # Only accept approved expenses belonging to this employee that are currently undisbursed
    rows = list(Expense.objects.filter(
        id__in=expense_ids,
        employee=payslip.employee,
        status='approved',
        disbursed_in_payslip__isnull=True,
    ).values_list('id', 'amount'))
    if not rows:
        return 0
    valid_ids = [r[0] for r in rows]
    total = sum(r[1] for r in rows)
    Expense.objects.filter(id__in=valid_ids).update(disbursed_in_payslip=payslip)
    return total


class UpdatePayslipReimbBonusView(APIView):
    """HR updates reimbursements and/or bonus on a draft payslip."""

    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk)

    def _update(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update payslip reimbursements.', http_status=403)

        payslip = get_object_or_404(EmployeePayslip, pk=pk)
        if payslip.status != EmployeePayslip.STATUS_DRAFT:
            return error('Only draft payslips can be updated.')

        settings_obj = PayrollSettings.objects.first()
        updated_fields = ['updated_at']

        # Reimbursements: prefer expense_ids (traceable) over flat amount
        if 'expense_ids' in request.data and settings_obj and settings_obj.enable_reimbursements:
            payslip.reimbursements = _apply_expense_ids(payslip, request.data['expense_ids'])
            updated_fields.append('reimbursements')
        elif 'reimbursements' in request.data and settings_obj and settings_obj.enable_reimbursements:
            try:
                payslip.reimbursements = Decimal(str(request.data['reimbursements']))
            except (InvalidOperation, TypeError, ValueError):
                return error('reimbursements must be a valid number.')
            updated_fields.append('reimbursements')

        # Bonuses: prefer breakdown (typed) over flat amount
        if 'bonus_breakdown' in request.data and settings_obj and settings_obj.enable_bonuses:
            breakdown = request.data['bonus_breakdown']
            if not isinstance(breakdown, list):
                return error('bonus_breakdown must be a list.')
            try:
                payslip.bonus = sum(
                    (Decimal(str(e.get('amount', 0) or 0)) for e in breakdown),
                    Decimal('0'),
                )
            except (InvalidOperation, TypeError, ValueError):
                return error('bonus_breakdown amounts must be valid numbers.')
            payslip.bonus_breakdown = breakdown
            updated_fields.extend(['bonus_breakdown', 'bonus'])
        elif 'bonus' in request.data and settings_obj and settings_obj.enable_bonuses:
            try:
                payslip.bonus = Decimal(str(request.data['bonus']))
            except (InvalidOperation, TypeError, ValueError):
                return error('bonus must be a valid number.')
            updated_fields.append('bonus')

        if 'lop_days' in request.data:
            try:
                payslip.lop_days = Decimal(str(request.data['lop_days']))
            except (InvalidOperation, TypeError, ValueError):
                return error('lop_days must be a valid number.')
            per_day = payslip.gross_earnings / payslip.total_working_days if payslip.total_working_days else 0
            payslip.lop_deduction = per_day * payslip.lop_days
            updated_fields.extend(['lop_days', 'lop_deduction'])

        other_earnings_total = sum(
            (Decimal(str(v)) for v in payslip.other_earnings.values()),
            Decimal(0),
        )
        payslip.gross_earnings = (
            payslip.basic + payslip.hra + payslip.special_allowance
            + other_earnings_total
            + payslip.reimbursements + payslip.bonus
            + payslip.adjustments_earning
        )
        payslip.total_deductions = (
            payslip.lop_deduction + payslip.pf_employee
            + payslip.esi_employee + payslip.pt_deduction + payslip.lwf_employee
            + payslip.adjustments_deduction
        )
        payslip.net_pay = payslip.gross_earnings - payslip.total_deductions
        updated_fields.extend(['gross_earnings', 'total_deductions', 'net_pay'])

        payslip.save(update_fields=list(set(updated_fields)))
        logger.info('Payslip %s reimb/bonus updated by %s', pk, request.user.email)
        return success('Payslip updated.', EmployeePayslipSerializer(payslip).data)


class ExpenseSummaryForCycleView(APIView):
    """Approved, undisbursed expenses per employee for a payroll cycle (for auto-population)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view this.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        payslips = list(cycle.payslips.select_related('employee').all())
        if not payslips:
            return success('No payslips in this cycle.', [])

        payslip_ids = [p.id for p in payslips]
        emp_payslip = {p.employee_id: p for p in payslips}

        from apps.hrms.models import Expense
        expenses = Expense.objects.filter(
            employee_id__in=list(emp_payslip.keys()),
            status='approved',
        ).filter(
            django_models.Q(disbursed_in_payslip__isnull=True) |
            django_models.Q(disbursed_in_payslip_id__in=payslip_ids)
        ).select_related('employee').order_by('expense_date')

        by_employee = defaultdict(list)
        for exp in expenses:
            by_employee[exp.employee_id].append(exp)

        result = []
        for emp_id, payslip in emp_payslip.items():
            emp_expenses = by_employee.get(emp_id, [])
            if not emp_expenses:
                continue
            result.append({
                'payslip_id': str(payslip.id),
                'employee_id': str(emp_id),
                'employee_name': payslip.employee.full_name,
                'employee_code': payslip.employee.employee_id,
                'current_reimbursements': str(payslip.reimbursements),
                'expenses': [
                    {
                        'id': str(e.id),
                        'title': e.title,
                        'category': e.category,
                        'amount': str(e.amount),
                        'expense_date': str(e.expense_date),
                        'already_included': e.disbursed_in_payslip_id == payslip.id,
                    }
                    for e in emp_expenses
                ],
            })

        return success('Expense summary retrieved.', result)


class ReferralBonusSummaryForCycleView(APIView):
    """Approved referral bonuses per employee for auto-populating payroll bonus entries."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view this.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        payslips = list(cycle.payslips.select_related('employee').all())
        if not payslips:
            return success('No payslips in this cycle.', [])

        emp_payslip = {p.employee_id: p for p in payslips}

        from apps.recruitment.models import ReferralBonus
        referral_bonuses = ReferralBonus.objects.filter(
            referrer_id__in=list(emp_payslip.keys()),
            status='approved',
        ).select_related('referrer', 'candidate')

        by_referrer = defaultdict(list)
        for bonus in referral_bonuses:
            by_referrer[bonus.referrer_id].append(bonus)

        result = []
        for emp_id, payslip in emp_payslip.items():
            bonuses = by_referrer.get(emp_id, [])
            if not bonuses:
                continue
            result.append({
                'payslip_id': str(payslip.id),
                'employee_id': str(emp_id),
                'employee_name': payslip.employee.full_name,
                'employee_code': payslip.employee.employee_id,
                'referral_bonuses': [
                    {
                        'id': str(b.id),
                        'bonus_amount': str(b.bonus_amount),
                        'candidate_name': getattr(b.candidate, 'full_name', None) or str(b.candidate),
                    }
                    for b in bonuses
                ],
            })

        return success('Referral bonus summary retrieved.', result)


class DispatchPayslipsView(APIView):
    """Mark all draft payslips in a cycle as sent and open the query window."""

    permission_classes = [IsAuthenticated]

    def post(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.edit'):
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
        if not _has_perm(request.user, 'payroll.view_own'):
            return error('You do not have permission to view payslips.', http_status=403)

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
        if not _has_perm(request.user, 'payroll.view_own'):
            return error('You do not have permission to view payslips.', http_status=403)

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
        if _has_perm(request.user, 'payroll.view'):
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
        if not _has_perm(request.user, 'payroll.view_own'):
            return error('You do not have permission to view payslips.', http_status=403)

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
        if not _has_perm(request.user, 'payroll.edit'):
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
