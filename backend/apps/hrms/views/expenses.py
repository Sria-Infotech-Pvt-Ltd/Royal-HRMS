import logging

from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from ..models import (
    Expense, ExpenseReceipt,
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
)
from ..serializers import (
    ExpenseCreateSerializer,
    ExpenseSerializer,
    validate_receipt_file,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _resolve_branch(user):
    branch_name = getattr(user, 'branch', None)
    if not branch_name:
        return None
    from apps.branch.models import Branch
    return Branch.objects.filter(branch_name__iexact=branch_name).first()


class ExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        has_approve = _has_perm(request.user, 'expenses.approve')
        queryset = (
            Expense.objects.select_related('employee', 'branch')
                           .prefetch_related('receipts')
                           .all()
            if has_approve
            else Expense.objects.select_related('employee', 'branch')
                                .prefetch_related('receipts')
                                .filter(employee=request.user)
        )

        branch = request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch_id=branch)

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        serializer = ExpenseSerializer(queryset, many=True, context={'request': request})
        return success('Expenses retrieved.', serializer.data)

    def post(self, request):
        receipt_files = request.FILES.getlist('receipts')
        if not receipt_files:
            return error('At least one receipt is required.')

        for receipt_file in receipt_files:
            try:
                validate_receipt_file(receipt_file)
            except Exception as exc:
                return error(str(exc))

        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        branch  = _resolve_branch(request.user)
        expense = serializer.save(employee=request.user, branch=branch)

        for receipt_file in receipt_files:
            ExpenseReceipt.objects.create(expense=expense, file=receipt_file)

        logger.info('Expense submitted: %s by %s (%d receipts)', expense.title, request.user.email, len(receipt_files))

        out = ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch')
                           .prefetch_related('receipts')
                           .get(pk=expense.pk),
            context={'request': request},
        )
        return success('Expense submitted successfully.', out.data, http_status=status.HTTP_201_CREATED)


