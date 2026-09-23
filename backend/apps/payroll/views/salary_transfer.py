"""
Dual-confirmation salary transfer.

Employee side: every payslip in the cycle must already be
EmployeePayslip.STATUS_ACKNOWLEDGED, STATUS_RESOLVED, or STATUS_PAID — no
payslip stuck unacknowledged or with an unresolved query.

Employer side: HR explicitly confirms via ConfirmSalaryTransferView, only
once the employee side is satisfied. Confirming snapshots every employee's
current bank details into SalaryTransferItem rows, which are then the ONLY
source the bank-transfer file is ever generated from — never live
EmployeeProfile data — so a bank-detail change after both sides have signed
off cannot silently redirect a transfer that's already locked.
"""
import csv
import io
import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from apps.accounts.models import AuditLog
from apps.payroll.models import EmployeePayslip, PayrollCycle, SalaryTransferBatch, SalaryTransferItem
from apps.payroll.views.shared import _is_admin, _resolve_user_branch

logger = logging.getLogger(__name__)

_EMPLOYEE_CONFIRMED_STATUSES = [
    EmployeePayslip.STATUS_ACKNOWLEDGED,
    EmployeePayslip.STATUS_RESOLVED,
    EmployeePayslip.STATUS_PAID,
]


def _cycle_ready_for_transfer_confirmation(cycle) -> tuple:
    """True (employee side satisfied) or (False, reason) for this cycle."""
    payslips = cycle.payslips.all()
    if not payslips.exists():
        return False, 'This cycle has no payslips generated yet.'
    not_ready = payslips.exclude(status__in=_EMPLOYEE_CONFIRMED_STATUSES)
    if not_ready.exists():
        return False, (
            f'{not_ready.count()} payslip(s) are not yet acknowledged by the employee, '
            'or still have an unresolved query.'
        )
    return True, ''


def _branch_scoped_or_403(request, cycle):
    """Returns an error response if a non-admin's branch doesn't match the cycle's, else None."""
    if _is_admin(request.user):
        return None
    branch_obj = _resolve_user_branch(request.user)
    if branch_obj is None or cycle.branch_id != branch_obj.pk:
        return error('You can only act on payroll for your own Company Code.', http_status=403)
    return None