class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def _get_expense(self, expense_id: str, user):
        try:
            expense = (
                Expense.objects.select_related('employee', 'branch')
                               .prefetch_related('receipts')
                               .get(id=expense_id)
            )
        except Expense.DoesNotExist:
            return None, error('Expense not found.', http_status=status.HTTP_404_NOT_FOUND)
        has_approve = _has_perm(user, 'expenses.approve')
        if not has_approve and expense.employee_id != user.id:
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return expense, None

    def get(self, request, expense_id: str):
        expense, err = self._get_expense(expense_id, request.user)
        if err:
            return err
        return success('Expense retrieved.', ExpenseSerializer(expense, context={'request': request}).data)

    def put(self, request, expense_id: str):
        expense, err = self._get_expense(expense_id, request.user)
        if err:
            return err
        if expense.employee_id != request.user.id:
            return error('Only the submitter can edit an expense.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status != STATUS_PENDING:
            return error('Only pending expenses can be edited.', http_status=status.HTTP_409_CONFLICT)
        serializer = ExpenseCreateSerializer(expense, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        new_receipts = request.FILES.getlist('receipts')
        if new_receipts:
            for receipt_file in new_receipts:
                try:
                    validate_receipt_file(receipt_file)
                except Exception as exc:
                    return error(str(exc))
            expense.receipts.all().delete()
            for receipt_file in new_receipts:
                ExpenseReceipt.objects.create(expense=expense, file=receipt_file)
        out = ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch').prefetch_related('receipts').get(pk=expense.pk),
            context={'request': request},
        )
        logger.info('Expense %s updated by %s', expense_id, request.user.email)
        return success('Expense updated.', out.data)

    def patch(self, request, expense_id: str):
        expense, err = self._get_expense(expense_id, request.user)
        if err:
            return err
        if expense.employee_id != request.user.id:
            return error('Only the submitter can edit an expense.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status != STATUS_PENDING:
            return error('Only pending expenses can be edited.', http_status=status.HTTP_409_CONFLICT)
        serializer = ExpenseCreateSerializer(expense, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        new_receipts = request.FILES.getlist('receipts')
        if new_receipts:
            for receipt_file in new_receipts:
                try:
                    validate_receipt_file(receipt_file)
                except Exception as exc:
                    return error(str(exc))
            expense.receipts.all().delete()
            for receipt_file in new_receipts:
                ExpenseReceipt.objects.create(expense=expense, file=receipt_file)
        out = ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch').prefetch_related('receipts').get(pk=expense.pk),
            context={'request': request},
        )
        logger.info('Expense %s patched by %s', expense_id, request.user.email)
        return success('Expense updated.', out.data)

    def post(self, request, expense_id: str):
        return self.patch(request, expense_id)

    def delete(self, request, expense_id: str):
        expense, err = self._get_expense(expense_id, request.user)
        if err:
            return err
        has_approve = _has_perm(request.user, 'expenses.approve')
        if not has_approve and expense.employee_id != request.user.id:
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status == STATUS_APPROVED:
            return error(
                'Approved expenses cannot be deleted.',
                http_status=status.HTTP_409_CONFLICT,
            )
        expense.delete()
        logger.info('Expense %s deleted by %s', expense_id, request.user.email)
        return success('Expense deleted.')


class ExpenseApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    _STATUS_CHOICES = [
        {'value': STATUS_PENDING,  'label': 'Pending'},
        {'value': STATUS_APPROVED, 'label': 'Approved'},
        {'value': STATUS_REJECTED, 'label': 'Rejected'},
    ]

    def _get_expense(self, expense_id: str):
        try:
            return (
                Expense.objects.select_related('employee', 'branch')
                               .prefetch_related('receipts')
                               .get(id=expense_id)
            ), None
        except Expense.DoesNotExist:
            return None, error('Expense not found.', http_status=status.HTTP_404_NOT_FOUND)

    def get(self, request, expense_id: str):
        if not _has_perm(request.user, 'expenses.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        expense, err = self._get_expense(expense_id)
        if err:
            return err
        return success('Expense retrieved.', {
            'expense':        ExpenseSerializer(expense, context={'request': request}).data,
            'status_choices': self._STATUS_CHOICES,
        })

    def post(self, request, expense_id: str):
        if not _has_perm(request.user, 'expenses.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        expense, err = self._get_expense(expense_id)
        if err:
            return err
        if expense.status != STATUS_PENDING:
            return error(
                f'Expense is already {expense.status}. Only pending expenses can be actioned.',
                http_status=status.HTTP_409_CONFLICT,
            )
        action = request.data.get('action', '').strip()
        if action not in ('approve', 'reject'):
            return error('action must be "approve" or "reject".')
        expense.status = STATUS_APPROVED if action == 'approve' else STATUS_REJECTED
        expense.save(update_fields=['status', 'updated_at'])
        logger.info('Expense %s %sd by %s', expense_id, action, request.user.email)
        out = ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch').prefetch_related('receipts').get(pk=expense.pk),
            context={'request': request},
        )
        return success(f'Expense {action}d.', out.data)

    def put(self, request, expense_id: str):
        return self.post(request, expense_id)

    def patch(self, request, expense_id: str):
        return self.post(request, expense_id)

    def delete(self, request, expense_id: str):
        return error(
            'Use DELETE /expenses/<id>/ to delete an expense.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )


class ExpenseStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_approve = _has_perm(request.user, 'expenses.approve')
        queryset = (
            Expense.objects.all()
            if has_approve
            else Expense.objects.filter(employee=request.user)
        )

        stats = queryset.aggregate(
            total           = Count('id'),
            pending_count   = Count('id', filter=Q(status='pending')),
            approved_count  = Count('id', filter=Q(status='approved')),
            rejected_count  = Count('id', filter=Q(status='rejected')),
            total_amount    = Sum('amount'),
            pending_amount  = Sum('amount', filter=Q(status='pending')),
            approved_amount = Sum('amount', filter=Q(status='approved')),
        )

        return success('Stats retrieved.', {
            'total':           stats['total']           or 0,
            'pending':         stats['pending_count']   or 0,
            'approved':        stats['approved_count']  or 0,
            'rejected':        stats['rejected_count']  or 0,
            'total_amount':    float(stats['total_amount']    or 0),
            'pending_amount':  float(stats['pending_amount']  or 0),
            'approved_amount': float(stats['approved_amount'] or 0),
        })