class SalaryTransferStatusView(APIView):
    """GET employee-side readiness + current batch status for a cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        denied = _branch_scoped_or_403(request, cycle)
        if denied:
            return denied

        ready, reason = _cycle_ready_for_transfer_confirmation(cycle)
        batch = SalaryTransferBatch.objects.filter(cycle=cycle).first()
        return success('Salary transfer status retrieved.', {
            'employee_side_ready': ready,
            'reason': reason,
            'batch_status': batch.status if batch else None,
            'confirmed_at': batch.confirmed_at if batch else None,
            'confirmed_by': batch.confirmed_by.full_name if batch and batch.confirmed_by else None,
            'item_count': batch.items.count() if batch else 0,
        })


class ConfirmSalaryTransferView(APIView):
    """POST — employer-side confirmation. Locks a bank-detail snapshot for every payslip."""

    permission_classes = [IsAuthenticated]

    def post(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can confirm salary transfer.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        denied = _branch_scoped_or_403(request, cycle)
        if denied:
            return denied

        ready, reason = _cycle_ready_for_transfer_confirmation(cycle)
        if not ready:
            return error(reason)

        batch, _created = SalaryTransferBatch.objects.get_or_create(cycle=cycle)
        if batch.status == SalaryTransferBatch.STATUS_CONFIRMED:
            return error("This cycle's salary transfer has already been confirmed.")

        payslips = list(
            cycle.payslips.select_related('employee', 'employee__profile')
        )
        missing_bank_details = [
            p.employee.full_name for p in payslips
            if not getattr(p.employee, 'profile', None)
            or not p.employee.profile.account_number
            or not p.employee.profile.ifsc_code
        ]
        if missing_bank_details:
            return error(
                'The following employees have no bank account details on file: '
                + ', '.join(missing_bank_details)
            )

        with transaction.atomic():
            batch.items.all().delete()
            items = [
                SalaryTransferItem(
                    batch=batch,
                    payslip=payslip,
                    employee=payslip.employee,
                    account_holder_name=(
                        payslip.employee.profile.account_holder_name or payslip.employee.full_name
                    ),
                    account_number=payslip.employee.profile.account_number,
                    ifsc_code=payslip.employee.profile.ifsc_code,
                    bank_name=payslip.employee.profile.bank_name,
                    amount=payslip.net_pay,
                )
                for payslip in payslips
            ]
            SalaryTransferItem.objects.bulk_create(items)
            batch.status = SalaryTransferBatch.STATUS_CONFIRMED
            batch.confirmed_at = timezone.now()
            batch.confirmed_by = request.user
            batch.cancelled_at = None
            batch.cancelled_by = None
            batch.cancellation_reason = ''
            batch.save(update_fields=[
                'status', 'confirmed_at', 'confirmed_by',
                'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at',
            ])

        total_amount = sum((i.amount for i in items), start=payslips[0].net_pay * 0)
        AuditLog.objects.create(
            user=request.user, action='salary_transfer_confirmed', module='payroll',
            object_id=str(batch.id),
            changes={
                'cycle': str(cycle.id), 'employee_count': len(items),
                'total_amount': str(total_amount),
            },
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        logger.info(
            'Salary transfer confirmed for cycle %s by %s (%d employees)',
            cycle.id, request.user.email, len(items),
        )
        return success('Salary transfer confirmed and locked.', {
            'batch_id': str(batch.id), 'employee_count': len(items),
        })


class CancelSalaryTransferView(APIView):
    """POST — cancel a confirmed-but-not-yet-transferred batch (e.g. a mistake found before download)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can cancel a salary transfer.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        denied = _branch_scoped_or_403(request, cycle)
        if denied:
            return denied

        batch = SalaryTransferBatch.objects.filter(cycle=cycle).first()
        if not batch or batch.status != SalaryTransferBatch.STATUS_CONFIRMED:
            return error('There is no confirmed salary transfer to cancel for this cycle.')
        if batch.file_generated_at:
            return error(
                'The transfer file has already been downloaded for this batch. '
                'Cancel the transfer with your bank directly, then contact an administrator.'
            )

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return error('A cancellation reason is required.')

        batch.status = SalaryTransferBatch.STATUS_CANCELLED
        batch.cancelled_at = timezone.now()
        batch.cancelled_by = request.user
        batch.cancellation_reason = reason
        batch.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='salary_transfer_cancelled', module='payroll',
            object_id=str(batch.id), changes={'cycle': str(cycle.id), 'reason': reason},
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        return success('Salary transfer cancelled.')


class SalaryTransferFileDownloadView(APIView):
    """
    GET — generates the bank bulk-transfer CSV from the locked
    SalaryTransferItem snapshot only. Never re-reads live EmployeeProfile
    data, and never writes the file to disk/storage — built in-memory and
    streamed directly as the response.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can download the transfer file.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=cycle_pk)
        denied = _branch_scoped_or_403(request, cycle)
        if denied:
            return denied

        batch = SalaryTransferBatch.objects.filter(cycle=cycle).first()
        if not batch or batch.status != SalaryTransferBatch.STATUS_CONFIRMED:
            return error('Salary transfer must be confirmed before the file can be downloaded.')

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            'Employee ID', 'Beneficiary Name', 'Account Number', 'IFSC Code',
            'Bank Name', 'Amount', 'Transfer Mode',
        ])
        for item in batch.items.select_related('employee').order_by('employee__full_name'):
            writer.writerow([
                item.employee.employee_id or '',
                item.account_holder_name,
                item.account_number,
                item.ifsc_code,
                item.bank_name,
                f'{item.amount:.2f}',
                'NEFT',
            ])

        batch.file_generated_at = timezone.now()
        batch.file_generated_by = request.user
        batch.save(update_fields=['file_generated_at', 'file_generated_by', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='salary_transfer_file_downloaded', module='payroll',
            object_id=str(batch.id),
            changes={'cycle': str(cycle.id), 'employee_count': batch.items.count()},
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        logger.info('Salary transfer file downloaded for cycle %s by %s', cycle.id, request.user.email)

        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="salary_transfer_{cycle.cycle_start}_{cycle.id}.csv"'
        )
        return response
